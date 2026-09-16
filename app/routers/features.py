from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import AppError
from app.schemas import FeatureIn
from app.services import common

router = APIRouter(prefix="/api/v1/features", tags=["features"])


@router.get("")
def get_features(layer_id: int = Query(...), db: Session = Depends(get_db)):
    return common.list_features(db, layer_id)


@router.post("", status_code=status.HTTP_201_CREATED)
def post_feature(payload: FeatureIn, db: Session = Depends(get_db)):
    if payload.id is not None:
        raise AppError(422, "ID_NOT_ALLOWED", "创建要素时不能传 id", {"field": "id"})
    with db.begin():
        return common.create_feature(
            db,
            layer_id=payload.layer_id,
            geometry=payload.geometry.model_dump(),
            properties=payload.properties,
        )


@router.put("/{feature_id}")
def put_feature(feature_id: int, payload: FeatureIn, db: Session = Depends(get_db)):
    if payload.id is None:
        raise AppError(422, "ID_REQUIRED", "更新要素时必须提供 id", {"field": "id"})
    with db.begin():
        return common.update_feature(
            db,
            feature_id,
            body_id=payload.id,
            layer_id=payload.layer_id,
            geometry=payload.geometry.model_dump(),
            properties=payload.properties,
        )


@router.delete("/{feature_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_feature(feature_id: int, db: Session = Depends(get_db)):
    with db.begin():
        common.delete_feature(db, feature_id)
    return Response(status_code=204)
