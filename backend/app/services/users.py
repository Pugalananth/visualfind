from pymongo.errors import DuplicateKeyError

from ..db import iso, new_id, utcnow
from ..security import hash_password


class EmailTaken(Exception):
    pass


async def create_user(db, name: str, email: str, password: str, role: str = "USER") -> dict:
    now = utcnow()
    doc = {
        "_id": new_id(),
        "name": name.strip(),
        "email": email.strip().lower(),
        "password_hash": hash_password(password),
        "role": role,
        "is_active": True,
        "token_version": 0,
        "notify_on_complete": False,
        "created_at": now,
        "updated_at": now,
        "last_login_at": None,
    }
    try:
        await db.users.insert_one(doc)
    except DuplicateKeyError as exc:
        raise EmailTaken(email) from exc
    return doc


def public_user(doc: dict) -> dict:
    return {"id": doc["_id"], "name": doc["name"], "email": doc["email"], "role": doc["role"]}


def detail_user(doc: dict) -> dict:
    return {
        **public_user(doc),
        "is_active": doc.get("is_active", True),
        "created_at": iso(doc.get("created_at")),
        "updated_at": iso(doc.get("updated_at")),
        "last_login_at": iso(doc.get("last_login_at")),
        "notify_on_complete": doc.get("notify_on_complete", False),
    }
