"""Train/serve parity: the API path must produce the exact matrix training produced."""
import json

import numpy as np
import pandas as pd
import xgboost as xgb
from conftest import ARTIFACTS, FIXTURES

from app.schemas import PredictRequest
from app.service import request_to_frame
from rentmodel.features import CATEGORICAL, FeatureSpec, build_features


def test_api_feature_builder_matches_training(meta, lookup):
    fx = json.loads((FIXTURES / "feature_parity_sample.json").read_text())
    spec = FeatureSpec.from_dict(meta["spec"])
    expected = pd.DataFrame(fx["expected"])[spec.feature_order]
    frames = []
    for row in fx["raw"]:
        req = PredictRequest.model_construct(
            suburb=row["suburb"], property_type=row["property_type"],
            bedrooms=int(row["bedrooms"]), bathrooms=int(row["bathrooms"]), carspaces=int(row["carspaces"]),
            amenities=[a for a in spec.amenities if row[a] == 1], target_date=None)
        X, seen = build_features(request_to_frame(req, spec.amenities), spec, lookup)
        assert seen.all()
        frames.append(X)
    got = pd.concat(frames, ignore_index=True)
    got_cmp = got.astype({c: object for c in CATEGORICAL})
    pd.testing.assert_frame_equal(got_cmp, expected.astype({c: object for c in CATEGORICAL}), check_dtype=False)
    # dtypes and categories exactly as recorded at training time
    assert {c: str(t) for c, t in got.dtypes.items()} == meta["dtypes"]
    assert list(got["suburb"].cat.categories) == spec.suburb_categories
    assert list(got["property_type"].cat.categories) == spec.property_type_categories

    booster = xgb.Booster()
    booster.load_model(ARTIFACTS / "rent_xgb.json")
    pred = booster.predict(xgb.DMatrix(got, enable_categorical=True))
    np.testing.assert_allclose(pred, fx["expected_pred_log"], rtol=1e-6)


def test_unseen_suburb_falls_back_to_global_medians(meta, lookup):
    spec = FeatureSpec.from_dict(meta["spec"])
    raw = pd.DataFrame([{"suburb": "NOWHEREVILLE", "property_type": "House",
                         "bedrooms": 3.0, "bathrooms": 2.0, "carspaces": 1.0}])
    X, seen = build_features(raw, spec, lookup)
    assert not seen[0]
    assert pd.isna(X.loc[0, "suburb"])
    for c in spec.lookup_features:
        assert X.loc[0, c] == lookup["__global__"][c]
    for a in spec.amenities:
        assert X.loc[0, a] == 0.0


def test_suburb_name_is_case_insensitive(meta, lookup):
    spec = FeatureSpec.from_dict(meta["spec"])
    base = {"property_type": "House", "bedrooms": 3.0, "bathrooms": 2.0, "carspaces": 1.0}
    a, _ = build_features(pd.DataFrame([{**base, "suburb": "TARNEIT"}]), spec, lookup)
    b, _ = build_features(pd.DataFrame([{**base, "suburb": "  tarneit "}]), spec, lookup)
    pd.testing.assert_frame_equal(a, b)
