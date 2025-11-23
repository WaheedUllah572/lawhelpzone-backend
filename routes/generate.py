from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from openai import OpenAI
import os, traceback

router = APIRouter()

class GenerateRequest(BaseModel):
    type: str
    partyA: str
    partyB: str
    effectiveDate: str
    country: str
    clauses: str | None = None


@router.post("/generate")
async def generate_doc(req: GenerateRequest):
    """Generate a legal document using OpenAI's latest API."""
    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="OpenAI API key not configured")

        # ✅ New SDK client usage
        client = OpenAI(api_key=api_key)

        prompt = (
            f"Draft a professional {req.type} legal agreement between {req.partyA} and {req.partyB}, "
            f"effective from {req.effectiveDate} under {req.country} law. "
            f"Use clear legal formatting with numbered clauses and structured sections."
        )
        if req.clauses:
            prompt += f"\nInclude these specific custom clauses: {req.clauses}"

        # ✅ Correct API call for openai>=1.0.0
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional legal assistant that drafts clean, formal legal documents.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
        )

        content = response.choices[0].message.content
        return {"status": "success", "content": content}

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error generating text: {str(e)}")
