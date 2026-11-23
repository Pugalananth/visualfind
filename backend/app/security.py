import base64
import hashlib
import re
import secrets
from datetime import timedelta
from pathlib import Path

import bcrypt
import jwt
from cryptography.fernet import Fernet, InvalidToken

from .config import get_settings
from .db import utcnow

ALGORITHM = "HS256"


def _file_secret(name: str) -> str:
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    path: Path = settings.data_dir / name
    if path.exists():
        return path.read_text().strip()
    value = secrets.token_urlsafe(48)
    path.write_text(value)
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return value


def jwt_secret() -> str:
    return get_settings().jwt_secret or _file_secret(".jwt_secret")


def _fernet() -> Fernet:
    raw = _file_secret(".enc_key")
    key = base64.urlsafe_b64encode(hashlib.sha256(raw.encode()).digest())
    return Fernet(key)


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_secret(token: str) -> str | None:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        return None


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode()[:72], password_hash.encode())
    except ValueError:
        return False


def password_problems(password: str, min_length: int = 8) -> list[str]:
    problems = []
    if len(password) < min_length:
        problems.append(f"at least {min_length} characters")
    if len(password.encode()) > 72:
        problems.append("at most 72 bytes")
    if not re.search(r"[a-z]", password):
        problems.append("a lowercase letter")
    if not re.search(r"[A-Z]", password):
        problems.append("an uppercase letter")
    if not re.search(r"\d", password):
        problems.append("a digit")
    return problems


def create_access_token(user: dict) -> str:
    settings = get_settings()
    now = utcnow()
    payload = {
        "sub": user["_id"],
        "role": user["role"],
        "tv": user.get("token_version", 0),
        "iat": now,
        "exp": now + timedelta(minutes=settings.token_ttl_minutes),
    }
    return jwt.encode(payload, jwt_secret(), algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, jwt_secret(), algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
