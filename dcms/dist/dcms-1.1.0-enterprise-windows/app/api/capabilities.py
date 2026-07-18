from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_permission
from app.database import get_db
from app.models import Permission, User
from app.schemas import CapabilitiesResponse
from app.services.capabilities import get_platform_capabilities

router = APIRouter(prefix="/platform", tags=["Platform"])


@router.get("/capabilities", response_model=CapabilitiesResponse)
async def platform_capabilities(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.VIEW))],
):
    return await get_platform_capabilities(db)
