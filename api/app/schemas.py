from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from rentmodel.projection import FIRST_FORECAST, LAST_FORECAST, quarter_index


class PredictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    suburb: str = Field(min_length=2, max_length=80)
    property_type: str = Field(min_length=2, max_length=60)
    bedrooms: int = Field(ge=0, le=10)
    bathrooms: int = Field(ge=0, le=10)
    carspaces: int = Field(ge=0, le=10)
    amenities: list[str] = Field(default_factory=list, max_length=20)
    target_date: Optional[str] = Field(default=None, pattern=r"^\d{4}Q[1-4]$",
                                       description=f"Quarter between {FIRST_FORECAST} and {LAST_FORECAST}")

    @field_validator("target_date")
    @classmethod
    def _quarter_range(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not quarter_index(FIRST_FORECAST) <= quarter_index(v) <= quarter_index(LAST_FORECAST):
            raise ValueError(f"target_date must be between {FIRST_FORECAST} and {LAST_FORECAST}")
        return v


class Warning_(BaseModel):
    code: str
    message: str


class ProjectionPoint(BaseModel):
    quarter: str
    point: float
    lower: float
    upper: float
    growth_factor: float


class SuburbMatch(BaseModel):
    input: str
    listing_suburb: Optional[str]
    seen_in_training: bool
    arima_suburb: Optional[str]


class PredictResponse(BaseModel):
    point: float
    lower: float
    upper: float
    interval_level: float
    price_level: str
    suburb: SuburbMatch
    target_date: Optional[str]
    at_target: Optional[ProjectionPoint]
    projection: Optional[list[ProjectionPoint]]
    warnings: list[Warning_]
