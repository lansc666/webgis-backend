# webgis-backend

Siyu Wu & Hongzhen Chen

# WebGIS Backend

WebGIS 后端服务，基于 FastAPI + PostgreSQL + PostGIS。

当前主要功能：

- Layer 图层管理
- Feature 空间要素增删改查
- GeoJSON 几何数据持久化
- Shapefile ZIP 导入
- Shapefile ZIP 导出
- CRS 自动转换为 EPSG:4326
- PostGIS 空间数据存储
- 统一错误响应

## 1. 技术环境

推荐环境：

- Python 3.11
- PostgreSQL 18
- PostGIS 3.6
- FastAPI
- SQLAlchemy
- GeoPandas
- Shapely
- Fiona
- psycopg2

## 2. 项目结构

```text
webgis-backend/
├── app/
│   ├── main.py
│   ├── db.py
│   ├── errors.py
│   ├── schemas.py
│   ├── routers/
│   └── services/
├── sql/
│   └── init.sql
├── tests/
├── docs/
│   └── api-contract.md
├── .env.example
├── requirements.txt
└── README.md