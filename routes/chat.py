import os
import asyncio
import json
from fastapi import APIRouter, WebSocket
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
router = APIRouter()

sessions = {}

def get_openai_client():
    # ✅ LAZY INIT — proxies already removed by main.py
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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
    client = get_openai_client()
    session_id = id(ws)

    sessions[session_id] = {
        "messages": [{
            "role": "system",
            "content": (
                "You are LawHelpZone AI, a professional legal assistant. "
                "Answer legal questions only and always add a disclaimer."
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
                continue

            sessions[session_id]["messages"].append({
                "role": "user",
                "content": user_message
            })

            try:
                completion = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=sessions[session_id]["messages"],
                    temperature=0.6,
                )
                reply = completion.choices[0].message.content.strip()
            except Exception:
                reply = "⚖️ Unable to fetch response right now."

            sessions[session_id]["messages"].append({
                "role": "assistant",
                "content": reply
            })

            await ws.send_text(reply)

    finally:
        sessions.pop(session_id, None)
        await ws.close()
