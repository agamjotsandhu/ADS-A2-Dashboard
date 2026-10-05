import json
import sys
from pathlib import Path

import pytest

API = Path(__file__).resolve().parents[1]
ROOT = API.parent
sys.path.insert(0, str(API))
sys.path.insert(0, str(ROOT / "ml" / "crosswalk"))

FIXTURES = Path(__file__).parent / "fixtures"
ARTIFACTS = ROOT / "ml" / "xgb" / "artifacts"
PARQUET = ROOT / "data" / "rentals_final.parquet"


@pytest.fixture(scope="session")
def meta():
    return json.loads((ARTIFACTS / "meta.json").read_text())


@pytest.fixture(scope="session")
def lookup():
    return json.loads((ARTIFACTS / "suburb_lookup.json").read_text())


@pytest.fixture(scope="session")
def synthetic_forecasts():
    return json.loads((FIXTURES / "synthetic_suburb_forecasts.json").read_text())
