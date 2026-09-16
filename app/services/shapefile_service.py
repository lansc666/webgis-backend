import json
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import geopandas as gpd
from shapely.geometry import mapping
from sqlalchemy.orm import Session

from app.errors import AppError
from app.services.common import create_feature, create_layer, get_layer, list_features

MAX_ZIP_BYTES = 20 * 1024 * 1024
MAX_UNZIPPED_BYTES = 100 * 1024 * 1024
MAX_FEATURES = 5000
REQUIRED_EXTS = {".shp", ".shx", ".dbf", ".prj"}
OPTIONAL_EXTS = {".cpg", ".qix", ".sbn", ".sbx", ".shp.xml", ".fix"}

FAMILY_BY_GEOM = {
    "Point": "point",
    "MultiPoint": "point",
    "LineString": "line",
    "MultiLineString": "line",
    "Polygon": "polygon",
    "MultiPolygon": "polygon",
}


def _safe_members(zf: zipfile.ZipFile):
    total = 0
    for info in zf.infolist():
        name = info.filename.replace("\\", "/")
        path = Path(name)

        if path.is_absolute() or ".." in path.parts:
            raise AppError(400, "INVALID_ZIP_PATH", "ZIP 中包含非法路径", {"name": name})
        if name.lower().endswith(".zip"):
            raise AppError(400, "NESTED_ZIP", "ZIP 中不允许嵌套 ZIP", {"name": name})

        total += info.file_size
        if total > MAX_UNZIPPED_BYTES:
            raise AppError(413, "UNZIPPED_TOO_LARGE", "ZIP 解压后总量超过 100 MiB", {})
        yield info


def _find_single_shapefile(folder: Path) -> Path:
    shp_files = list(folder.rglob("*.shp"))
    if len(shp_files) != 1:
        raise AppError(
            400,
            "INVALID_SHAPEFILE_COUNT",
            "ZIP 中必须且只能包含一组 Shapefile",
            {"count": len(shp_files)},
        )
    shp = shp_files[0]
    base = shp.with_suffix("")
    for ext in REQUIRED_EXTS:
        candidate = Path(str(base) + ext)
        if not candidate.exists():
            raise AppError(
                400,
                "MISSING_SHAPEFILE_PART",
                f"缺少必需文件 {candidate.name}",
                {"extension": ext},
            )
    return shp


def _validate_mapping(path: Path, columns: list[str]) -> dict[str, dict[str, Any]] | None:
    if not path.exists():
        return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise AppError(400, "INVALID_FIELD_MAPPING", "field_mapping.json 无法解析", {}) from e

    if data.get("version") != 1 or not isinstance(data.get("fields"), list):
        raise AppError(400, "INVALID_FIELD_MAPPING", "field_mapping.json 格式无效", {})

    result = {}
    seen_names = set()
    for item in data["fields"]:
        dbf = item.get("dbf")
        name = item.get("name")
        typ = item.get("type")
        if dbf not in columns or typ not in {"string", "number", "boolean"}:
            raise AppError(400, "INVALID_FIELD_MAPPING", "字段映射与 DBF 不一致", {"field": dbf})
        if not isinstance(name, str) or not name or name in seen_names:
            raise AppError(400, "INVALID_FIELD_MAPPING", "字段映射名称无效或重复", {"name": name})
        seen_names.add(name)
        result[dbf] = {"name": name, "type": typ}
    return result


def _normalize_value(value):
    if value is None:
        return None
    try:
        if value != value:  # NaN
            return None
    except Exception:
        pass
    if hasattr(value, "item"):
        value = value.item()
    if hasattr(value, "isoformat") and not isinstance(value, str):
        try:
            return value.isoformat()
        except Exception:
            pass
    return value


def import_shapefile_zip(db: Session, upload_bytes: bytes, original_name: str) -> dict:
    if len(upload_bytes) > MAX_ZIP_BYTES:
        raise AppError(413, "FILE_TOO_LARGE", "上传文件超过 20 MiB", {})

    with tempfile.TemporaryDirectory(prefix="webgis_import_") as td:
        root = Path(td)
        zip_path = root / "upload.zip"
        zip_path.write_bytes(upload_bytes)

        try:
            with zipfile.ZipFile(zip_path) as zf:
                for info in _safe_members(zf):
                    zf.extract(info, root / "unzipped")
        except zipfile.BadZipFile as e:
            raise AppError(400, "INVALID_ZIP", "上传文件不是有效 ZIP", {}) from e

        shp = _find_single_shapefile(root / "unzipped")

        try:
            gdf = gpd.read_file(shp)
        except Exception as e:
            raise AppError(400, "SHAPEFILE_READ_ERROR", "Shapefile 无法读取", {}) from e

        if gdf.crs is None:
            raise AppError(400, "CRS_REQUIRED", "Shapefile 缺少可识别 CRS", {})

        if len(gdf) > MAX_FEATURES:
            raise AppError(413, "FEATURE_LIMIT_EXCEEDED", "单包最多 5000 个要素", {"count": len(gdf)})
        if len(gdf) == 0:
            raise AppError(422, "EMPTY_LAYER", "不接受空 Shapefile 导入", {})

        try:
            gdf = gdf.to_crs(epsg=4326)
        except Exception as e:
            raise AppError(400, "CRS_UNSUPPORTED", "原始 CRS 无法转换为 EPSG:4326", {}) from e

        geom_types = set(gdf.geometry.geom_type.dropna().tolist())
        families = {FAMILY_BY_GEOM.get(t) for t in geom_types}
        if None in families or len(families) != 1:
            raise AppError(
                422,
                "MIXED_OR_UNSUPPORTED_GEOMETRY",
                "Shapefile 几何类型混合或不受支持",
                {"types": sorted(geom_types)},
            )
        family = next(iter(families))

        field_mapping = _validate_mapping(
            shp.with_name("field_mapping.json"),
            [c for c in gdf.columns if c != gdf.geometry.name],
        )

        layer_name = shp.stem[:100]
        layer = create_layer(db, layer_name, family)
        warnings: list[str] = []

        prop_columns = [c for c in gdf.columns if c != gdf.geometry.name]

        for _, row in gdf.iterrows():
            geom = row[gdf.geometry.name]
            if geom is None or geom.is_empty:
                raise AppError(422, "EMPTY_GEOMETRY", "导入要素包含空几何", {})

            props = {}
            for col in prop_columns:
                value = _normalize_value(row[col])
                out_name = col
                if field_mapping and col in field_mapping:
                    meta = field_mapping[col]
                    out_name = meta["name"]
                    if meta["type"] == "boolean" and value is not None:
                        if isinstance(value, str):
                            low = value.lower()
                            if low not in {"true", "false"}:
                                raise AppError(422, "FIELD_TYPE_MISMATCH", "布尔字段值无效", {"field": col})
                            value = low == "true"
                        else:
                            value = bool(value)
                props[out_name] = value

            create_feature(
                db,
                layer_id=layer["id"],
                geometry=mapping(geom),
                properties=props,
            )

        return {
            "layer": layer,
            "imported_count": len(gdf),
            "warnings": warnings,
        }


def _infer_column_type(values):
    actual = [v for v in values if v is not None]
    if not actual:
        return "string"
    if all(isinstance(v, bool) for v in actual):
        return "boolean"
    if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in actual):
        return "number"
    if all(isinstance(v, str) for v in actual):
        return "string"
    raise AppError(422, "MIXED_FIELD_TYPES", "同一属性字段存在不兼容类型", {})


def export_layer_to_zip(db: Session, layer_id: int) -> tuple[Path, str]:
    layer = get_layer(db, layer_id)
    collection = list_features(db, layer_id)
    feats = collection["features"]

    if not feats:
        raise AppError(422, "EMPTY_LAYER", "空图层不能导出 Shapefile", {"layer_id": layer_id})

    business_fields = sorted({
        key
        for f in feats
        for key in (f.get("properties") or {}).keys()
    })

    field_meta = {}
    for idx, name in enumerate(business_fields, start=1):
        dbf = f"f{idx:04d}"
        values = [(f.get("properties") or {}).get(name) for f in feats]
        typ = _infer_column_type(values)
        field_meta[name] = {"dbf": dbf, "type": typ}

    records = []
    geoms = []
    for f in feats:
        props = f.get("properties") or {}
        rec = {}
        for name in business_fields:
            meta = field_meta[name]
            value = props.get(name)
            if isinstance(value, str) and len(value.encode("utf-8")) > 254:
                raise AppError(
                    422,
                    "TEXT_TOO_LONG",
                    "字符串超过 Shapefile DBF 可安全保存的 254 字节",
                    {"field": name},
                )
            if meta["type"] == "boolean" and value is not None:
                value = "true" if value else "false"
            rec[meta["dbf"]] = value
        records.append(rec)
        from shapely.geometry import shape
        geoms.append(shape(f["geometry"]))

    gdf = gpd.GeoDataFrame(records, geometry=geoms, crs="EPSG:4326")

    tmpdir = Path(tempfile.mkdtemp(prefix="webgis_export_"))
    stem = f"layer_{layer_id}"
    shp_path = tmpdir / f"{stem}.shp"

    try:
        gdf.to_file(shp_path, driver="ESRI Shapefile", encoding="UTF-8")
    except Exception as e:
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise AppError(500, "SHAPEFILE_EXPORT_ERROR", "Shapefile 导出失败", {}) from e

    (tmpdir / f"{stem}.cpg").write_text("UTF-8", encoding="ascii")

    mapping_payload = {
        "version": 1,
        "fields": [
            {"dbf": field_meta[name]["dbf"], "name": name, "type": field_meta[name]["type"]}
            for name in business_fields
        ],
    }
    (tmpdir / "field_mapping.json").write_text(
        json.dumps(mapping_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    zip_path = tmpdir / f"{stem}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in tmpdir.iterdir():
            if p == zip_path:
                continue
            if p.suffix.lower() in {".shp", ".shx", ".dbf", ".prj", ".cpg"} or p.name == "field_mapping.json":
                zf.write(p, p.name)

    return zip_path, f"{stem}.zip"
