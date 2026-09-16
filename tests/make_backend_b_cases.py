from pathlib import Path
import shutil
import zipfile

import geopandas as gpd
from shapely.geometry import (
    Point,
    MultiPoint,
    MultiLineString,
    MultiPolygon,
    Polygon,
)


ROOT = Path("backend_b_cases")

if ROOT.exists():
    shutil.rmtree(ROOT)

ROOT.mkdir()


def make_zip(name, gdf, remove_prj=False):
    folder = ROOT / name
    folder.mkdir()

    shp_path = folder / f"{name}.shp"

    gdf.to_file(
        shp_path,
        driver="ESRI Shapefile",
        encoding="UTF-8",
        index=False,
    )

    cpg = folder / f"{name}.cpg"
    cpg.write_text("UTF-8", encoding="ascii")

    if remove_prj:
        prj = folder / f"{name}.prj"
        if prj.exists():
            prj.unlink()

    zip_path = ROOT / f"{name}.zip"

    with zipfile.ZipFile(
        zip_path,
        "w",
        zipfile.ZIP_DEFLATED
    ) as zf:
        for file in folder.iterdir():
            zf.write(file, file.name)

    print(f"Created: {zip_path}")


# 1. EPSG:3857：验证 CRS 自动转换到 EPSG:4326
gdf_3857 = gpd.GeoDataFrame(
    {
        "name": ["东门", "教学楼"],
        "category": ["gate", "building"],
    },
    geometry=[
        Point(116.39, 39.91),
        Point(116.40, 39.92),
    ],
    crs="EPSG:4326",
).to_crs("EPSG:3857")

make_zip("crs_3857", gdf_3857)


# 2. MultiPoint
gdf_multipoint = gpd.GeoDataFrame(
    {"name": ["多点设施"]},
    geometry=[
        MultiPoint([
            (116.39, 39.91),
            (116.40, 39.92),
        ])
    ],
    crs="EPSG:4326",
)

make_zip("multi_point", gdf_multipoint)


# 3. MultiLineString
gdf_multiline = gpd.GeoDataFrame(
    {"name": ["校园道路组"]},
    geometry=[
        MultiLineString([
            [
                (116.39, 39.91),
                (116.40, 39.92),
            ],
            [
                (116.40, 39.92),
                (116.41, 39.915),
            ],
        ])
    ],
    crs="EPSG:4326",
)

make_zip("multi_line", gdf_multiline)


# 4. MultiPolygon
polygon1 = Polygon([
    (116.39, 39.91),
    (116.395, 39.91),
    (116.395, 39.915),
    (116.39, 39.915),
    (116.39, 39.91),
])

polygon2 = Polygon([
    (116.40, 39.92),
    (116.405, 39.92),
    (116.405, 39.925),
    (116.40, 39.925),
    (116.40, 39.92),
])

gdf_multipolygon = gpd.GeoDataFrame(
    {"name": ["校园区域组"]},
    geometry=[
        MultiPolygon([polygon1, polygon2])
    ],
    crs="EPSG:4326",
)

make_zip("multi_polygon", gdf_multipolygon)


# 5. 缺少 .prj：应该导入失败
gdf_missing_prj = gpd.GeoDataFrame(
    {"name": ["无坐标系测试"]},
    geometry=[Point(116.39, 39.91)],
    crs="EPSG:4326",
)

make_zip(
    "missing_prj",
    gdf_missing_prj,
    remove_prj=True,
)


# 6. 非法 Polygon：验证事务整体回滚
valid_polygon = Polygon([
    (116.39, 39.91),
    (116.40, 39.91),
    (116.40, 39.92),
    (116.39, 39.92),
    (116.39, 39.91),
])

invalid_polygon = Polygon([
    (116.41, 39.91),
    (116.42, 39.92),
    (116.41, 39.92),
    (116.42, 39.91),
    (116.41, 39.91),
])

gdf_rollback = gpd.GeoDataFrame(
    {
        "name": [
            "合法区域",
            "非法区域",
        ]
    },
    geometry=[
        valid_polygon,
        invalid_polygon,
    ],
    crs="EPSG:4326",
)

make_zip("rollback_invalid", gdf_rollback)


# 7. Z 坐标：后端应该拒绝三维几何
gdf_z = gpd.GeoDataFrame(
    {"name": ["三维点"]},
    geometry=[
        Point(116.39, 39.91, 100)
    ],
    crs="EPSG:4326",
)

make_zip("point_z", gdf_z)


print()
print("All Backend B test files created.")