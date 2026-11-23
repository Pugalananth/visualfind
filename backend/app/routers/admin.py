import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from ..config import get_settings
from ..db import iso
from ..deps import client_ip, get_db, require_admin
from ..schemas import AdminSettingsIn, UserAdminUpdateIn
from ..services import audit, search_service, system_status
from ..services.app_settings import get_app_settings, update_app_settings
from ..services.users import detail_user, public_user

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


def _day(value: str, end: bool = False) -> datetime:
    try:
        d = datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
    except ValueError:
        raise HTTPException(422, "Dates must be in YYYY-MM-DD format.")
    return d + timedelta(days=1) if end else d


@router.get("/overview")
async def overview(db=Depends(get_db)):
    c = db.searches.count_documents
    stats = {
        "total_users": await db.users.count_documents({}),
        "active_users": await db.users.count_documents({"is_active": True}),
        "total_searches": await c({}),
        "completed_searches": await c({"status": "completed"}),
        "failed_searches": await c({"status": "failed"}),
    }
    total_matches = 0
    async for s in db.searches.find({"status": "completed"}, {"match_count": 1}):
        total_matches += s.get("match_count", 0)
    stats["total_matches"] = total_matches
    recent_searches = []
    async for s in db.searches.find({}).sort("created_at", -1).limit(8):
        owner = await db.users.find_one({"_id": s["user_id"]})
        recent_searches.append(search_service.serialize_search(s, owner))
    recent_users = [detail_user(u) async for u in db.users.find({}).sort("created_at", -1).limit(8)]
    return {"stats": stats, "recent_searches": recent_searches, "recent_users": recent_users}


@router.get("/users")
async def list_users(q: str | None = None, skip: int = Query(0, ge=0), limit: int = Query(25, ge=1, le=100),
                     db=Depends(get_db)):
    query: dict = {}
    if q:
        rx = {"$regex": re.escape(q.strip()), "$options": "i"}
        query["$or"] = [{"name": rx}, {"email": rx}]
    total = await db.users.count_documents(query)
    items = []
    async for u in db.users.find(query).sort("created_at", -1).skip(skip).limit(limit):
        d = detail_user(u)
        d["search_count"] = await db.searches.count_documents({"user_id": u["_id"]})
        items.append(d)
    return {"total": total, "items": items}


@router.get("/users/{user_id}")
async def user_detail(user_id: str, db=Depends(get_db)):
    u = await db.users.find_one({"_id": user_id})
    if not u:
        raise HTTPException(404, "User not found.")
    c = db.searches.count_documents
    usage = {"searches": await c({"user_id": user_id}), "completed": await c({"user_id": user_id, "status": "completed"}),
             "failed": await c({"user_id": user_id, "status": "failed"}), "matches": 0}
    async for s in db.searches.find({"user_id": user_id, "status": "completed"}, {"match_count": 1}):
        usage["matches"] += s.get("match_count", 0)
    recent = [search_service.serialize_search(s) async for s in
              db.searches.find({"user_id": user_id}).sort("created_at", -1).limit(20)]
    return {**detail_user(u), "usage": usage, "recent_searches": recent}


@router.patch("/users/{user_id}")
async def update_user(user_id: str, body: UserAdminUpdateIn, request: Request, admin=Depends(require_admin),
                      db=Depends(get_db)):
    u = await db.users.find_one({"_id": user_id})
    if not u:
        raise HTTPException(404, "User not found.")
    changes = {}
    if body.is_active is not None and body.is_active != u.get("is_active", True):
        if user_id == admin["_id"]:
            raise HTTPException(409, "You cannot deactivate your own account.")
        changes["is_active"] = body.is_active
    if body.role is not None and body.role != u["role"]:
        if user_id == admin["_id"]:
            raise HTTPException(409, "You cannot change your own role.")
        changes["role"] = body.role
    if not changes:
        return detail_user(u)
    from ..db import utcnow
    await db.users.update_one({"_id": user_id}, {"$set": {**changes, "updated_at": utcnow()},
                                                 "$inc": {"token_version": 1 if "role" in changes else 0}})
    ip = client_ip(request)
    if "is_active" in changes:
        await audit.record(db, "user.activated" if changes["is_active"] else "user.deactivated", actor=admin,
                           target=user_id, metadata={"email": u["email"]}, ip=ip)
    if "role" in changes:
        await audit.record(db, "admin.changed_user_role", actor=admin, target=user_id,
                           metadata={"email": u["email"], "from": u["role"], "to": changes["role"]}, ip=ip)
    return detail_user(await db.users.find_one({"_id": user_id}))


@router.get("/searches")
async def list_searches(user_id: str | None = None, user: str | None = None, status: str | None = None, mode: str | None = None,
                        date_from: str | None = None, date_to: str | None = None,
                        skip: int = Query(0, ge=0), limit: int = Query(25, ge=1, le=100), db=Depends(get_db)):
    q: dict = {}
    if user_id:
        q["user_id"] = user_id
    if user:
        rx = {"$regex": re.escape(user.strip()), "$options": "i"}
        ids = [u["_id"] async for u in db.users.find({"$or": [{"name": rx}, {"email": rx}]}, {"_id": 1})]
        q["user_id"] = {"$in": ids}
    if status:
        q["status"] = status
    if mode:
        q["detection_mode"] = mode
    if date_from or date_to:
        q["created_at"] = {}
        if date_from:
            q["created_at"]["$gte"] = _day(date_from)
        if date_to:
            q["created_at"]["$lt"] = _day(date_to, end=True)
    total = await db.searches.count_documents(q)
    items = []
    async for s in db.searches.find(q).sort("created_at", -1).skip(skip).limit(limit):
        items.append(search_service.serialize_search(s, await db.users.find_one({"_id": s["user_id"]})))
    return {"total": total, "items": items}


@router.get("/jobs")
async def jobs(db=Depends(get_db)):
    counts = {st: await db.searches.count_documents({"status": st}) for st in ("queued", "processing", "completed", "failed")}
    active = []
    async for s in db.searches.find({"status": {"$in": ["queued", "processing"]}}).sort("created_at", 1).limit(50):
        active.append(search_service.serialize_search(s, await db.users.find_one({"_id": s["user_id"]})))
    failed = []
    async for s in db.searches.find({"status": "failed"}).sort("created_at", -1).limit(20):
        failed.append(search_service.serialize_search(s, await db.users.find_one({"_id": s["user_id"]})))
    return {"counts": counts, "active": active, "recent_failed": failed,
            "concurrency": get_settings().search_concurrency}


@router.get("/system")
async def system(request: Request):
    return {"services": await system_status.collect(request)}


@router.get("/audit-logs")
async def audit_logs(action: str | None = None, actor: str | None = None, date_from: str | None = None,
                     date_to: str | None = None, skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200),
                     db=Depends(get_db)):
    q: dict = {}
    if action:
        q["action"] = {"$regex": re.escape(action), "$options": "i"}
    if actor:
        q["actor_email"] = {"$regex": re.escape(actor), "$options": "i"}
    if date_from or date_to:
        q["created_at"] = {}
        if date_from:
            q["created_at"]["$gte"] = _day(date_from)
        if date_to:
            q["created_at"]["$lt"] = _day(date_to, end=True)
    total = await db.audit_logs.count_documents(q)
    items = [audit.serialize(d) async for d in db.audit_logs.find(q).sort("created_at", -1).skip(skip).limit(limit)]
    return {"total": total, "items": items}


@router.get("/settings")
async def read_settings(db=Depends(get_db)):
    s = get_settings()
    return {"settings": await get_app_settings(db),
            "environment": {"storage_backend": "local", "token_ttl_minutes": s.token_ttl_minutes,
                            "email_delivery": s.smtp_configured, "search_concurrency": s.search_concurrency,
                            "database": s.mongodb_db_name, "encoder_checkpoint": s.encoder_checkpoint.name,
                            "yolo_weights": s.yolo_weights}}


@router.put("/settings")
async def write_settings(body: AdminSettingsIn, request: Request, admin=Depends(require_admin), db=Depends(get_db)):
    changes = {k: v for k, v in body.model_dump().items() if v is not None}
    new = await update_app_settings(db, changes)
    await audit.record(db, "admin.settings_updated", actor=admin, metadata=changes, ip=client_ip(request))
    return {"settings": new}
