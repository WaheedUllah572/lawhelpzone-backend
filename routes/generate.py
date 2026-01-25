import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
router = APIRouter()

# ✅ Lazy, proxy-safe OpenAI client
def get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not configured")
    return OpenAI(api_key=api_key)

class GenerateRequest(BaseModel):
    type: str
    partyA: str
    partyB: str
    effectiveDate: str
    country: str
    clauses: str | None = None

@router.post("/generate")
async def generate(req: GenerateRequest):
    try:
        client = get_openai_client()

        prompt = (
            f"Draft a professional {req.type} agreement between {req.partyA} and {req.partyB}, "
            f"effective {req.effectiveDate} under {req.country} law. "
            f"Use clear legal formatting and numbered clauses."
        )

        if req.clauses:
            prompt += f"\nInclude these clauses: {req.clauses}"

        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You draft formal legal documents."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
        )

        return {"content": res.choices[0].message.content.strip()}

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Document generation failed: {str(e)}"
        )
