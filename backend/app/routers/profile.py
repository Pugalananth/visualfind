from fastapi import APIRouter, Depends, HTTPException, Request

from ..db import utcnow
from ..deps import client_ip, current_user, get_db
from ..config import get_settings
from ..schemas import PasswordChangeIn, ProfileUpdateIn
from ..security import create_access_token, hash_password, password_problems, verify_password
from ..services import audit
from ..services.app_settings import get_app_settings
from ..services.users import detail_user

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.get("")
async def get_profile(user=Depends(current_user), db=Depends(get_db)):
    count = await db.searches.count_documents({"user_id": user["_id"]})
    return {**detail_user(user), "search_count": count, "email_delivery": get_settings().smtp_configured}


@router.patch("")
async def update_profile(body: ProfileUpdateIn, user=Depends(current_user), db=Depends(get_db)):
    changes = {k: v for k, v in body.model_dump().items() if v is not None}  # role/status are not accepted here
    if changes:
        changes["updated_at"] = utcnow()
        await db.users.update_one({"_id": user["_id"]}, {"$set": changes})
        user = await db.users.find_one({"_id": user["_id"]})
    return detail_user(user)


@router.post("/password")
async def change_password(body: PasswordChangeIn, request: Request, user=Depends(current_user), db=Depends(get_db)):
    cfg = await get_app_settings(db)
    if not verify_password(body.current_password, user["password_hash"]):
        raise HTTPException(422, "Current password is incorrect.")
    if body.new_password != body.confirm_password:
        raise HTTPException(422, "Passwords do not match.")
    problems = password_problems(body.new_password, cfg["min_password_length"])
    if problems:
        raise HTTPException(422, "Password must contain " + ", ".join(problems) + ".")
    await db.users.update_one({"_id": user["_id"]}, {"$set": {"password_hash": hash_password(body.new_password),
                              "updated_at": utcnow()}, "$inc": {"token_version": 1}})
    user = await db.users.find_one({"_id": user["_id"]})
    await audit.record(db, "user.password_changed", actor=user, target=user["_id"], ip=client_ip(request))
    return {"ok": True, "access_token": create_access_token(user)}  # other sessions are invalidated
