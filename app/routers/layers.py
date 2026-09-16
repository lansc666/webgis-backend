from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import LayerCreate
from app.services import common

router = APIRouter(prefix="/api/v1/layers", tags=["layers"])


@router.get("")
def get_layers(db: Session = Depends(get_db)):
    return {"items": common.list_layers(db)}


@router.post("", status_code=status.HTTP_201_CREATED)
def post_layer(payload: LayerCreate, db: Session = Depends(get_db)):
    with db.begin():
        return common.create_layer(db, payload.name, payload.geometry_family)


@router.delete("/{layer_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_layer(layer_id: int, db: Session = Depends(get_db)):
    with db.begin():
        common.delete_layer(db, layer_id)
    return Response(status_code=204)
