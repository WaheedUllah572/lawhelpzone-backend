from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from openai_client import get_openai_client

router = APIRouter()

class GenerateRequest(BaseModel):
    type: str
    partyA: str
    partyB: str
    effectiveDate: str
    country: str
    clauses: str | None = None

@router.post("/generate")
async def generate(req: GenerateRequest):
    client = get_openai_client()

    prompt = (
        f"Draft a professional {req.type} agreement between {req.partyA} and {req.partyB}, "
        f"effective {req.effectiveDate} under {req.country} law."
    )
    if req.clauses:
        prompt += f"\nInclude clauses: {req.clauses}"

    try:
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You draft formal legal documents."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
        )
        return {"content": res.choices[0].message.content}

    except Exception as e:
        raise HTTPException(500, str(e))
