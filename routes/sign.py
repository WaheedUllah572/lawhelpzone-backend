from fastapi import APIRouter, Form, UploadFile, File, HTTPException
from database import SessionLocal, Document
from datetime import datetime
from fpdf import FPDF
import os, tempfile, traceback, hashlib, requests

router = APIRouter()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Supabase credentials missing in environment variables.")

BUCKET_NAME = "signed_documents"

# ---------- HELPER: UPLOAD VIA REST ----------
def supabase_upload(path: str, file_bytes: bytes):
    url = f"{SUPABASE_URL}/storage/v1/object/{BUCKET_NAME}/{path}"

    headers = {
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "apikey": SUPABASE_KEY,
        "Content-Type": "application/octet-stream"
    }

    r = requests.post(url, headers=headers, data=file_bytes)

    if r.status_code not in [200, 201]:
        raise Exception(f"Supabase upload error: {r.text}")

    return f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/{path}"


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

        file_bytes = await signature.read()

        with open(temp_signature_path, "wb") as f:
            f.write(file_bytes)

        # ----- UPLOAD SIGNATURE -----
        signature_storage_path = f"signatures/{doc_id}_{timestamp}_{signature.filename}"

        signature_url = supabase_upload(signature_storage_path, file_bytes)

        sig_hash = hashlib.sha256(file_bytes).hexdigest()

        # Update DB
        doc.signer_name = signer_name
        doc.signature_url = signature_url
        doc.signature_hash = sig_hash
        db.commit()

        # ----- GENERATE PDF -----
        signed_pdf_path = generate_signed_pdf(
            doc.title,
            doc.content,
            signer_name,
            temp_signature_path
        )

        with open(signed_pdf_path, "rb") as f:
            pdf_bytes = f.read()

        signed_pdf_storage_path = f"signed_pdfs/{doc_id}_signed.pdf"

        signed_pdf_url = supabase_upload(signed_pdf_storage_path, pdf_bytes)

        doc.signed_pdf_url = signed_pdf_url
        db.commit()

        # Cleanup
        os.remove(temp_signature_path)
        os.remove(signed_pdf_path)

        return {
            "status": "success",
            "signature_url": signature_url,
            "signed_pdf_url": signed_pdf_url
        }

    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()
