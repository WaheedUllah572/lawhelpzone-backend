import os
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
router = APIRouter()
sessions = {}

def get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    return OpenAI(api_key=api_key)

@router.websocket("/chat")
async def chat_socket(ws: WebSocket):
    await ws.accept()

    try:
        client = get_openai_client()
    except Exception:
        await ws.send_text("⚖️ AI service not configured.")
        await ws.close()
        return

    sid = id(ws)
    sessions[sid] = {
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are LawHelpZone AI, a professional legal assistant. "
                    "Answer legal questions only. "
                    "Always end your response with: "
                    "'⚖️ This information is AI-generated and not legal advice.'"
                ),
            }
        ]
    }

    try:
        while True:
            try:
                msg = await asyncio.wait_for(ws.receive_text(), timeout=60)
            except asyncio.TimeoutError:
                await ws.send_text("__PING__")
                continue

            if not msg.strip():
                continue

            sessions[sid]["messages"].append({"role": "user", "content": msg})

            try:
                res = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=sessions[sid]["messages"],
                    temperature=0.6,
                )
                reply = res.choices[0].message.content.strip()
            except Exception:
                reply = "⚖️ Service temporarily unavailable."

            sessions[sid]["messages"].append({"role": "assistant", "content": reply})
            await ws.send_text(reply)

    except WebSocketDisconnect:
        pass
    finally:
        sessions.pop(sid, None)
