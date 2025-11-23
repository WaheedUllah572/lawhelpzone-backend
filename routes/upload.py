import sys
import os

# 🧩 FIX: prevent PyMuPDF from confusing your React folder ("webapp") as a Python module
sys.path = [p for p in sys.path if not p.endswith("frontend") and "webapp" not in p]

from fastapi import APIRouter, UploadFile, File, HTTPException
from openai import OpenAI
import fitz  # PyMuPDF for PDFs
from docx import Document as DocxReader  # for .docx
from database import SessionLocal, Document
from datetime import datetime

router = APIRouter()
client = OpenAI()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ----------------------------
# Extract text from file
# ----------------------------
def extract_text(file_path: str):
    """Extract text content from PDF, DOCX, or TXT."""
    if file_path.endswith(".pdf"):
        text = ""
        with fitz.open(file_path) as pdf:
            for page in pdf:
                text += page.get_text("text")
        return text

    elif file_path.endswith(".docx"):
        doc = DocxReader(file_path)
        return "\n".join([p.text for p in doc.paragraphs])

    elif file_path.endswith(".txt"):
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    raise HTTPException(status_code=400, detail="Unsupported file type. Use PDF, DOCX, or TXT.")


# ----------------------------
# AI Document Analysis (Summary + Clause Detection + Risk Rating)
# ----------------------------
def analyze_document(content: str):
    """Summarize and extract legal clauses from the uploaded document."""
    prompt = f"""
    You are an advanced Legal AI Analyst.

    Analyze the following contract/document text and produce a detailed report including:
    1. ### Summary — concise overview of what the document is about.
    2. ### Breakdown of Major Legal Clauses — clearly labeled and emoji-tagged sections:
       ⚖️ **Governing Law Clause:** ...
       💰 **Payment Terms:** ...
       🤝 **Confidentiality Clause:** ...
       🚪 **Termination Clause:** ...
       ⏱️ **Duration Clause:** ...
       🧾 **Liability Clause:** ...
       ✉️ **Dispute Resolution Clause:** ...
       🧩 **Other Important Clauses (if found):** ...
    3. ⚠️ **Missing Clauses:** List any standard clauses that are not found.
    4. 🔍 **AI Legal Risk Assessment:**
       - Rate each clause as 🟢 Low Risk / 🟠 Moderate Risk / 🔴 High Risk.
       - Add a short reason for the rating.
       - End with a one-line “Overall Document Risk Summary”.

    Document Content (truncated to 4000 chars):
    {content[:4000]}
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a professional legal contract analyzer."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )
        return response.choices[0].message.content
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI analysis failed: {str(e)}")


# ----------------------------
# Save to Supabase DB
# ----------------------------
def save_to_db(title: str, content: str, user_id="guest"):
    """Save analysis result to the Supabase PostgreSQL database."""
    db = SessionLocal()
    try:
        doc = Document(
            title=title,
            content=content,
            user_id=user_id,
            created_at=datetime.utcnow(),
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        return doc.id
    finally:
        db.close()


# ----------------------------
# Upload and Process Route
# ----------------------------
@router.post("/")
async def upload_file(file: UploadFile = File(...)):
    """Upload a legal document, extract content, analyze with AI, and store in DB."""
    try:
        file_ext = os.path.splitext(file.filename)[1].lower()
        temp_path = os.path.join(UPLOAD_DIR, f"{datetime.utcnow().timestamp()}{file_ext}")
        with open(temp_path, "wb") as f:
            f.write(await file.read())

        text_content = extract_text(temp_path)
        ai_analysis = analyze_document(text_content)
        doc_id = save_to_db(title=file.filename, content=ai_analysis)
        os.remove(temp_path)

        print(f"📄 File processed: {file.filename} | Saved as ID: {doc_id}")
        return {
            "status": "success",
            "message": f"File '{file.filename}' analyzed successfully",
            "doc_id": doc_id,
            "ai_summary": ai_analysis,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
