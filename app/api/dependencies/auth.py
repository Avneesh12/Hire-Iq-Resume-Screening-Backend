from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.db.models import User
from app.db.redis import is_token_denied
from app.db.session import get_db

bearer = HTTPBearer(auto_error=True)

_401 = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or expired token.",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    1. Decode JWT — raise 401 if invalid/expired
    2. Check Redis denylist — raise 401 if logged out
    3. Load user from PostgreSQL — raise 401 if not found/inactive
    """
    try:
        payload = decode_token(credentials.credentials)
        user_id: str = payload["sub"]
        jti: str = payload["jti"]
    except (JWTError, KeyError):
        raise _401

    # Denylist check (O(1) Redis lookup)
    if await is_token_denied(jti):
        raise _401

    result = await db.execute(select(User).where(User.id == user_id, User.is_active == True))
    user = result.scalar_one_or_none()
    if not user:
        raise _401

    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required.")
    return current_user
