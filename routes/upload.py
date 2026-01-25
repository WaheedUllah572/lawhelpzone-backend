import os
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, HTTPException
import fitz
from docx import Document as DocxReader
from database import SessionLocal, Document
from openai_client import get_openai_client

router = APIRouter()
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def extract_text(path: str) -> str:
    if path.endswith(".pdf"):
        with fitz.open(path) as pdf:
            return "".join(p.get_text() for p in pdf)
    if path.endswith(".docx"):
        return "\n".join(p.text for p in DocxReader(path).paragraphs)
    if path.endswith(".txt"):
        return open(path, encoding="utf-8", errors="ignore").read()
    raise HTTPException(400, "Unsupported file")

@router.post("/")
async def upload(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename)[1].lower()
    path = os.path.join(UPLOAD_DIR, f"{int(datetime.utcnow().timestamp())}{ext}")

    data = await file.read()
    if not data:
        raise HTTPException(400, "Empty file")

    with open(path, "wb") as f:
        f.write(data)

    try:
        text = extract_text(path)
        if len(text) < 50:
            raise HTTPException(400, "Document too short")

        client = get_openai_client()
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": text[:4000]}],
            temperature=0.3,
        )

        analysis = res.choices[0].message.content.strip()

        db = SessionLocal()
        doc = Document(title=file.filename, content=analysis)
        db.add(doc)
        db.commit()
        db.refresh(doc)

        return {"doc_id": doc.id, "ai_summary": analysis}

    finally:
        if os.path.exists(path):
            os.remove(path)
