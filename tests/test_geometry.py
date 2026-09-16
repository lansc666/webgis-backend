import pytest

from app.errors import AppError
from app.services.common import validate_geometry


def test_valid_point():
    geom = {"type": "Point", "coordinates": [116.39, 39.91]}
    result = validate_geometry(geom, "point")
    assert result.geom_type == "Point"


def test_reject_out_of_range():
    with pytest.raises(AppError) as e:
        validate_geometry(
            {"type": "Point", "coordinates": [200, 39.91]},
            "point",
        )
    assert e.value.code == "COORDINATE_OUT_OF_RANGE"


def test_reject_family_mismatch():
    with pytest.raises(AppError) as e:
        validate_geometry(
            {"type": "LineString", "coordinates": [[116, 39], [117, 40]]},
            "point",
        )
    assert e.value.code == "GEOMETRY_FAMILY_MISMATCH"
