from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_permission
from app.database import get_db
from app.models import Alert, AlertStatus, Permission, User
from app.schemas import AlertResponse, AlertUpdate
from app.services.redis_service import publish_alert_event

router = APIRouter(prefix="/alerts", tags=["Alerts"])


@router.get("", response_model=list[AlertResponse])
async def list_alerts(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.VIEW))],
    status_filter: AlertStatus | None = None,
    datacenter_id: int | None = None,
):
    query = select(Alert).order_by(Alert.created_at.desc())
    if status_filter:
        query = query.where(Alert.status == status_filter)
    if datacenter_id:
        query = query.where(Alert.datacenter_id == datacenter_id)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.patch("/{alert_id}", response_model=AlertResponse)
async def update_alert(
    alert_id: int,
    payload: AlertUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.MANAGE_ALERTS))],
):
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.status = payload.status
    if payload.status == AlertStatus.RESOLVED:
        alert.resolved_at = datetime.now(timezone.utc)

    await db.flush()
    await publish_alert_event(alert.id, {"status": alert.status.value, "title": alert.title})
    await db.refresh(alert)
    return alert
