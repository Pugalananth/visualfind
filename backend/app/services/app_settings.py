from ..db import utcnow

DEFAULTS = {
    "registration_enabled": True,
    "min_password_length": 8,
    "default_threshold": 0.70,
    "default_detection_mode": "auto",
    "max_video_mb": 500,
    "max_url_download_mb": 500,
    "url_download_timeout_s": 120,
    "max_sampled_frames": 900,
    "retention_days": 30,
}


async def get_app_settings(db) -> dict:
    doc = await db.app_settings.find_one({"_id": "app"}) or {}
    out = dict(DEFAULTS)
    out.update({k: v for k, v in doc.items() if k in DEFAULTS})
    return out


async def update_app_settings(db, changes: dict) -> dict:
    changes = {k: v for k, v in changes.items() if k in DEFAULTS and v is not None}
    if changes:
        changes["updated_at"] = utcnow()
        await db.app_settings.update_one({"_id": "app"}, {"$set": changes}, upsert=True)
    return await get_app_settings(db)
