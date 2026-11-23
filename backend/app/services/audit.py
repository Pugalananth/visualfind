import logging

from ..db import iso, new_id, utcnow

log = logging.getLogger("visualfind.audit")
_SENSITIVE = ("password", "key", "token", "secret", "authorization")


def _clean(meta: dict | None) -> dict:
    out = {}
    for k, v in (meta or {}).items():
        if any(s in k.lower() for s in _SENSITIVE):
            continue
        out[k] = v
    return out


async def record(db, action: str, actor: dict | None = None, target: str | None = None,
                 metadata: dict | None = None, ip: str | None = None) -> None:
    doc = {
        "_id": new_id(),
        "created_at": utcnow(),
        "action": action,
        "actor_id": actor["_id"] if actor else None,
        "actor_email": actor["email"] if actor else None,
        "actor_role": actor["role"] if actor else None,
        "target": target,
        "metadata": _clean(metadata),
        "ip": ip,
    }
    try:
        await db.audit_logs.insert_one(doc)
    except Exception:  # auditing must never take the request down
        log.exception("failed to write audit log for %s", action)


def serialize(doc: dict) -> dict:
    return {
        "id": doc["_id"],
        "timestamp": iso(doc["created_at"]),
        "actor_id": doc.get("actor_id"),
        "actor": doc.get("actor_email"),
        "actor_role": doc.get("actor_role"),
        "action": doc["action"],
        "target": doc.get("target"),
        "metadata": doc.get("metadata", {}),
        "ip": doc.get("ip"),
    }
