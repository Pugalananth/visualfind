from fastapi import APIRouter, Depends

from ..deps import get_db
from ..services.app_settings import get_app_settings

router = APIRouter(prefix="/api/public", tags=["public"])


@router.get("/policy")
async def policy(db=Depends(get_db)):
    """Live values the Privacy page quotes, so the page never drifts from real configuration."""
    cfg = await get_app_settings(db)
    return {"retention_days": cfg["retention_days"], "registration_enabled": cfg["registration_enabled"],
            "max_video_mb": cfg["max_video_mb"], "min_password_length": cfg["min_password_length"],
            "default_threshold": cfg["default_threshold"], "default_detection_mode": cfg["default_detection_mode"]}
