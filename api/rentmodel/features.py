"""Feature engineering for the reduced (user-fillable) XGBoost rent model.

The same ``build_features`` function turns either raw listing rows (training) or
a single API request (serving) into the model matrix, so there is one source of
truth for column order, dtypes and categorical encodings.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd
from pandas.api.types import CategoricalDtype

TARGET = "weekly_rent"
DATE_COL = "date_listed"
CATEGORICAL = ["suburb", "property_type"]
USER_NUMERIC = ["bedrooms", "bathrooms", "carspaces"]

# Suburb-level context filled from a per-suburb lookup built on the training set.
BASE_LOOKUP_FEATURES = [
    "dist_to_cbd_km_driving",
    "median_weekly_income",
    "crime_rate",
    "population",
    "lat",
    "lon",
]
# Candidate extra distance features; training keeps them only if CV says they help.
EXTRA_LOOKUP_CANDIDATES = [
    "beaches_road_distance_m",
    "train_stations_PTV_road_distance_m",
    "park_national_road_distance_m",
]
# Amenities a visitor can sensibly tick on a form. Training ranks these by SHAP
# on the training set and keeps the top ones.
AMENITY_CANDIDATES = [
    "feat_dishwasher",
    "feat_furnished",
    "feat_air_conditioning",
    "feat_built_in_wardrobes",
    "feat_balcony___deck",
    "feat_study",
    "feat_pets_allowed",
    "feat_secure_parking",
    "feat_gas_heating",
    "feat_ensuite",
    "feat_swimming_pool",
    "feat_gym",
    "feat_city_views",
    "feat_internal_laundry",
    "feat_floorboards",
    "feat_garden___courtyard",
    "feat_ducted_heating",
    "feat_remote_garage",
]

GLOBAL_KEY = "__global__"


def normalise_listing_suburb(name: str | None) -> str:
    """Listing suburbs are stored upper-case with single spaces."""
    if name is None:
        return ""
    return re.sub(r"\s+", " ", str(name)).strip().upper()


def amenity_label(col: str) -> str:
    """``feat_balcony___deck`` -> ``Balcony / deck``."""
    text = col.removeprefix("feat_").replace("___", " / ").replace("_", " ")
    return text[:1].upper() + text[1:]


@dataclass
class FeatureSpec:
    suburb_categories: list[str]
    property_type_categories: list[str]
    amenities: list[str]
    lookup_features: list[str]
    feature_order: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.feature_order:
            self.feature_order = (
                CATEGORICAL + USER_NUMERIC + self.amenities + self.lookup_features
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "suburb_categories": self.suburb_categories,
            "property_type_categories": self.property_type_categories,
            "amenities": self.amenities,
            "lookup_features": self.lookup_features,
            "feature_order": self.feature_order,
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "FeatureSpec":
        return cls(
            suburb_categories=list(d["suburb_categories"]),
            property_type_categories=list(d["property_type_categories"]),
            amenities=list(d["amenities"]),
            lookup_features=list(d["lookup_features"]),
            feature_order=list(d["feature_order"]),
        )


def build_suburb_lookup(train_df: pd.DataFrame, columns: Iterable[str]) -> dict[str, Any]:
    """Per-suburb medians of context features, from TRAINING rows only.

    Also stores sensible form defaults per suburb and a global fallback used for
    suburbs never seen in training.
    """
    columns = list(columns)
    d = train_df.copy()
    d["suburb"] = d["suburb"].map(normalise_listing_suburb)
    out: dict[str, Any] = {}
    for sub, g in d.groupby("suburb", sort=True):
        entry = {c: float(g[c].median()) for c in columns}
        entry["n_listings"] = int(len(g))
        entry["default_bedrooms"] = int(g["bedrooms"].median())
        entry["default_bathrooms"] = int(g["bathrooms"].median())
        entry["default_carspaces"] = int(g["carspaces"].median())
        entry["default_property_type"] = str(g["property_type"].mode().iloc[0])
        entry["median_rent"] = float(g[TARGET].median()) if TARGET in g else None
        out[sub] = entry
    glob = {c: float(d[c].median()) for c in columns}
    glob["n_listings"] = int(len(d))
    out[GLOBAL_KEY] = glob
    return out


def build_features(
    raw: pd.DataFrame,
    spec: FeatureSpec,
    lookup: Mapping[str, Any],
) -> tuple[pd.DataFrame, np.ndarray]:
    """Return (model matrix, seen_suburb mask).

    ``raw`` needs ``suburb``, ``property_type``, ``bedrooms``, ``bathrooms``,
    ``carspaces`` and the amenity columns (missing amenities default to 0).
    Suburb context columns always come from ``lookup`` (never from the row), so
    training and serving see exactly the same values for a given suburb.
    """
    n = len(raw)
    suburbs = raw["suburb"].map(normalise_listing_suburb).to_numpy()
    glob = lookup[GLOBAL_KEY]
    seen = np.array([s in lookup and s != GLOBAL_KEY for s in suburbs])

    data: dict[str, Any] = {}
    data["suburb"] = pd.Categorical(
        [s if ok and s in spec.suburb_categories else np.nan for s, ok in zip(suburbs, seen)],
        dtype=CategoricalDtype(categories=spec.suburb_categories),
    )
    data["property_type"] = pd.Categorical(
        raw["property_type"].astype(object).to_numpy(),
        dtype=CategoricalDtype(categories=spec.property_type_categories),
    )
    for c in USER_NUMERIC:
        data[c] = raw[c].astype("float64").to_numpy()
    for c in spec.amenities:
        vals = raw[c] if c in raw else pd.Series(np.zeros(n), index=raw.index)
        data[c] = vals.fillna(0).astype("float64").to_numpy()
    for c in spec.lookup_features:
        data[c] = np.array(
            [lookup[s][c] if ok else glob[c] for s, ok in zip(suburbs, seen)],
            dtype="float64",
        )
    X = pd.DataFrame(data, index=raw.index)[spec.feature_order]
    return X, seen
