import os
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, HTTPException
from dotenv import load_dotenv
from openai import OpenAI
import fitz
from docx import Document as DocxReader
from database import SessionLocal, Document

load_dotenv()
router = APIRouter()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ✅ Lazy, proxy-safe OpenAI client
def get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not configured")
    return OpenAI(api_key=api_key)

def extract_text(path: str) -> str:
    if path.endswith(".pdf"):
        with fitz.open(path) as pdf:
            return "".join(page.get_text() for page in pdf)

    if path.endswith(".docx"):
        return "\n".join(p.text for p in DocxReader(path).paragraphs)

    if path.endswith(".txt"):
        with open(path, encoding="utf-8", errors="ignore") as f:
            return f.read()

    raise HTTPException(status_code=400, detail="Unsupported file")

@router.post("/")
async def upload(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename)[1].lower()
    path = os.path.join(
        UPLOAD_DIR,
        f"{int(datetime.utcnow().timestamp())}{ext}"
    )

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")

    with open(path, "wb") as f:
        f.write(data)

    try:
        text = extract_text(path)
        if len(text.strip()) < 50:
            raise HTTPException(status_code=400, detail="Document too short")

        client = get_openai_client()

        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": text[:4000]}],
            temperature=0.3,
        )

        analysis = res.choices[0].message.content.strip()

        db = SessionLocal()
        try:
            doc = Document(title=file.filename, content=analysis)
            db.add(doc)
            db.commit()
            db.refresh(doc)
            return {"doc_id": doc.id, "ai_summary": analysis}
        finally:
            db.close()

    finally:
        if os.path.exists(path):
            os.remove(path)
