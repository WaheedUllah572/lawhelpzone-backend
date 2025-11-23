from fastapi import APIRouter, WebSocket, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from openai import OpenAI
import os, asyncio, json

load_dotenv()
router = APIRouter()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
sessions = {}

def load_law_fallback():
    try:
        with open("data/laws/LawFacts.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
LAW_FACTS = load_law_fallback()


@router.websocket("/chat")
async def chat_socket(ws: WebSocket):
    await ws.accept()
    session_id = id(ws)

    sessions.pop(session_id, None)
    sessions[session_id] = {
        "messages": [{
            "role": "system",
            "content": (
                "You are LawHelpZone AI, a professional yet friendly legal assistant (2025). "
                "You specialize in explaining laws, regulations, rights, and compliance across jurisdictions. "
                "If the user greets you, warmly introduce yourself as LawHelpZone. "
                "If a question is unrelated to law, reply: "
                "'I'm trained to discuss legal topics only.' "
                "Always end your response with: "
                "'⚖️ This information is AI-generated for educational purposes and is not legal advice.'"
            )
        }],
        "last_jurisdiction": "General",
    }

    try:
        while True:
            try:
                user_message = await asyncio.wait_for(ws.receive_text(), timeout=60)
            except asyncio.TimeoutError:
                await ws.send_text("__PING__")
                continue

            if not user_message.strip():
                await ws.send_text("⚠️ I didn’t catch that. Could you please repeat?")
                continue

            user_question = user_message.strip()
            last_jurisdiction = sessions[session_id]["last_jurisdiction"]

            detection_prompt = (
                f"Identify which country's or region's legal system this question most likely relates to. "
                f"Examples: Pakistan, UK, Australia, India, Canada, USA, EU. "
                f"If unclear, respond '{last_jurisdiction}'.\n\nQuestion: {user_question}"
            )

            try:
                classification = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "system", "content": detection_prompt}],
                    temperature=0.0,
                )
                jurisdiction = classification.choices[0].message.content.strip() or last_jurisdiction
            except Exception:
                jurisdiction = last_jurisdiction

            sessions[session_id]["last_jurisdiction"] = jurisdiction

            contextual_prompt = (
                f"The user's legal question falls under **{jurisdiction}** law. "
                f"Start your answer with a short jurisdiction tag like '🇵🇰 Pakistan Law:' or "
                f"'🇺🇸 United States Law:' accordingly. Provide a professional and up-to-date explanation.\n\n"
                f"User question: {user_question}"
            )

            sessions[session_id]["messages"].append({"role": "user", "content": contextual_prompt})

            try:
                completion = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=sessions[session_id]["messages"],
                    temperature=0.6,
                )
                reply = completion.choices[0].message.content.strip()
            except Exception:
                reply = LAW_FACTS.get(jurisdiction, {}).get(
                    "general", "⚖️ Unable to fetch response. Try again later."
                )

            response_payload = f"__JURISDICTION__:{jurisdiction}\n{reply}"
            sessions[session_id]["messages"].append({"role": "assistant", "content": reply})
            await ws.send_text(response_payload)

    except Exception as e:
        try:
            await ws.send_text(f"Error: {str(e)}")
        except Exception:
            pass
        finally:
            if ws.client_state.name != "DISCONNECTED":
                await ws.close()
            sessions.pop(session_id, None)
