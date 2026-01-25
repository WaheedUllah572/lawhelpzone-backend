from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from openai import OpenAI
import os, asyncio

router = APIRouter()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@router.websocket("/chat")
async def chat_socket(ws: WebSocket):
    await ws.accept()
    print("✅ WebSocket client connected")

    try:
        while True:
            try:
                data = await asyncio.wait_for(ws.receive_text(), timeout=60)
            except asyncio.TimeoutError:
                await ws.send_text("__PING__")
                continue

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are LawHelpZone AI."},
                    {"role": "user", "content": data},
                ],
                temperature=0.6,
            )

            reply = response.choices[0].message.content.strip()
            await ws.send_text(reply)

    except WebSocketDisconnect:
        print("❌ WebSocket disconnected")
