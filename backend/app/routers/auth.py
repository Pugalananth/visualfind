import logging
import secrets
import time
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request

from ..config import get_settings
from ..db import new_id, utcnow
from ..deps import client_ip, current_user, get_db
from ..schemas import ForgotIn, LoginIn, RegisterIn, ResetIn
from ..security import (create_access_token, hash_password, hash_token, password_problems,
                        verify_password)
from ..services import audit
from ..services.app_settings import get_app_settings
from ..services.emailer import send_email
from ..services.users import EmailTaken, create_user, public_user

router = APIRouter(prefix="/api/auth", tags=["auth"])
log = logging.getLogger("visualfind.auth")

_fails: dict[str, list[float]] = {}
MAX_FAILS, WINDOW = 5, 15 * 60


def _throttled(key: str) -> bool:
    now = time.time()
    _fails[key] = [t for t in _fails.get(key, []) if now - t < WINDOW]
    return len(_fails[key]) >= MAX_FAILS


def _problem_text(problems: list[str]) -> str:
    return "Password must contain " + ", ".join(problems) + "."


@router.post("/register", status_code=201)
async def register(body: RegisterIn, request: Request, db=Depends(get_db)):
    cfg = await get_app_settings(db)
    if not cfg["registration_enabled"]:
        raise HTTPException(403, "Registration is currently disabled.")
    if body.password != body.confirm_password:
        raise HTTPException(422, "Passwords do not match.")
    problems = password_problems(body.password, cfg["min_password_length"])
    if problems:
        raise HTTPException(422, _problem_text(problems))
    try:
        user = await create_user(db, body.name, body.email, body.password, role="USER")  # public signup is always USER
    except EmailTaken:
        raise HTTPException(409, "An account with this email already exists.")
    await audit.record(db, "user.registered", actor=user, target=user["_id"], ip=client_ip(request))
    return public_user(user)


@router.post("/login")
async def login(body: LoginIn, request: Request, db=Depends(get_db)):
    key = f"{body.email}|{client_ip(request)}"
    if _throttled(key):
        raise HTTPException(429, "Too many failed sign-in attempts. Try again in a few minutes.")
    user = await db.users.find_one({"email": body.email})
    if not user or not verify_password(body.password, user["password_hash"]):
        _fails.setdefault(key, []).append(time.time())
        await audit.record(db, "auth.login_failed", target=body.email, ip=client_ip(request))
        raise HTTPException(401, "Invalid email or password.")
    if not user.get("is_active", True):
        raise HTTPException(403, "This account has been deactivated.")
    _fails.pop(key, None)
    await db.users.update_one({"_id": user["_id"]}, {"$set": {"last_login_at": utcnow()}})
    await audit.record(db, "admin.login" if user["role"] == "ADMIN" else "user.login",
                       actor=user, target=user["_id"], ip=client_ip(request))
    return {"access_token": create_access_token(user), "token_type": "bearer", "user": public_user(user)}


@router.post("/logout")
async def logout(request: Request, user=Depends(current_user), db=Depends(get_db)):
    await audit.record(db, "user.logout", actor=user, target=user["_id"], ip=client_ip(request))
    return {"ok": True}


@router.get("/me")
async def me(user=Depends(current_user)):
    return public_user(user)


@router.post("/forgot-password")
async def forgot_password(body: ForgotIn, request: Request, db=Depends(get_db)):
    """Always answers the same way so account existence is not revealed."""
    settings = get_settings()
    user = await db.users.find_one({"email": body.email.lower()})
    if user and user.get("is_active", True):
        token = secrets.token_urlsafe(32)
        await db.password_resets.insert_one({"_id": new_id(), "user_id": user["_id"], "token_hash": hash_token(token),
                                             "created_at": utcnow(), "expires_at": utcnow() + timedelta(hours=1)})
        link = f"{settings.frontend_url.rstrip('/')}/reset-password?token={token}"
        sent = send_email(user["email"], "Reset your VisualFind password",
                          f"Use this link within one hour to choose a new password:\n\n{link}\n")
        if not sent:
            log.warning("SMTP not configured; password reset link for %s: %s", user["email"], link)
        await audit.record(db, "auth.password_reset_requested", actor=user, target=user["_id"], ip=client_ip(request))
    return {"ok": True, "email_delivery": settings.smtp_configured}


@router.post("/reset-password")
async def reset_password(body: ResetIn, request: Request, db=Depends(get_db)):
    cfg = await get_app_settings(db)
    if body.password != body.confirm_password:
        raise HTTPException(422, "Passwords do not match.")
    problems = password_problems(body.password, cfg["min_password_length"])
    if problems:
        raise HTTPException(422, _problem_text(problems))
    rec = await db.password_resets.find_one_and_delete({"token_hash": hash_token(body.token)})
    exp = rec and rec["expires_at"]
    if not rec or (exp.tzinfo is None and exp < utcnow().replace(tzinfo=None)) or (exp.tzinfo is not None and exp < utcnow()):
        raise HTTPException(400, "This reset link is invalid or has expired.")
    await db.users.update_one({"_id": rec["user_id"]}, {"$set": {"password_hash": hash_password(body.password),
                              "updated_at": utcnow()}, "$inc": {"token_version": 1}})
    user = await db.users.find_one({"_id": rec["user_id"]})
    await audit.record(db, "auth.password_reset", actor=user, target=rec["user_id"], ip=client_ip(request))
    return {"ok": True}
