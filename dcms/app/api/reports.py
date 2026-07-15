from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_permission
from app.database import get_db
from app.models import Permission, User
from app.schemas import DashboardStats
from app.services.report_service import generate_datacenter_report, get_dashboard_stats

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/dashboard", response_model=DashboardStats)
async def dashboard(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.VIEW_REPORTS))],
):
    stats = await get_dashboard_stats(db)
    return DashboardStats(**stats)


@router.get("/datacenter/{datacenter_id}/pdf")
async def datacenter_pdf_report(
    datacenter_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.VIEW_REPORTS))],
):
    content = await generate_datacenter_report(db, datacenter_id)
    media_type = "application/pdf" if content[:4] == b"%PDF" else "text/html"
    filename = "report.pdf" if media_type == "application/pdf" else "report.html"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
