from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import permissions_from_user, resolve_permissions
from app.core.security import (
    authenticate_user,
    create_access_token,
    get_current_user,
    hash_password,
    require_permission,
)
from app.database import get_db
from app.models import Permission, User
from app.schemas import MeResponse, TokenResponse, UserCreate, UserResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    user = await authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(user.username, user.role)
    return TokenResponse(access_token=token)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.MANAGE_USERS))],
):
    existing = await db.execute(select(User).where(User.username == payload.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already exists")

    perms = resolve_permissions(payload.role, payload.permissions)
    user = User(
        username=payload.username,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role,
        permissions=perms,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


@router.get("/me", response_model=MeResponse)
async def me(current_user: Annotated[User, Depends(get_current_user)]):
    perms = permissions_from_user(current_user)
    return MeResponse(
        **{k: getattr(current_user, k) for k in ("id", "username", "email", "full_name", "role", "permissions", "is_active", "created_at")},
        permission_keys=[p.value for p in perms],
    )


@router.post("/logout")
async def logout(current_user: Annotated[User, Depends(get_current_user)]):
    return {"message": "تم تسجيل الخروج", "username": current_user.username}
