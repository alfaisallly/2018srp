from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_permission
from app.database import get_db
from app.models import Permission, User
from app.schemas import ExcelImportPreview, ExcelImportResult
from app.services.excel_apply import apply_excel_import
from app.services.excel_import import generate_template_bytes, parse_excel_bytes

router = APIRouter(prefix="/import", tags=["Excel Import"])

ALLOWED_EXTENSIONS = {".xlsx", ".xls"}


@router.get("/excel/template")
async def download_template(
    _: Annotated[User, Depends(require_permission(Permission.VIEW))],
):
    content = generate_template_bytes()
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="dcms-import-template.xlsx"'},
    )


@router.post("/excel/preview", response_model=ExcelImportPreview)
async def preview_excel(
    file: UploadFile = File(...),
    _: Annotated[User, Depends(require_permission(Permission.MANAGE_DEVICES))] = None,
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="لم يُرفع ملف")
    ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="يُقبل ملف Excel فقط (.xlsx)")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="الملف أكبر من 10MB")

    result = parse_excel_bytes(content)
    return ExcelImportPreview(
        summary=result.summary,
        datacenters=result.datacenters,
        errors=result.errors,
        assets=[
            {
                "row": a.row,
                "datacenter": a.datacenter,
                "asset_type": a.asset_type,
                "name": a.name,
                "ip_address": a.ip_address,
                "vendor": a.vendor,
                "protocol": a.protocol,
            }
            for a in result.assets
        ],
        links=[
            {"row": l.row, "datacenter": l.datacenter, "from": l.from_ref, "to": l.to_ref, "label": l.label}
            for l in result.links
        ],
    )


@router.post("/excel/apply", response_model=ExcelImportResult)
async def apply_excel(
    file: UploadFile = File(...),
    skip_existing: bool = True,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    _: Annotated[User, Depends(require_permission(Permission.MANAGE_DEVICES))] = None,
):
    content = await file.read()
    parsed = parse_excel_bytes(content)
    if not parsed.assets:
        raise HTTPException(status_code=400, detail="لا توجد أصول للاستيراد")

    stats = await apply_excel_import(session=db, assets=parsed.assets, links=parsed.links, skip_existing=skip_existing)
    return ExcelImportResult(**stats)
