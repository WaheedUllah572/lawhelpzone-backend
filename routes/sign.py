from fastapi import APIRouter, Form, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from database import SessionLocal, Document
from datetime import datetime
from fpdf import FPDF
from supabase import create_client, Client
import os, tempfile, traceback, hashlib

router = APIRouter()

# ----------------------------
# 🧩 Supabase client setup
# ----------------------------
import os

# --- Fix Supabase 'proxy' crash on Render ---
for var in ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"]:
    if var in os.environ:
        del os.environ[var]

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Supabase credentials missing in environment variables.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ----------------------------
# 🧾 Save signature + Regenerate Signed PDF
# ----------------------------
@router.post("/")
async def save_signature(
    doc_id: int = Form(...),
    signer_name: str = Form(...),
    signature: UploadFile = File(...),
):
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found.")

        # Save signature temporarily
        temp_dir = "temp_files"
        os.makedirs(temp_dir, exist_ok=True)
        timestamp = int(datetime.utcnow().timestamp())
        temp_signature_path = os.path.join(temp_dir, f"{timestamp}_{signature.filename}")

        # ✅ Save uploaded signature file
        file_bytes = await signature.read()
        with open(temp_signature_path, "wb") as f:
            f.write(file_bytes)

        # ✅ Upload signature to Supabase
        BUCKET_NAME = "signed_documents"
        signature_storage_path = f"signatures/{doc_id}_{timestamp}_{signature.filename}"

        with open(temp_signature_path, "rb") as f:
            res = supabase.storage.from_(BUCKET_NAME).upload(signature_storage_path, f)

        if "error" in str(res).lower():
            raise HTTPException(status_code=500, detail="Supabase upload failed. Check bucket permissions.")

        signature_url = supabase.storage.from_(BUCKET_NAME).get_public_url(signature_storage_path)
        sig_hash = hashlib.sha256(file_bytes).hexdigest()

        # ✅ Update DB with signature metadata
        doc.signer_name = signer_name
        doc.signature_url = signature_url
        doc.signature_hash = sig_hash
        db.commit()

        # ✅ Generate new signed PDF
        signed_pdf_path = generate_signed_pdf(doc.title, doc.content, signer_name, temp_signature_path)

        # ✅ Upload new signed PDF to Supabase (delete if already exists)
        signed_pdf_storage_path = f"signed_pdfs/{doc_id}_signed.pdf"
        try:
            # Delete old version if exists (avoids 'upsert' param issue)
            supabase.storage.from_(BUCKET_NAME).remove([signed_pdf_storage_path])
        except Exception:
            pass

        with open(signed_pdf_path, "rb") as f:
            res_pdf = supabase.storage.from_(BUCKET_NAME).upload(signed_pdf_storage_path, f)

        if "error" in str(res_pdf).lower():
            raise HTTPException(status_code=500, detail="Supabase PDF upload failed.")

        signed_pdf_url = supabase.storage.from_(BUCKET_NAME).get_public_url(signed_pdf_storage_path)

        # ✅ Save signed PDF URL
        doc.signed_pdf_url = signed_pdf_url
        db.commit()

        # ✅ Clean up temp files
        if os.path.exists(temp_signature_path):
            os.remove(temp_signature_path)
        if os.path.exists(signed_pdf_path):
            os.remove(signed_pdf_path)

        return {
            "status": "success",
            "message": f"Signature added and signed PDF generated for {signer_name}.",
            "signature_url": signature_url,
            "signed_pdf_url": signed_pdf_url,
        }

    except Exception as e:
        trace = traceback.format_exc()
        print(f"❌ Signature upload failed:\n{trace}")
        raise HTTPException(status_code=500, detail=f"Signature upload failed: {str(e)}")
    finally:
        db.close()


# ----------------------------
# 🧠 Generate Signed PDF with Embedded Signature
# ----------------------------
def generate_signed_pdf(title: str, content: str, signer_name: str, signature_path: str):
    FONT_DIR = os.path.join(os.path.dirname(__file__), "../fonts")
    FONT_REGULAR = os.path.join(FONT_DIR, "DejaVuSans.ttf")
    FONT_BOLD = os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf")
    FONT_ITALIC = os.path.join(FONT_DIR, "DejaVuSans-Oblique.ttf")

    for font_file in [FONT_REGULAR, FONT_BOLD, FONT_ITALIC]:
        if not os.path.exists(font_file):
            raise FileNotFoundError(f"Missing font file: {font_file}")

    pdf = FPDF()
    pdf.add_page()
    pdf.add_font("DejaVu", "", FONT_REGULAR, uni=True)
    pdf.add_font("DejaVu", "B", FONT_BOLD, uni=True)
    pdf.add_font("DejaVu", "I", FONT_ITALIC, uni=True)

    # Header
    pdf.set_fill_color(28, 33, 48)
    pdf.rect(0, 0, 210, 25, "F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("DejaVu", "B", 16)
    pdf.cell(0, 15, "LawHelpZone AI — Signed Legal Document", ln=True, align="C")
    pdf.ln(10)

    # Info
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("DejaVu", "", 12)
    pdf.cell(0, 10, f"Document Title: {title}", ln=True)
    pdf.cell(0, 10, f"Signed on: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}", ln=True)
    pdf.cell(0, 10, f"Signed by: {signer_name}", ln=True)
    pdf.ln(6)

    # Divider
    pdf.set_draw_color(180, 180, 180)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(8)

    # Content
    pdf.set_font("DejaVu", "", 11)
    pdf.multi_cell(0, 8, content)
    pdf.ln(20)

    # Signature Image Block
    pdf.set_font("DejaVu", "I", 11)
    pdf.cell(0, 10, "Authorized Signature:", ln=True)
    pdf.image(signature_path, x=30, y=pdf.get_y(), w=50)
    pdf.ln(30)
    pdf.cell(0, 10, f"({signer_name})", ln=True)

    # Footer
    pdf.set_y(-15)
    pdf.set_font("DejaVu", "I", 9)
    pdf.set_text_color(120)
    pdf.cell(0, 10, "Generated by LawHelpZone AI — www.lawhelpzone.com", 0, 0, "C")

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    pdf.output(tmp.name)
    return tmp.name
