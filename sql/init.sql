CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS layers (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(100) NOT NULL CHECK (char_length(name) BETWEEN 1 AND 100),
    geometry_family VARCHAR(10) NOT NULL CHECK (geometry_family IN ('point', 'line', 'polygon')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS features (
    id          SERIAL PRIMARY KEY,
    layer_id    INTEGER NOT NULL REFERENCES layers(id) ON DELETE CASCADE,
    geom        geometry(Geometry, 4326) NOT NULL,
    properties  JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT features_geom_srid CHECK (ST_SRID(geom) = 4326),
    CONSTRAINT features_geom_2d CHECK (ST_NDims(geom) = 2),
    CONSTRAINT features_geom_valid CHECK (ST_IsValid(geom)),
    CONSTRAINT features_geom_not_empty CHECK (NOT ST_IsEmpty(geom)),
    CONSTRAINT features_no_geometrycollection CHECK (GeometryType(geom) <> 'GEOMETRYCOLLECTION')
);

CREATE INDEX IF NOT EXISTS idx_features_geom_gist
    ON features USING GIST (geom);

CREATE INDEX IF NOT EXISTS idx_features_layer_id
    ON features (layer_id);

CREATE OR REPLACE FUNCTION enforce_geometry_family()
RETURNS trigger AS $$
DECLARE
    fam text;
    gtype text;
BEGIN
    SELECT geometry_family INTO fam
    FROM layers
    WHERE id = NEW.layer_id;

    IF fam IS NULL THEN
        RAISE EXCEPTION 'layer % not found', NEW.layer_id;
    END IF;

    gtype := GeometryType(NEW.geom);

    IF fam = 'point' AND gtype NOT IN ('POINT', 'MULTIPOINT') THEN
        RAISE EXCEPTION 'geometry family mismatch';
    ELSIF fam = 'line' AND gtype NOT IN ('LINESTRING', 'MULTILINESTRING') THEN
        RAISE EXCEPTION 'geometry family mismatch';
    ELSIF fam = 'polygon' AND gtype NOT IN ('POLYGON', 'MULTIPOLYGON') THEN
        RAISE EXCEPTION 'geometry family mismatch';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_features_geometry_family ON features;

CREATE TRIGGER trg_features_geometry_family
BEFORE INSERT OR UPDATE OF geom, layer_id ON features
FOR EACH ROW
EXECUTE FUNCTION enforce_geometry_family();
