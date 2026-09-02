"""
Authentication router — identical API surface, now backed by MongoDB.

What changed vs the original:
  - Removed: AsyncSession / get_db_session / SQLAlchemy imports
  - Added:   MongoUserRepository / get_mongo_user_repo / MongoUser imports
  - db.commit() calls removed (Mongo is auto-commit)
  - UserModel references replaced with MongoUser
  - All endpoint signatures / URLs / response models are UNCHANGED
"""
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr

from .mongo_db import MongoUserRepository, MongoUser, get_mongo_user_repo
from .utils import (
    Token, UserOut, verify_password, get_password_hash,
    create_access_token, create_refresh_token, decode_token,
    ACCESS_TOKEN_EXPIRE_MINUTES
)
from .oauth import get_google_user, get_github_user
from .email_utils import send_reset_email

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")

# ── Schemas (unchanged) ──────────────────────────────────────────────────────

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


# ── Dependencies ─────────────────────────────────────────────────────────────

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    repo: MongoUserRepository = Depends(get_mongo_user_repo),
) -> MongoUser:
    """Dependency to get the current authenticated user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_token(token)
    if payload is None:
        raise credentials_exception

    email: str = payload.get("sub")
    if email is None:
        raise credentials_exception

    user = await repo.get_by_email(email)
    if user is None:
        raise credentials_exception

    return user


# ── Endpoints (API surface UNCHANGED) ────────────────────────────────────────

@router.post("/signup", response_model=UserOut)
async def signup(
    user_in: UserCreate,
    repo: MongoUserRepository = Depends(get_mongo_user_repo),
):
    """Register a new user."""
    existing_user = await repo.get_by_email(user_in.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    user = MongoUser(
        email=user_in.email,
        name=user_in.name,
        hashed_password=get_password_hash(user_in.password),
        auth_provider="LOCAL",
        is_active=True,
        is_verified=False,
    )
    await repo.create(user)
    return user


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    repo: MongoUserRepository = Depends(get_mongo_user_repo),
):
    """Login with email and password."""
    user = await repo.get_by_email(form_data.username)
    if not user or not user.hashed_password or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email, "user_id": user.id},
        expires_delta=access_token_expires
    )
    refresh_token = create_refresh_token(data={"sub": user.email})

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "refresh_token": refresh_token,
    }


@router.get("/me", response_model=UserOut)
async def read_users_me(current_user: MongoUser = Depends(get_current_user)):
    """Get the current authenticated user."""
    return current_user


@router.get("/google/callback")
async def google_callback(
    code: str,
    request: Request,
    redirect_uri: Optional[str] = None,
    repo: MongoUserRepository = Depends(get_mongo_user_repo),
):
    """Handle Google OAuth callback."""
    if not redirect_uri:
        redirect_uri = (
            str(request.url_for("google_callback")).replace("http://", "https://")
            if "https" in str(request.base_url)
            else str(request.url_for("google_callback"))
        )

    try:
        google_user = await get_google_user(code, redirect_uri)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Google authentication failed: {str(e)}"
        )

    email = google_user.get("email")
    name = google_user.get("name")
    picture = google_user.get("picture")
    provider_id = google_user.get("sub")

    user = await repo.get_by_email(email)

    if not user:
        user = MongoUser(
            email=email,
            name=name,
            auth_provider="GOOGLE",
            provider_user_id=provider_id,
            profile_image=picture,
            is_active=True,
            is_verified=True,
        )
        await repo.create(user)
    else:
        user.auth_provider = "GOOGLE"
        user.provider_user_id = provider_id
        user.profile_image = picture
        await repo.update(user)

    access_token = create_access_token(data={"sub": user.email, "user_id": user.id})
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/github/callback")
async def github_callback(
    code: str,
    repo: MongoUserRepository = Depends(get_mongo_user_repo),
    redirect_uri: Optional[str] = None,
):
    """Handle GitHub OAuth callback."""
    github_user = await get_github_user(code, redirect_uri)
    email = github_user.get("email")
    name = github_user.get("name") or github_user.get("login")
    picture = github_user.get("avatar_url")
    provider_id = str(github_user.get("id"))

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub did not return an email address"
        )

    user = await repo.get_by_email(email)

    if not user:
        user = MongoUser(
            email=email,
            name=name,
            auth_provider="GITHUB",
            provider_user_id=provider_id,
            profile_image=picture,
            is_active=True,
            is_verified=True,
        )
        await repo.create(user)
    else:
        user.auth_provider = "GITHUB"
        user.provider_user_id = provider_id
        user.profile_image = picture
        await repo.update(user)

    access_token = create_access_token(data={"sub": user.email, "user_id": user.id})
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/forgot-password")
async def forgot_password(
    request: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    repo: MongoUserRepository = Depends(get_mongo_user_repo),
):
    """Request a password reset."""
    user = await repo.get_by_email(request.email)
    if user:
        token = create_access_token(
            data={"sub": user.email, "purpose": "reset-password"},
            expires_delta=timedelta(hours=1)
        )
        background_tasks.add_task(send_reset_email, user.email, token)

    return {"detail": "If the email exists, a reset link has been sent."}


@router.post("/reset-password")
async def reset_password(
    request: ResetPasswordRequest,
    repo: MongoUserRepository = Depends(get_mongo_user_repo),
):
    """Reset password using a token."""
    payload = decode_token(request.token)
    if not payload or payload.get("purpose") != "reset-password":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )

    email = payload.get("sub")
    user = await repo.get_by_email(email)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.hashed_password = get_password_hash(request.new_password)
    await repo.update(user)

    return {"detail": "Password has been reset successfully."}


@router.post("/logout")
async def logout():
    """Logout endpoint (JWT is stateless; client deletes the token)."""
    return {"detail": "Successfully logged out"}
