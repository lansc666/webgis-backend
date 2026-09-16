import json
from datetime import datetime, timezone
from typing import Any

from shapely.geometry import shape, mapping
from shapely.validation import explain_validity
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.errors import AppError

MAX_FEATURES_PER_LAYER = 5000

FAMILY_TO_TYPES = {
    "point": {"Point", "MultiPoint"},
    "line": {"LineString", "MultiLineString"},
    "polygon": {"Polygon", "MultiPolygon"},
}


def utc_iso(value) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    if getattr(value, "tzinfo", None) is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def row_to_layer(row) -> dict:
    m = row._mapping
    return {
        "id": m["id"],
        "name": m["name"],
        "geometry_family": m["geometry_family"],
        "created_at": utc_iso(m["created_at"]),
    }


def validate_geometry(geometry: dict, family: str):
    try:
        geom = shape(geometry)
    except Exception as e:
        raise AppError(422, "INVALID_GEOMETRY", "几何格式无效", {"field": "geometry"}) from e

    if geom.is_empty:
        raise AppError(422, "EMPTY_GEOMETRY", "不接受空几何", {"field": "geometry"})

    if geom.geom_type == "GeometryCollection":
        raise AppError(422, "UNSUPPORTED_GEOMETRY", "不支持 GeometryCollection", {"field": "geometry"})

    if geom.geom_type not in FAMILY_TO_TYPES[family]:
        raise AppError(
            422,
            "GEOMETRY_FAMILY_MISMATCH",
            f"几何类型 {geom.geom_type} 与图层类型 {family} 不匹配",
            {"field": "geometry"},
        )

    if getattr(geom, "has_z", False):
        raise AppError(422, "UNSUPPORTED_DIMENSION", "不接受 Z/M 坐标", {"field": "geometry"})

    if not geom.is_valid:
        raise AppError(
            422,
            "INVALID_GEOMETRY",
            "几何无效，请检查面边界",
            {"field": "geometry", "reason": explain_validity(geom)},
        )

    minx, miny, maxx, maxy = geom.bounds
    if minx < -180 or maxx > 180 or miny < -90 or maxy > 90:
        raise AppError(
            422,
            "COORDINATE_OUT_OF_RANGE",
            "坐标超出 EPSG:4326 合法范围",
            {"field": "geometry"},
        )
    return geom


def get_layer(db: Session, layer_id: int):
    row = db.execute(
        text("""
            SELECT id, name, geometry_family, created_at
            FROM layers
            WHERE id = :id
        """),
        {"id": layer_id},
    ).first()
    if not row:
        raise AppError(404, "LAYER_NOT_FOUND", "图层不存在", {"id": layer_id})
    return row


def list_layers(db: Session) -> list[dict]:
    rows = db.execute(
        text("""
            SELECT id, name, geometry_family, created_at
            FROM layers
            ORDER BY id
        """)
    ).all()
    return [row_to_layer(r) for r in rows]


def create_layer(db: Session, name: str, geometry_family: str) -> dict:
    row = db.execute(
        text("""
            INSERT INTO layers (name, geometry_family)
            VALUES (:name, :geometry_family)
            RETURNING id, name, geometry_family, created_at
        """),
        {"name": name, "geometry_family": geometry_family},
    ).one()
    return row_to_layer(row)


def delete_layer(db: Session, layer_id: int):
    result = db.execute(
        text("DELETE FROM layers WHERE id = :id"),
        {"id": layer_id},
    )
    if result.rowcount == 0:
        raise AppError(404, "LAYER_NOT_FOUND", "图层不存在", {"id": layer_id})


def count_features(db: Session, layer_id: int) -> int:
    get_layer(db, layer_id)
    return db.execute(
        text("SELECT COUNT(*) FROM features WHERE layer_id = :layer_id"),
        {"layer_id": layer_id},
    ).scalar_one()


def _feature_row_to_geojson(row) -> dict:
    m = row._mapping
    return {
        "type": "Feature",
        "id": m["id"],
        "layer_id": m["layer_id"],
        "geometry": json.loads(m["geometry"]),
        "properties": m["properties"] or {},
    }


def list_features(db: Session, layer_id: int) -> dict:
    get_layer(db, layer_id)
    rows = db.execute(
        text("""
            SELECT
                id,
                layer_id,
                ST_AsGeoJSON(geom)::text AS geometry,
                properties
            FROM features
            WHERE layer_id = :layer_id
            ORDER BY id
        """),
        {"layer_id": layer_id},
    ).all()
    return {
        "type": "FeatureCollection",
        "features": [_feature_row_to_geojson(r) for r in rows],
    }


def create_feature(
    db: Session,
    *,
    layer_id: int,
    geometry: dict,
    properties: dict[str, Any],
) -> dict:
    layer = get_layer(db, layer_id)
    family = layer._mapping["geometry_family"]

    if count_features(db, layer_id) >= MAX_FEATURES_PER_LAYER:
        raise AppError(
            409,
            "LAYER_FEATURE_LIMIT",
            "单层最多允许 5000 个要素",
            {"layer_id": layer_id},
        )

    geom = validate_geometry(geometry, family)

    row = db.execute(
        text("""
            INSERT INTO features (layer_id, geom, properties)
            VALUES (
                :layer_id,
                ST_SetSRID(ST_GeomFromText(:wkt), 4326),
                CAST(:properties AS jsonb)
            )
            RETURNING
                id,
                layer_id,
                ST_AsGeoJSON(geom)::text AS geometry,
                properties
        """),
        {
            "layer_id": layer_id,
            "wkt": geom.wkt,
            "properties": json.dumps(properties, ensure_ascii=False),
        },
    ).one()
    return _feature_row_to_geojson(row)


def update_feature(
    db: Session,
    feature_id: int,
    *,
    body_id: int,
    layer_id: int,
    geometry: dict,
    properties: dict[str, Any],
) -> dict:
    if feature_id != body_id:
        raise AppError(
            422,
            "FEATURE_ID_MISMATCH",
            "URL id 与 body.id 必须一致",
            {"url_id": feature_id, "body_id": body_id},
        )

    existing = db.execute(
        text("SELECT id, layer_id FROM features WHERE id = :id"),
        {"id": feature_id},
    ).first()
    if not existing:
        raise AppError(404, "FEATURE_NOT_FOUND", "要素不存在", {"id": feature_id})

    old_layer_id = existing._mapping["layer_id"]
    if old_layer_id != layer_id:
        raise AppError(
            422,
            "LAYER_CHANGE_NOT_ALLOWED",
            "PUT 不允许将要素移动到其他图层",
            {"layer_id": layer_id},
        )

    layer = get_layer(db, layer_id)
    geom = validate_geometry(geometry, layer._mapping["geometry_family"])

    row = db.execute(
        text("""
            UPDATE features
            SET
                geom = ST_SetSRID(ST_GeomFromText(:wkt), 4326),
                properties = CAST(:properties AS jsonb),
                updated_at = now()
            WHERE id = :id
            RETURNING
                id,
                layer_id,
                ST_AsGeoJSON(geom)::text AS geometry,
                properties
        """),
        {
            "id": feature_id,
            "wkt": geom.wkt,
            "properties": json.dumps(properties, ensure_ascii=False),
        },
    ).one()
    return _feature_row_to_geojson(row)


def delete_feature(db: Session, feature_id: int):
    result = db.execute(
        text("DELETE FROM features WHERE id = :id"),
        {"id": feature_id},
    )
    if result.rowcount == 0:
        raise AppError(404, "FEATURE_NOT_FOUND", "要素不存在", {"id": feature_id})
