from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.websockets import WebSocket
from routes.chat import router as chat_router
from routes.save import router as save_router
from routes.upload import router as upload_router
from routes.sign import router as sign_router
from routes.settings import router as settings_router
from routes.generate import router as generate_router
from database import init_db
import uvicorn, os
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
init_db()

# ✅ CORS Configuration (specific to your frontend)
origins = [
    "https://lawhelpzone-frontend-6hsi.vercel.app",
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.websocket("/ws/ping")
async def ws_ping(websocket: WebSocket):
    await websocket.accept()
    await websocket.send_text("pong")
    await websocket.close()

# Routers
app.include_router(chat_router, prefix="/api")
app.include_router(save_router, prefix="/api/save")
app.include_router(upload_router, prefix="/api/upload")
app.include_router(sign_router, prefix="/api/sign")
app.include_router(settings_router, prefix="/api/settings")
app.include_router(generate_router, prefix="/api")

@app.get("/")
def root():
    return {"message": "Backend running OK on port 5050 🚀"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=5050, reload=True)
