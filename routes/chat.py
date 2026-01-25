import asyncio
from fastapi import APIRouter, WebSocket
from openai_client import get_openai_client

router = APIRouter()
sessions = {}

@router.websocket("/chat")
async def chat_socket(ws: WebSocket):
    await ws.accept()
    client = get_openai_client()
    sid = id(ws)

    sessions[sid] = {
        "messages": [{
            "role": "system",
            "content": (
                "You are LawHelpZone AI, a legal assistant. "
                "Answer legal questions only. "
                "End every answer with: "
                "'⚖️ This information is AI-generated and not legal advice.'"
            )
        }]
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

    finally:
        sessions.pop(sid, None)
        await ws.close()
