from datetime import datetime, timedelta, timezone

import bcrypt
from jose import jwt

from app.core.config import settings


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), password_hash.encode("utf-8")
        )
    except ValueError:
        return False


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode(
        "utf-8"
    )


def create_access_token(
    subject: str,
    roles: list[str],
    permissions: list[str] | None = None,
    menus: list[dict] | None = None,
    username: str | None = None,
    display_name: str | None = None,
) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {
        "sub": subject,
        "roles": roles,
        "permissions": permissions or [],
        "menus": menus or [],
        "exp": expires_at,
    }
    if username:
        payload["username"] = username
    if display_name:
        payload["display_name"] = display_name
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
