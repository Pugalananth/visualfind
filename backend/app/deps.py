from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .security import decode_access_token

bearer = HTTPBearer(auto_error=False)


def get_db(request: Request):
    return request.app.state.db


def get_runtime(request: Request):
    return request.app.state.runtime


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


async def current_user(request: Request, creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    if creds is None:
        raise HTTPException(401, "Authentication required.", headers={"WWW-Authenticate": "Bearer"})
    payload = decode_access_token(creds.credentials)
    if not payload:
        raise HTTPException(401, "Your session has expired. Please sign in again.")
    user = await request.app.state.db.users.find_one({"_id": payload["sub"]})
    if not user or payload.get("tv", 0) != user.get("token_version", 0):
        raise HTTPException(401, "Your session is no longer valid. Please sign in again.")
    if not user.get("is_active", True):
        raise HTTPException(403, "This account has been deactivated.")
    return user


async def require_admin(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "ADMIN":
        raise HTTPException(403, "You do not have permission to access this resource.")
    return user
