# WebGIS API Contract

## 1. Overview

This document defines the HTTP API contract for the WebGIS backend.

Backend stack:

- FastAPI
- PostgreSQL
- PostGIS
- SQLAlchemy
- GeoPandas
- Shapely
- Fiona

Local development server:

```text
http://127.0.0.1:8000
```

Swagger UI:

```text
http://127.0.0.1:8000/docs
```

OpenAPI schema:

```text
http://127.0.0.1:8000/openapi.json
```

All business APIs use the following prefix:

```text
/api/v1
```

The health check endpoint does not use the `/api/v1` prefix.

---

## 2. General Conventions

### 2.1 JSON

JSON requests use:

```http
Content-Type: application/json
```

JSON responses use:

```http
Content-Type: application/json
```

### 2.2 Character Encoding

All JSON content uses UTF-8.

Shapefile export also uses UTF-8.

### 2.3 Time Format

Timestamps use ISO 8601 in UTC.

Example:

```text
2026-09-16T14:15:06.854171Z
```

### 2.4 Coordinate Reference System

All geometry stored in the database uses:

```text
EPSG:4326
```

GeoJSON coordinate order:

```text
[longitude, latitude]
```

Example:

```json
{
  "type": "Point",
  "coordinates": [116.39, 39.91]
}
```

Valid coordinate ranges:

```text
Longitude: -180 to 180
Latitude:  -90 to 90
```

---

## 3. Geometry Rules

Supported geometry types:

```text
Point
MultiPoint
LineString
MultiLineString
Polygon
MultiPolygon
```

Geometry family mapping:

| geometry_family | Allowed Geometry Types |
|---|---|
| point | Point, MultiPoint |
| line | LineString, MultiLineString |
| polygon | Polygon, MultiPolygon |

The following geometries are rejected:

```text
GeometryCollection
Empty Geometry
Invalid Geometry
Z Geometry
M Geometry
```

All stored geometries must satisfy:

```text
SRID = 4326
2D only
Non-empty
Valid geometry
Compatible with the layer geometry family
```

---

## 4. Feature Properties

The `properties` field must be a flat JSON object.

Supported property value types:

```text
string
number
boolean
null
```

Example:

```json
{
  "name": "East Gate",
  "category": "gate",
  "level": 1,
  "enabled": true,
  "description": null
}
```

Nested objects and arrays are not supported by the current demo contract.

---

# 5. Health API

## GET /health

Checks the backend service and database connection.

### Request

```http
GET /health
```

### Success Response

```http
200 OK
```

```json
{
  "status": "ok",
  "database": "ok"
}
```

### Database Failure

```http
503 Service Unavailable
```

---

# 6. Layer API

A Layer represents a collection of features that belong to the same geometry family.

Layer object:

```json
{
  "id": 1,
  "name": "Campus Facilities",
  "geometry_family": "point",
  "created_at": "2026-09-16T13:48:38.236882Z"
}
```

Fields:

| Field | Type | Description |
|---|---|---|
| id | integer | Globally unique layer ID |
| name | string | Layer name |
| geometry_family | string | point, line, or polygon |
| created_at | datetime | Creation timestamp |

Layer names must contain between 1 and 100 characters.

---

## 6.1 GET /api/v1/layers

Returns all layers.

### Request

```http
GET /api/v1/layers
```

### Success Response

```http
200 OK
```

Example:

```json
[
  {
    "id": 1,
    "name": "Campus Facilities",
    "geometry_family": "point",
    "created_at": "2026-09-16T13:48:38.236882Z"
  }
]
```

If no layers exist:

```json
[]
```

---

## 6.2 POST /api/v1/layers

Creates a new layer.

### Request

```http
POST /api/v1/layers
Content-Type: application/json
```

Body:

```json
{
  "name": "Campus Facilities",
  "geometry_family": "point"
}
```

Allowed values for `geometry_family`:

```text
point
line
polygon
```

### Success Response

```http
201 Created
```

```json
{
  "id": 1,
  "name": "Campus Facilities",
  "geometry_family": "point",
  "created_at": "2026-09-16T13:48:38.236882Z"
}
```

---

## 6.3 DELETE /api/v1/layers/{layer_id}

Deletes a layer.

All features belonging to the layer are automatically deleted through cascade deletion.

### Example

```http
DELETE /api/v1/layers/1
```

### Success Response

```http
204 No Content
```

### Layer Not Found

```http
404 Not Found
```

---

# 7. Feature Object

Features follow the GeoJSON Feature structure.

Example:

```json
{
  "type": "Feature",
  "id": 1,
  "layer_id": 1,
  "geometry": {
    "type": "Point",
    "coordinates": [116.39, 39.91]
  },
  "properties": {
    "name": "East Gate",
    "category": "gate"
  }
}
```

Fields:

| Field | Type | Description |
|---|---|---|
| type | string | Always `Feature` |
| id | integer | Globally unique feature ID |
| layer_id | integer | Parent layer ID |
| geometry | GeoJSON Geometry | Spatial geometry |
| properties | object | Business attributes |

---

# 8. Feature API

## 8.1 GET /api/v1/features

Returns all features belonging to a specified layer.

### Query Parameters

| Parameter | Type | Required |
|---|---|---|
| layer_id | integer | Yes |

### Example

```http
GET /api/v1/features?layer_id=1
```

### Success Response

```http
200 OK
```

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": 1,
      "layer_id": 1,
      "geometry": {
        "type": "Point",
        "coordinates": [116.39, 39.91]
      },
      "properties": {
        "name": "East Gate",
        "category": "gate"
      }
    }
  ]
}
```

The current demo supports a maximum of:

```text
5000 features
```

per layer response.

---

## 8.2 POST /api/v1/features

Creates a new feature.

The client must not provide a new feature ID.

### Request

```http
POST /api/v1/features
Content-Type: application/json
```

Point example:

```json
{
  "type": "Feature",
  "layer_id": 1,
  "geometry": {
    "type": "Point",
    "coordinates": [116.39, 39.91]
  },
  "properties": {
    "name": "East Gate",
    "category": "gate"
  }
}
```

LineString example:

```json
{
  "type": "Feature",
  "layer_id": 2,
  "geometry": {
    "type": "LineString",
    "coordinates": [
      [116.39, 39.91],
      [116.40, 39.92]
    ]
  },
  "properties": {
    "name": "Main Road"
  }
}
```

Polygon example:

```json
{
  "type": "Feature",
  "layer_id": 3,
  "geometry": {
    "type": "Polygon",
    "coordinates": [
      [
        [116.39, 39.91],
        [116.40, 39.91],
        [116.40, 39.92],
        [116.39, 39.92],
        [116.39, 39.91]
      ]
    ]
  },
  "properties": {
    "name": "Teaching Area"
  }
}
```

### Success Response

```http
201 Created
```

---

## 8.3 PUT /api/v1/features/{feature_id}

Fully replaces an existing feature.

`properties` uses replacement semantics rather than merge semantics.

The request ID and layer ID must remain consistent with the existing feature.

### Example

```http
PUT /api/v1/features/1
```

```json
{
  "type": "Feature",
  "id": 1,
  "layer_id": 1,
  "geometry": {
    "type": "Point",
    "coordinates": [116.40, 39.92]
  },
  "properties": {
    "name": "New East Gate",
    "category": "gate"
  }
}
```

### Success Response

```http
200 OK
```

### Feature Not Found

```http
404 Not Found
```

---

## 8.4 DELETE /api/v1/features/{feature_id}

Deletes a feature.

### Example

```http
DELETE /api/v1/features/1
```

### Success Response

```http
204 No Content
```

### Feature Not Found

```http
404 Not Found
```

---

# 9. Shapefile Import API

## POST /api/v1/imports/shapefile

Imports a ZIP archive containing one Shapefile dataset.

### Request Type

```text
multipart/form-data
```

The upload field name must be:

```text
file
```

### Example

```text
file = campus_points.zip
```

---

## 9.1 File Size Limits

Maximum ZIP upload size:

```text
20 MiB
```

Maximum total extracted size:

```text
100 MiB
```

Maximum number of features:

```text
5000
```

---

## 9.2 Required Shapefile Components

The ZIP archive must contain exactly one Shapefile dataset with matching base names.

Required files:

```text
.shp
.shx
.dbf
.prj
```

Example:

```text
campus_points.shp
campus_points.shx
campus_points.dbf
campus_points.prj
```

Optional files may include:

```text
.cpg
Shapefile index files
field_mapping.json
```

---

## 9.3 Invalid ZIP Structures

The following cases must be rejected:

```text
Missing required Shapefile components
Multiple Shapefile datasets
Nested ZIP files
Absolute paths
../ path traversal
Unsafe archive paths
```

---

## 9.4 CRS Handling

The source CRS must be determined from the `.prj` file.

The backend must not guess the CRS.

All imported geometries are converted to:

```text
EPSG:4326
```

before being stored in PostGIS.

For example:

```text
EPSG:3857
    ↓
EPSG:4326
```

If the CRS cannot be determined, the import must fail.

---

## 9.5 Character Encoding

Encoding should be determined using the `.cpg` file when available.

If `.cpg` is unavailable, DBF metadata may be used.

If the encoding cannot be determined reliably, the import should fail instead of silently producing corrupted text.

---

## 9.6 Geometry Validation

Imported geometries must follow the geometry rules defined in this document.

Supported:

```text
Point
MultiPoint
LineString
MultiLineString
Polygon
MultiPolygon
```

Rejected:

```text
GeometryCollection
Empty Geometry
Invalid Geometry
Z Geometry
M Geometry
```

---

## 9.7 Automatic Layer Creation

A successful import automatically creates a new layer.

The layer name is derived from the Shapefile base filename.

Example:

```text
campus_points.shp
```

creates a layer similar to:

```json
{
  "name": "campus_points",
  "geometry_family": "point"
}
```

The geometry family is determined from the imported Shapefile geometry.

---

## 9.8 Transaction Behavior

A Shapefile import must be processed as a single database transaction.

If any feature fails validation or insertion:

```text
the entire import must be rolled back
```

The database must not contain:

```text
a partially imported layer
partially imported features
```

---

## 9.9 Success Response

```http
201 Created
```

Example:

```json
{
  "layer": {
    "id": 2,
    "name": "campus_points",
    "geometry_family": "point",
    "created_at": "2026-09-16T14:15:06.854171Z"
  },
  "imported_count": 3,
  "warnings": []
}
```

Fields:

| Field | Type | Description |
|---|---|---|
| layer | object | Newly created layer |
| imported_count | integer | Number of imported features |
| warnings | array | Non-fatal import warnings |

---

# 10. Shapefile Export API

## GET /api/v1/layers/{layer_id}/export

Exports all features in a layer as a Shapefile ZIP archive.

### Query Parameter

```text
format=shp
```

### Example

```http
GET /api/v1/layers/2/export?format=shp
```

### Success Response

```http
200 OK
```

Response Content-Type:

```http
application/zip
```

Response header example:

```http
Content-Disposition: attachment; filename="layer_2.zip"
```

---

## 10.1 Exported ZIP Contents

The ZIP archive must contain at least:

```text
layer_2.shp
layer_2.shx
layer_2.dbf
layer_2.prj
layer_2.cpg
field_mapping.json
```

ZIP filename format:

```text
layer_{id}.zip
```

---

## 10.2 Export CRS

All exported Shapefiles use:

```text
EPSG:4326
```

---

## 10.3 Export Encoding

Exported DBF text uses:

```text
UTF-8
```

A `.cpg` file must be included.

---

# 11. DBF Field Mapping

DBF field names have length and character limitations.

Business property names may contain:

```text
long names
Unicode characters
characters unsupported by DBF field names
```

Therefore, business property names are mapped to stable ASCII field names during export.

Example:

```text
f0001
f0002
f0003
```

Business keys should be mapped in a stable sorted order.

Example source properties:

```json
{
  "category": "gate",
  "is_public": true,
  "name": "East Gate"
}
```

Possible DBF fields:

```text
f0001
f0002
f0003
```

---

## 11.1 field_mapping.json

The ZIP must contain:

```text
field_mapping.json
```

Mapping version:

```text
1
```

Example:

```json
{
  "version": 1,
  "fields": {
    "f0001": {
      "name": "category"
    },
    "f0002": {
      "name": "is_public"
    },
    "f0003": {
      "name": "name"
    }
  }
}
```

---

## 11.2 Re-import Behavior

When a ZIP exported by this system is imported again, the backend should read `field_mapping.json` and restore the original business property names.

For example:

```text
f0001
```

should be restored to:

```text
category
```

The API response should expose the original property names instead of internal DBF field aliases.

---

## 11.3 Boolean Values

Boolean values must be exported in a way that allows them to be restored after re-import.

The following values must remain distinguishable:

```text
true
false
```

---

## 11.4 String Length

A DBF string value must not exceed:

```text
254 UTF-8 bytes
```

Values exceeding the supported size must not be silently truncated.

The export should fail with an appropriate error instead.

---

## 11.5 Numeric Values

Numeric export must use an appropriate precision and scale.

The backend should avoid silent numeric precision loss.

---

# 12. Shapefile Round Trip

The backend must support the following workflow:

```text
Input Shapefile ZIP
        ↓
Import
        ↓
PostGIS
        ↓
Export Shapefile ZIP
        ↓
Open in QGIS
        ↓
Re-import
```

After a round trip, the following data should remain equivalent:

```text
Feature count
Geometry
Normalized properties
```

Example:

Original:

```json
{
  "name": "East Gate",
  "category": "gate"
}
```

After export and re-import:

```json
{
  "name": "East Gate",
  "category": "gate"
}
```

The result should not expose DBF aliases such as:

```json
{
  "f0001": "gate",
  "f0002": "East Gate"
}
```

---

# 13. Unified Error Response

Business errors use the following structure:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": {}
  }
}
```

Fields:

| Field | Type | Description |
|---|---|---|
| error.code | string | Stable machine-readable error code |
| error.message | string | Human-readable error message |
| error.details | object or null | Additional error information |

Example:

```json
{
  "error": {
    "code": "LAYER_NOT_FOUND",
    "message": "Layer not found",
    "details": {
      "layer_id": 999
    }
  }
}
```

Geometry error example:

```json
{
  "error": {
    "code": "INVALID_GEOMETRY",
    "message": "Geometry is invalid",
    "details": {}
  }
}
```

Shapefile error example:

```json
{
  "error": {
    "code": "INVALID_SHAPEFILE",
    "message": "Required .prj file is missing",
    "details": {}
  }
}
```

---

# 14. HTTP Status Codes

| Status | Meaning |
|---|---|
| 200 OK | Successful GET or PUT |
| 201 Created | Resource creation or Shapefile import succeeded |
| 204 No Content | Successful DELETE |
| 400 Bad Request | Business validation failure |
| 404 Not Found | Layer or Feature not found |
| 422 Unprocessable Entity | Request schema validation failure |
| 503 Service Unavailable | Database or required service unavailable |

---

# 15. Database Model

## 15.1 layers

Main fields:

```text
id
name
geometry_family
created_at
```

Important constraints:

```text
id > 0
name length = 1 to 100
geometry_family in point, line, polygon
```

---

## 15.2 features

Main fields:

```text
id
layer_id
geom
properties
created_at
updated_at
```

Geometry column:

```text
geometry(Geometry, 4326)
```

Properties column:

```text
JSONB
```

---

## 15.3 Geometry Database Constraints

Stored geometry must satisfy:

```text
ST_SRID(geom) = 4326
ST_NDims(geom) = 2
NOT ST_IsEmpty(geom)
ST_IsValid(geom)
```

The geometry type must also match the parent layer geometry family.

---

## 15.4 Indexes

The geometry column uses a:

```text
GiST
```

spatial index.

`layer_id` also uses a normal database index.

---

## 15.5 Cascade Delete

Deleting a layer automatically deletes all features belonging to that layer.

The relationship uses:

```text
ON DELETE CASCADE
```

---

# 16. Demo Limits

The current backend is designed for the WebGIS demo environment.

Current limits include:

```text
Maximum uploaded ZIP size: 20 MiB
Maximum extracted ZIP size: 100 MiB
Maximum Shapefile feature count: 5000
Maximum feature list size: 5000
```

These values are part of the current demo contract and may be changed in future production versions.

---

# 17. Verification Checklist

Before merging backend changes, verify:

```text
GET /health works
Database connection works
Layer creation works
Layer deletion works
Feature creation works
Feature update works
Feature deletion works
Point works
LineString works
Polygon works
MultiPoint works
MultiLineString works
MultiPolygon works
Shapefile import works
EPSG:3857 input converts to EPSG:4326
UTF-8 attributes remain valid
Shapefile export works
Exported ZIP opens in QGIS
Exported ZIP can be re-imported
field_mapping.json restores property names
Invalid geometry is rejected
Missing .prj is rejected
Failed imports are fully rolled back
pytest passes
```

---

# 18. Running Automated Tests

From the project root:

```powershell
.venv\Scripts\python.exe -m pytest -v
```

All tests should pass before creating a Pull Request.