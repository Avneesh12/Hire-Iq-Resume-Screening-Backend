from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.api.schemas.schemas import (
    ApiResponse, AuthResponse, ForgotPasswordRequest,
    LoginRequest, RegisterRequest, UserOut,
)
from app.core.logger import get_logger
from app.core.security import (
    create_access_token, decode_token, hash_password,
    token_ttl_seconds, verify_password,
)
from app.db.models import User
from app.db.redis import deny_token
from app.db.session import get_db

logger = get_logger("auth")
router = APIRouter(prefix="/auth", tags=["Auth"])


def _serialize_user(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role,
        organization=user.organization,
        avatar=user.avatar,
        createdAt=user.created_at,
    )


# ── Register ──────────────────────────────────────────────────────────────────

@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)) -> AuthResponse:
    existing = await db.scalar(select(User).where(User.email == body.email))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )
    user = User(
        name=body.name,
        email=body.email,
        hashed_password=hash_password(body.password),
        organization=body.organization,
        role="recruiter",
    )
    db.add(user)
    await db.flush()
    token, _ = create_access_token(user.id, user.role)
    logger.info("Registered: %s (%s)", body.email, user.id)
    return AuthResponse(access_token=token, user=_serialize_user(user))


# ── Login ─────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)) -> AuthResponse:
    user = await db.scalar(select(User).where(User.email == body.email, User.is_active == True))
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")
    token, _ = create_access_token(user.id, user.role)
    logger.info("Login: %s", body.email)
    return AuthResponse(access_token=token, user=_serialize_user(user))


# ── Me ────────────────────────────────────────────────────────────────────────

@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)) -> UserOut:
    return _serialize_user(current_user)


# ── Update Profile ────────────────────────────────────────────────────────────

class UpdateProfileRequest(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=100)
    email: EmailStr | None = None
    job_title: str | None = None   # stored in avatar field as placeholder; ignored if not relevant


@router.patch("/me", response_model=UserOut)
async def update_profile(
    body: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    if body.name is not None:
        current_user.name = body.name
    if body.email is not None:
        # Check unique
        existing = await db.scalar(
            select(User).where(User.email == body.email, User.id != current_user.id)
        )
        if existing:
            raise HTTPException(status_code=409, detail="Email already in use.")
        current_user.email = body.email
    await db.flush()
    return _serialize_user(current_user)


# ── Change Password ───────────────────────────────────────────────────────────

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


@router.post("/change-password", response_model=ApiResponse)
async def change_password(
    body: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
    current_user.hashed_password = hash_password(body.new_password)
    await db.flush()
    return ApiResponse(success=True, message="Password updated successfully.")


# ── Logout ────────────────────────────────────────────────────────────────────

@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(current_user: User = Depends(get_current_user)) -> None:
    logger.info("Logout: %s", current_user.email)


# ── Forgot Password ───────────────────────────────────────────────────────────

@router.post("/forgot-password", response_model=ApiResponse)
async def forgot_password(body: ForgotPasswordRequest) -> ApiResponse:
    logger.info("Password reset requested: %s", body.email)
    return ApiResponse(
        success=True,
        message="If that email exists, a reset link has been sent.",
    )
