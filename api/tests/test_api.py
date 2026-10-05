import json
import shutil

import pytest
from conftest import ARTIFACTS, FIXTURES
from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import Settings
from build_crosswalk import build


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    art = tmp_path_factory.mktemp("artifacts")
    for f in ("rent_xgb.json", "meta.json", "suburb_lookup.json"):
        shutil.copy(ARTIFACTS / f, art / f)
    lookup = json.loads((ARTIFACTS / "suburb_lookup.json").read_text())
    index = json.loads((FIXTURES / "synthetic_suburb_index.json").read_text())
    cw = build([k for k in lookup if not k.startswith("__")], index)
    cw.pop("_review")
    (art / "suburb_crosswalk.json").write_text(json.dumps(cw))
    settings = Settings(artifacts_dir=art, forecasts_path=FIXTURES / "synthetic_suburb_forecasts.json",
                        allowed_origins=["https://example.org"], rate_limit_per_minute=1000, trust_proxy=False)
    with TestClient(create_app(settings)) as c:
        yield c


BASE = {"suburb": "Tarneit", "property_type": "House", "bedrooms": 4, "bathrooms": 2, "carspaces": 2,
        "amenities": ["feat_dishwasher"]}


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and body["xgboost_version"] == "2.1.4" and body["suburbs"] > 600


def test_suburbs_payload(client):
    body = client.get("/suburbs").json()
    names = {s["name"]: s for s in body["suburbs"]}
    assert names["TARNEIT"]["has_forecast"] and names["TARNEIT"]["arima_suburb"] == "Tarneit"
    assert not names["TOORAK"]["has_forecast"]
    assert body["quarters"] == {"base": "2025Q3", "first": "2025Q4", "last": "2031Q3"}
    assert len(body["amenities"]) == 9 and "House" in body["property_types"]


def test_predict_current_level(client):
    r = client.post("/predict", json=BASE)
    assert r.status_code == 200, r.text
    b = r.json()
    assert 0 < b["lower"] < b["point"] < b["upper"]
    assert b["projection"] is None and b["at_target"] is None
    assert b["suburb"]["seen_in_training"] and b["suburb"]["listing_suburb"] == "TARNEIT"
    assert b["warnings"] == []


def test_predict_with_projection(client):
    b = client.post("/predict", json={**BASE, "target_date": "2027Q2"}).json()
    proj = b["projection"]
    assert proj[0]["quarter"] == "2025Q3" and proj[-1]["quarter"] == "2027Q2" and len(proj) == 8
    assert proj[0]["point"] == pytest.approx(b["point"])
    assert proj[0]["lower"] == pytest.approx(b["lower"]) and proj[0]["upper"] == pytest.approx(b["upper"])
    assert b["at_target"] == proj[-1]
    assert all(p["lower"] < p["point"] < p["upper"] for p in proj)
    assert any(w["code"] == "combined_band" for w in b["warnings"])


def test_no_forecast_warning(client):
    b = client.post("/predict", json={**BASE, "suburb": "Toorak", "target_date": "2027Q2"}).json()
    assert b["projection"] is None
    assert [w["code"] for w in b["warnings"]] == ["no_forecast"]


def test_unseen_suburb(client):
    b = client.post("/predict", json={**BASE, "suburb": "Nowhereville", "target_date": "2027Q2"}).json()
    codes = [w["code"] for w in b["warnings"]]
    assert "unseen_suburb" in codes and "no_forecast" in codes
    assert not b["suburb"]["seen_in_training"] and b["suburb"]["listing_suburb"] is None
    assert 0 < b["lower"] < b["point"] < b["upper"]


def test_luxury_warning(client):
    b = client.post("/predict", json={"suburb": "Toorak", "property_type": "House", "bedrooms": 6,
                                      "bathrooms": 5, "carspaces": 4,
                                      "amenities": ["feat_swimming_pool", "feat_study"]}).json()
    codes = [w["code"] for w in b["warnings"]]
    assert ("luxury" in codes) == (b["point"] > 2500)
    assert "rare_input" not in codes or b["point"] > 0


@pytest.mark.parametrize("patch", [
    {"bedrooms": 11}, {"bedrooms": -1}, {"bathrooms": 11}, {"carspaces": 99}, {"bedrooms": "three"},
    {"target_date": "2025Q3"}, {"target_date": "2031Q4"}, {"target_date": "2027-06"},
    {"suburb": ""}, {"unexpected": 1}, {"amenities": ["feat_helipad"]}, {"property_type": "Castle"},
])
def test_validation_rejects_bad_input(client, patch):
    r = client.post("/predict", json={**BASE, **patch})
    assert r.status_code == 422, (patch, r.text)


def test_missing_field(client):
    body = dict(BASE)
    body.pop("bedrooms")
    assert client.post("/predict", json=body).status_code == 422


def test_cors_locked_to_origin(client):
    ok = client.options("/predict", headers={"Origin": "https://example.org", "Access-Control-Request-Method": "POST"})
    bad = client.options("/predict", headers={"Origin": "https://evil.test", "Access-Control-Request-Method": "POST"})
    assert ok.headers.get("access-control-allow-origin") == "https://example.org"
    assert "access-control-allow-origin" not in bad.headers


def test_rate_limit(tmp_path):
    settings = Settings(artifacts_dir=ARTIFACTS, forecasts_path=tmp_path / "none.json",
                        allowed_origins=[], rate_limit_per_minute=3, trust_proxy=False)
    with TestClient(create_app(settings)) as c:
        codes = [c.post("/predict", json=BASE).status_code for _ in range(5)]
        assert codes == [200, 200, 200, 429, 429]
        assert c.get("/health").status_code == 200  # only /predict is limited
        assert c.get("/suburbs").json()["forecasts_available"] is False
