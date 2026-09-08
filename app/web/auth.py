"""Сессии, пароли, текущий пользователь."""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from typing import Optional

from fastapi import Request

from app.database.db import SessionLocal
from app.database.models import UserORM

PBKDF_ROUNDS = 120_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode(), PBKDF_ROUNDS)
    return f"{salt}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    if not stored or "$" not in stored:
        return False
    salt, hexed = stored.split("$", 1)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode(), PBKDF_ROUNDS)
    return hmac.compare_digest(dk.hex(), hexed)


def get_db_user(user_id: int) -> Optional[UserORM]:
    session = SessionLocal()
    try:
        return session.query(UserORM).filter(UserORM.id == user_id).first()
    finally:
        session.close()


def current_user(request: Request) -> Optional[UserORM]:
    uid = request.session.get("user_id")
    if not uid:
        return None
    return get_db_user(int(uid))


def login_user(request: Request, user: UserORM) -> None:
    request.session["user_id"] = user.id
    request.session["is_admin"] = bool(user.is_admin)


def logout_user(request: Request) -> None:
    request.session.clear()


def require_user(request: Request) -> Optional[UserORM]:
    return current_user(request)


def session_secret() -> str:
    return os.getenv("SECRET_KEY") or os.getenv("DIMAS_SECRET") or "dimas-dev-change-me"
