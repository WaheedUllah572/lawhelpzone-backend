import os

# 🔥 PERMANENT FIX: REMOVE RENDER PROXY VARS BEFORE ANY OTHER IMPORTS
for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
    os.environ.pop(key, None)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes.chat import router as chat_router
from routes.save import router as save_router
from routes.upload import router as upload_router
from routes.sign import router as sign_router
from routes.settings import router as settings_router
from routes.generate import router as generate_router
from database import init_db
import uvicorn
import asyncio

app = FastAPI(title="LawHelpZone AI Backend")

# -------------------------------------------------
# Startup (safe for Render)
# -------------------------------------------------
@app.on_event("startup")
async def startup_event():
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, init_db)

# -------------------------------------------------
# CORS
# -------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------
# ROUTERS
# -------------------------------------------------
app.include_router(chat_router, prefix="/api")
app.include_router(save_router, prefix="/api/save")
app.include_router(upload_router, prefix="/api/upload")
app.include_router(sign_router, prefix="/api/sign")
app.include_router(settings_router, prefix="/api/settings")
app.include_router(generate_router, prefix="/api")

# -------------------------------------------------
# Health check
# -------------------------------------------------
@app.get("/")
def root():
    return {"message": "Backend running OK 🚀"}

# -------------------------------------------------
# Render entrypoint
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
