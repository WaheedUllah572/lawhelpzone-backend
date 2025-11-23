from fastapi import APIRouter, HTTPException, Form
from database import SessionLocal, UserSettings
from datetime import datetime
from pydantic import BaseModel
import traceback

router = APIRouter()

class SettingsRequest(BaseModel):
    user_id: str | None = None
    openai_model: str | None = None
    theme: str | None = None
    api_key: str | None = None
    supabase_url: str | None = None


@router.get("/")
def get_settings(user_id: str = "default_user"):
    db = SessionLocal()
    try:
        settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
        if not settings:
            settings = UserSettings(user_id=user_id)
            db.add(settings)
            db.commit()
            db.refresh(settings)
        return {
            "user_id": settings.user_id,
            "openai_model": settings.openai_model,
            "theme": settings.theme,
            "api_key": settings.api_key,
            "supabase_url": settings.supabase_url,
            "updated_at": settings.updated_at,
        }
    except Exception as e:
        print("❌ Error fetching settings:", e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.post("/")
def update_settings(req: SettingsRequest):
    db = SessionLocal()
    try:
        settings = db.query(UserSettings).filter(UserSettings.user_id == req.user_id).first()
        if not settings:
            settings = UserSettings(user_id=req.user_id)
            db.add(settings)

        if req.openai_model:
            settings.openai_model = req.openai_model
        if req.theme:
            settings.theme = req.theme
        if req.api_key:
            settings.api_key = req.api_key
        if req.supabase_url:
            settings.supabase_url = req.supabase_url

        settings.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(settings)

        return {"status": "success", "updated": True, "data": settings.__dict__}
    except Exception:
        trace = traceback.format_exc()
        print(f"❌ Error updating settings:\n{trace}")
        raise HTTPException(status_code=500, detail="Failed to update settings")
    finally:
        db.close()
