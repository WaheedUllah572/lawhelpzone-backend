import os
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, HTTPException
from openai import OpenAI
import fitz
from docx import Document as DocxReader
from database import SessionLocal, Document

router = APIRouter()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def extract_text(path: str) -> str:
    if path.endswith(".pdf"):
        with fitz.open(path) as pdf:
            return "".join(p.get_text() for p in pdf)

    if path.endswith(".docx"):
        doc = DocxReader(path)
        return "\n".join(p.text for p in doc.paragraphs)

    if path.endswith(".txt"):
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    raise HTTPException(400, "Unsupported file type")

def analyze(text: str) -> str:
    if len(text) < 50:
        raise HTTPException(400, "Document too short")

    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": text[:4000]}],
        temperature=0.3,
    )
    return res.choices[0].message.content

def save(title: str, content: str) -> int:
    db = SessionLocal()
    try:
        doc = Document(title=title, content=content)
        db.add(doc)
        db.commit()
        db.refresh(doc)
        return doc.id
    finally:
        db.close()

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
        analysis = analyze(text)
        doc_id = save(file.filename, analysis)
        return {"doc_id": doc_id, "ai_summary": analysis}
    finally:
        if os.path.exists(path):
            os.remove(path)
