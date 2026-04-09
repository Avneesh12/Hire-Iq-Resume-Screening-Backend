from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings
from argon2 import PasswordHasher

ph = PasswordHasher()

# pwd_context = CryptContext(
#     schemes=["argon2"],
#     deprecated="auto"
# )


def hash_password(plain: str) -> str:
    return ph.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return ph.verify(hashed,plain)


def create_access_token(user_id: str, role: str) -> tuple[str, str]:
    """
    Create a signed JWT access token.
    Returns (token, jti) — jti is stored in Redis on logout.
    """
    jti = str(uuid4())
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload: dict[str, Any] = {
        "sub": user_id,
        "role": role,
        "jti": jti,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return token, jti


def decode_token(token: str) -> dict[str, Any]:
    """Decode and verify. Raises JWTError on failure."""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


def token_ttl_seconds(payload: dict) -> int:
    """Remaining lifetime of a token in seconds (for denylist TTL)."""
    exp = payload.get("exp", 0)
    remaining = int(exp - datetime.now(timezone.utc).timestamp())
    return max(remaining, 0)
