from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


GeometryFamily = Literal["point", "line", "polygon"]


class LayerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    geometry_family: GeometryFamily


class LayerOut(BaseModel):
    id: int
    name: str
    geometry_family: GeometryFamily
    created_at: str


class GeoJSONGeometry(BaseModel):
    type: str
    coordinates: Any


class FeatureIn(BaseModel):
    type: Literal["Feature"] = "Feature"
    id: int | None = None
    layer_id: int
    geometry: GeoJSONGeometry
    properties: dict[str, Any] = Field(default_factory=dict)

    @field_validator("properties")
    @classmethod
    def validate_properties(cls, value: dict[str, Any]):
        for key, item in value.items():
            if not isinstance(key, str) or not key:
                raise ValueError("属性字段名必须为非空字符串")
            if isinstance(item, (dict, list, tuple, set)):
                raise ValueError("属性值不接受嵌套对象或数组")
            if not (
                item is None
                or isinstance(item, (str, bool, int, float))
            ):
                raise ValueError(f"属性 {key} 的类型不受支持")
            if isinstance(item, float) and (item != item or item in (float("inf"), float("-inf"))):
                raise ValueError(f"属性 {key} 必须为有限数值")
        return value
