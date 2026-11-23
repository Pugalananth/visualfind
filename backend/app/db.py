import uuid
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase


def new_id() -> str:
    return uuid.uuid4().hex


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def connect(uri: str, db_name: str) -> tuple[AsyncIOMotorClient, AsyncIOMotorDatabase]:
    client = AsyncIOMotorClient(uri, tz_aware=True, serverSelectionTimeoutMS=5000)
    return client, client[db_name]


async def ensure_indexes(db) -> None:
    await db.users.create_index("email", unique=True)
    await db.searches.create_index([("user_id", 1), ("created_at", -1)])
    await db.searches.create_index("status")
    await db.searches.create_index("detection_mode")
    await db.searches.create_index("created_at")
    await db.search_results.create_index([("search_id", 1), ("rank", 1)])
    await db.search_frames.create_index([("search_id", 1), ("track_id", 1), ("frame_index", 1)])
    await db.audit_logs.create_index([("created_at", -1)])
    await db.audit_logs.create_index("action")
    await db.password_resets.create_index("token_hash", unique=True)
    await db.password_resets.create_index("expires_at", expireAfterSeconds=0)
