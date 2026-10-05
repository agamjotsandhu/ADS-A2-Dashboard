"""Loads artifacts once and turns a validated request into a prediction."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import xgboost as xgb

from rentmodel.features import (
    GLOBAL_KEY, FeatureSpec, amenity_label, build_features, normalise_listing_suburb,
)
from rentmodel.intervals import apply_interval
from rentmodel.projection import BASE_QUARTER, FIRST_FORECAST, LAST_FORECAST, project

from .schemas import PredictRequest
from .settings import Settings

log = logging.getLogger(__name__)


def request_to_frame(req: PredictRequest, amenities: list[str]) -> pd.DataFrame:
    """One raw row in the same shape as a training listing."""
    chosen = set(req.amenities)
    row: dict[str, Any] = {
        "suburb": req.suburb,
        "property_type": req.property_type,
        "bedrooms": float(req.bedrooms),
        "bathrooms": float(req.bathrooms),
        "carspaces": float(req.carspaces),
    }
    for a in amenities:
        row[a] = 1 if a in chosen else 0
    return pd.DataFrame([row])


class RentService:
    def __init__(self, settings: Settings):
        art = settings.artifacts_dir
        self.meta: dict[str, Any] = json.loads((art / "meta.json").read_text())
        self.spec = FeatureSpec.from_dict(self.meta["spec"])
        self.lookup: dict[str, Any] = json.loads((art / "suburb_lookup.json").read_text())
        self.booster = xgb.Booster()
        self.booster.load_model(art / "rent_xgb.json")
        if self.meta.get("xgboost_version") != xgb.__version__:
            log.warning("model trained with xgboost %s, serving with %s",
                        self.meta.get("xgboost_version"), xgb.__version__)
        cw_path = art / "suburb_crosswalk.json"
        self.crosswalk: dict[str, Any] = (
            json.loads(cw_path.read_text()) if cw_path.exists() else {"listing_to_arima": {}})
        self.forecasts: dict[str, Any] = {}
        self.forecasts_meta: dict[str, Any] | None = None
        self._load_forecasts(settings.forecasts_path)
        self.luxury = float(self.meta.get("luxury_threshold", 2500))

    def _load_forecasts(self, path: Path) -> None:
        if not path.exists():
            log.warning("no suburb forecasts at %s; projections disabled", path)
            return
        data = json.loads(path.read_text())
        self.forecasts = data.get("suburbs", {})
        self.forecasts_meta = data.get("meta")

    def predict_log(self, X: pd.DataFrame) -> np.ndarray:
        return self.booster.predict(xgb.DMatrix(X, enable_categorical=True))

    # ------------------------------------------------------------------ helpers
    def arima_for(self, listing_suburb: str) -> str | None:
        m = self.crosswalk.get("listing_to_arima", {}).get(listing_suburb)
        name = m["arima"] if m else None
        return name if name in self.forecasts else None

    @property
    def amenities(self) -> list[str]:
        return self.spec.amenities

    def suburbs_payload(self) -> dict[str, Any]:
        subs = []
        for name, e in self.lookup.items():
            if name == GLOBAL_KEY:
                continue
            arima = self.arima_for(name)
            subs.append({
                "name": name,
                "display": name.title(),
                "n_listings": e["n_listings"],
                "defaults": {
                    "property_type": e["default_property_type"],
                    "bedrooms": e["default_bedrooms"],
                    "bathrooms": e["default_bathrooms"],
                    "carspaces": e["default_carspaces"],
                },
                "arima_suburb": arima,
                "has_forecast": arima is not None,
            })
        m = self.meta["metrics"]
        return {
            "suburbs": subs,
            "property_types": self.spec.property_type_categories,
            "amenities": [{"key": a, "label": amenity_label(a)} for a in self.amenities],
            "quarters": {"base": BASE_QUARTER, "first": FIRST_FORECAST, "last": LAST_FORECAST},
            "price_level": self.meta["price_level"],
            "model": {
                "test_metrics": m["reduced_test"],
                "interval_level": self.meta["intervals"]["nominal"],
                "test_coverage": m["test_coverage"]["banded" if self.meta["intervals"]["use_bands"] else "global"]["all"],
                "train_date_range": self.meta["train_date_range"],
            },
            "forecasts_available": bool(self.forecasts),
        }

    # ------------------------------------------------------------------ predict
    def predict(self, req: PredictRequest) -> dict[str, Any]:
        warnings: list[dict[str, str]] = []
        unknown = sorted(set(req.amenities) - set(self.amenities))
        if unknown:
            raise ValueError(f"unknown amenities: {unknown}")
        if req.property_type not in self.spec.property_type_categories:
            raise ValueError(f"unknown property_type {req.property_type!r}")

        raw = request_to_frame(req, self.amenities)
        X, seen = build_features(raw, self.spec, self.lookup)
        point = float(np.expm1(self.predict_log(X)[0]))
        lo, hi = apply_interval(point, self.meta["intervals"])
        lower, upper = float(lo[0]), float(hi[0])

        listing_suburb = normalise_listing_suburb(req.suburb)
        is_seen = bool(seen[0])
        if not is_seen:
            warnings.append({"code": "unseen_suburb", "message":
                "This suburb was not in the training data, so the estimate uses Victoria-wide averages for "
                "location features. Treat it as low confidence."})
        if point > self.luxury:
            warnings.append({"code": "luxury", "message":
                f"Estimate is above ${self.luxury:,.0f}/week. The model under-predicts luxury listings and its "
                "interval is unreliable at this level."})
        if req.bedrooms >= 7 or req.bathrooms >= 6 or req.carspaces >= 7:
            warnings.append({"code": "rare_input", "message":
                "Very few training listings have this many rooms or car spaces, so the estimate is less reliable."})

        arima_name = self.arima_for(listing_suburb) if is_seen else None
        projection = at_target = None
        if req.target_date:
            if arima_name is None:
                warnings.append({"code": "no_forecast", "message":
                    "No suburb rent forecast is available for this suburb, so the estimate is shown at the "
                    "Sep 2025 level only."})
            else:
                projection = project(point, lower, upper, self.forecasts[arima_name], req.target_date)
                at_target = projection[-1]
                warnings.append({"code": "combined_band", "message":
                    "The projected range combines the property model's interval with the suburb forecast's 95% "
                    "band. It is a rough guide, not a formal joint interval."})

        return {
            "point": point,
            "lower": lower,
            "upper": upper,
            "interval_level": self.meta["intervals"]["nominal"],
            "price_level": "Sep 2025",
            "suburb": {
                "input": req.suburb,
                "listing_suburb": listing_suburb if is_seen else None,
                "seen_in_training": is_seen,
                "arima_suburb": arima_name,
            },
            "target_date": req.target_date,
            "at_target": at_target,
            "projection": projection,
            "warnings": warnings,
        }
