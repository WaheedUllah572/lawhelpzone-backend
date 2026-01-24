import sys
import os
from datetime import datetime

# 🧩 FIX: prevent PyMuPDF from confusing frontend folders as Python modules
sys.path = [
    p for p in sys.path
    if not p.endswith("frontend") and "webapp" not in p
]

from fastapi import APIRouter, UploadFile, File, HTTPException
from openai import OpenAI
import fitz  # PyMuPDF
from docx import Document as DocxReader
from database import SessionLocal, Document

router = APIRouter()
client = OpenAI()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# -------------------------------------------------
# Extract text from supported documents
# -------------------------------------------------
def extract_text(file_path: str) -> str:
    if file_path.endswith(".pdf"):
        text = ""
        with fitz.open(file_path) as pdf:
            for page in pdf:
                text += page.get_text("text")
        return text.strip()

    if file_path.endswith(".docx"):
        doc = DocxReader(file_path)
        return "\n".join(p.text for p in doc.paragraphs).strip()

    if file_path.endswith(".txt"):
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read().strip()

    raise HTTPException(
        status_code=400,
        detail="Unsupported file type. Use PDF, DOCX, or TXT."
    )

# -------------------------------------------------
# AI Document Analysis
# -------------------------------------------------
def analyze_document(content: str) -> str:
    if not content or len(content) < 50:
        raise HTTPException(
            status_code=400,
            detail="Document appears empty or unreadable."
        )

    prompt = f"""
You are an advanced Legal AI Analyst.

Analyze the following document and provide:

1. ### Summary
2. ### Major Legal Clauses (emoji-tagged)
3. ⚠️ Missing Clauses
4. 🔍 AI Legal Risk Assessment

Document Content (truncated):
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
        return response.choices[0].message.content.strip()

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"AI analysis failed: {str(e)}"
        )

# -------------------------------------------------
# Save analysis to database
# -------------------------------------------------
def save_to_db(title: str, content: str, user_id: str = "guest") -> int:
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

# -------------------------------------------------
# ✅ UPLOAD ENDPOINT (NO REDIRECTS)
# -------------------------------------------------
@router.post("")
async def upload_file(file: UploadFile = File(...)):
    """
    Upload a legal document, analyze with AI, and save results.
    """
    try:
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in [".pdf", ".docx", ".txt"]:
            raise HTTPException(status_code=400, detail="Unsupported file type.")

        temp_path = os.path.join(
            UPLOAD_DIR,
            f"{int(datetime.utcnow().timestamp())}{ext}"
        )

        contents = await file.read()
        if not contents:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        with open(temp_path, "wb") as f:
            f.write(contents)

        text_content = extract_text(temp_path)
        ai_analysis = analyze_document(text_content)
        doc_id = save_to_db(title=file.filename, content=ai_analysis)

        os.remove(temp_path)

        print(f"✅ File analyzed: {file.filename} | ID: {doc_id}")

        return {
            "status": "success",
            "doc_id": doc_id,
            "ai_summary": ai_analysis,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Upload failed: {str(e)}"
        )
