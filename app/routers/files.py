import os
from pathlib import Path

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import AppError
from app.services.shapefile_service import (
    export_layer_to_zip,
    import_shapefile_zip,
)

router = APIRouter(tags=["files"])


@router.post("/api/v1/imports/shapefile", status_code=status.HTTP_201_CREATED)
async def import_shapefile(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise AppError(400, "ZIP_REQUIRED", "请上传 ZIP 格式的 Shapefile", {})

    data = await file.read()

    # 所有导入操作必须处于同一事务；任一要素失败则整体回滚。
    with db.begin():
        return import_shapefile_zip(db, data, file.filename)


@router.get("/api/v1/layers/{layer_id}/export")
def export_shapefile(
    layer_id: int,
    format: str = Query("shp"),
    db: Session = Depends(get_db),
):
    if format != "shp":
        raise AppError(422, "UNSUPPORTED_FORMAT", "当前仅支持 format=shp", {"format": format})

    zip_path, filename = export_layer_to_zip(db, layer_id)

    return FileResponse(
        path=str(zip_path),
        media_type="application/zip",
        filename=filename,
        headers={"Access-Control-Expose-Headers": "Content-Disposition"},
    )
