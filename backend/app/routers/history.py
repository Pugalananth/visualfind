from fastapi import APIRouter, Depends, HTTPException, Query

from ..deps import current_user, get_db
from ..services import audit, search_service

router = APIRouter(prefix="/api/history", tags=["history"])


async def list_own(skip: int, limit: int, status: str | None, user: dict, db) -> dict:
    q: dict = {"user_id": user["_id"]}  # ownership enforced here: a user only ever sees their own
    if status:
        q["status"] = status
    total = await db.searches.count_documents(q)
    items = [search_service.serialize_search(s) async for s in
             db.searches.find(q).sort("created_at", -1).skip(skip).limit(min(limit, 100))]
    return {"total": total, "items": items}


@router.get("")
async def history(skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100), status: str | None = None,
                  user=Depends(current_user), db=Depends(get_db)):
    return await list_own(skip, limit, status, user, db)


@router.delete("/{search_id}")
async def delete_search(search_id: str, user=Depends(current_user), db=Depends(get_db)):
    s = await db.searches.find_one({"_id": search_id, "user_id": user["_id"]})
    if not s:
        raise HTTPException(404, "Search not found.")
    if s["status"] in ("queued", "processing"):
        raise HTTPException(409, "This search is still running.")
    await search_service.purge_search(db, s)
    await audit.record(db, "search.deleted", actor=user, target=search_id)
    return {"ok": True}


@router.delete("")
async def delete_all(user=Depends(current_user), db=Depends(get_db)):
    """Delete all of the caller's finished searches (running ones are kept)."""
    n = 0
    async for s in db.searches.find({"user_id": user["_id"], "status": {"$in": ["completed", "failed"]}}):
        await search_service.purge_search(db, s)
        n += 1
    await audit.record(db, "history.cleared", actor=user, target=user["_id"], metadata={"deleted": n})
    return {"deleted": n}
