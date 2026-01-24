from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from routes.chat import router as chat_router
from routes.save import router as save_router
from routes.upload import router as upload_router
from routes.sign import router as sign_router
from routes.settings import router as settings_router
from routes.generate import router as generate_router
from database import init_db
import uvicorn, os, asyncio

# ---- GLOBAL PATCH FOR HTTPX PROXIES CRASH ----
import httpx

_real_init = httpx.Client.__init__

def _patched_init(self, *args, **kwargs):
    kwargs.pop("proxy", None)
    kwargs.pop("proxies", None)
    return _real_init(self, *args, **kwargs)

httpx.Client.__init__ = _patched_init
# ---------------------------------------------

os.makedirs("temp_files", exist_ok=True)

app = FastAPI(title="LawHelpZone AI Backend")

# ✅ INIT DB (non-blocking safe for Render)
@app.on_event("startup")
async def startup_event():
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, init_db)

# ✅ CORS (allow Vercel + local)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # WebSockets ignore CORS anyway, this is safe
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------
# ✅ REQUIRED FIX: REAL CHAT WEBSOCKET
# -------------------------------------------------
@app.websocket("/api/chat")
async def chat_websocket(websocket: WebSocket):
    await websocket.accept()
    print("✅ WebSocket client connected")

    try:
        while True:
            data = await websocket.receive_text()

            # ---- SIMPLE ECHO TEST (CONFIRMS WORKING) ----
            # Replace this later with your AI streaming logic
            await websocket.send_text(f"🤖 AI Response: {data}")

    except WebSocketDisconnect:
        print("❌ WebSocket disconnected")
    except Exception as e:
        print("❌ WebSocket error:", e)
        await websocket.close()

# -------------------------------------------------
# ROUTERS (REST APIs)
# -------------------------------------------------
app.include_router(chat_router, prefix="/api")
app.include_router(save_router, prefix="/api/save")
app.include_router(upload_router, prefix="/api/upload")
app.include_router(sign_router, prefix="/api/sign")
app.include_router(settings_router, prefix="/api/settings")
app.include_router(generate_router, prefix="/api")

@app.get("/")
def root():
    return {"message": "Backend running OK 🚀"}

# -------------------------------------------------
# RENDER ENTRYPOINT
# -------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        ws_ping_interval=20,
        ws_ping_timeout=20,
    )
