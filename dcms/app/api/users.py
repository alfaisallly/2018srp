from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import PERMISSION_LABELS, ROLE_TEMPLATES, resolve_permissions
from app.core.security import get_current_user, hash_password, require_permission
from app.database import get_db
from app.models import Permission, User
from app.schemas import (
    PermissionInfo,
    RoleTemplate,
    UserCreate,
    UserResponse,
    UserUpdate,
)

router = APIRouter(prefix="/users", tags=["User Management"])


@router.get("/permissions", response_model=list[PermissionInfo])
async def list_permissions(_: Annotated[User, Depends(require_permission(Permission.MANAGE_USERS))]):
    return [
        PermissionInfo(
            key=p.value,
            label=info["label"],
            group=info["group"],
            description=info["description"],
        )
        for p, info in PERMISSION_LABELS.items()
    ]


@router.get("/roles", response_model=list[RoleTemplate])
async def list_roles(_: Annotated[User, Depends(require_permission(Permission.MANAGE_USERS))]):
    return [
        RoleTemplate(
            key=key,
            label=data["label"],
            permissions=[p.value for p in data["permissions"]],
        )
        for key, data in ROLE_TEMPLATES.items()
    ]


@router.get("", response_model=list[UserResponse])
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.MANAGE_USERS))],
):
    result = await db.execute(select(User).order_by(User.username))
    return list(result.scalars().all())


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.MANAGE_USERS))],
):
    existing = await db.execute(select(User).where(User.username == payload.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="اسم المستخدم موجود مسبقاً")

    email_check = await db.execute(select(User).where(User.email == payload.email))
    if email_check.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="البريد الإلكتروني مستخدم مسبقاً")

    perms = resolve_permissions(payload.role, payload.permissions)
    user = User(
        username=payload.username,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role,
        permissions=perms,
        is_active=payload.is_active,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.MANAGE_USERS))],
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    return user


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[User, Depends(require_permission(Permission.MANAGE_USERS))],
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")

    if payload.email and payload.email != user.email:
        dup = await db.execute(select(User).where(User.email == payload.email, User.id != user_id))
        if dup.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="البريد الإلكتروني مستخدم مسبقاً")

    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.email is not None:
        user.email = payload.email
    if payload.role is not None:
        user.role = payload.role
    if payload.is_active is not None:
        if user.id == current.id and not payload.is_active:
            raise HTTPException(status_code=400, detail="لا يمكن تعطيل حسابك الحالي")
        user.is_active = payload.is_active
    if payload.password:
        user.hashed_password = hash_password(payload.password)
    if payload.role is not None or payload.permissions is not None:
        role = payload.role or user.role
        user.permissions = resolve_permissions(role, payload.permissions or user.permissions)

    await db.flush()
    await db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[User, Depends(require_permission(Permission.MANAGE_USERS))],
):
    if user_id == current.id:
        raise HTTPException(status_code=400, detail="لا يمكن حذف حسابك الحالي")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    await db.delete(user)
