import sys

import numpy as np
import pandas as pd
from conftest import ROOT

sys.path.insert(0, str(ROOT / "ml" / "profiles"))
from build_suburb_profiles import LIVABILITY_DOMAINS, MIN_LISTINGS_AFFORD, build_profiles  # noqa: E402


def toy():
    rng = np.random.default_rng(0)
    rows = []
    spec = {"ALPHA": (8, 400, 1500, 2000.0), "BETA": (6, 800, 1000, 9000.0), "GAMMA": (2, 300, 1200, 5000.0)}
    for sub, (n, rent, income, crime) in spec.items():
        for i in range(n):
            row = {c: float(rng.uniform(100, 5000)) for cs, _ in LIVABILITY_DOMAINS.values() for c in cs}
            row.update(suburb=sub, weekly_rent=rent, median_weekly_income=income, crime_rate=crime, population=1000.0,
                       property_type=["House", "Apartment / Unit / Flat", "Studio", "Townhouse"][i % 4],
                       bedrooms=float(i % 6), date_listed="2025-08-01")
            rows.append(row)
    return pd.DataFrame(rows)


def test_affordability_rank_and_threshold():
    out = build_profiles(toy(), [])["suburbs"]
    assert out["ALPHA"]["affordability"]["rent_to_income_pct"] == round(400 / 1500 * 100, 1)
    assert out["ALPHA"]["affordability"]["rank"] == 1 and out["BETA"]["affordability"]["rank"] == 2
    assert out["GAMMA"]["affordability"]["rank"] is None  # fewer than MIN_LISTINGS_AFFORD
    assert MIN_LISTINGS_AFFORD > 2


def test_livability_scores_and_ranks():
    out = build_profiles(toy(), [])["suburbs"]
    for s in out.values():
        assert 0 <= s["livability"]["score"] <= 100
        assert set(s["livability"]["domains"]) == set(LIVABILITY_DOMAINS)
    assert out["ALPHA"]["livability"]["domains"]["Safety"] == 100.0  # lowest crime
    assert out["BETA"]["livability"]["domains"]["Safety"] == 0.0
    ranks = sorted(s["livability"]["rank"] for s in out.values())
    assert ranks[0] == 1


def test_property_profile_counts_add_up():
    out = build_profiles(toy(), [])["suburbs"]
    a = out["ALPHA"]["property_profile"]
    assert sum(a["dwelling"].values()) == sum(a["bedrooms"].values()) == out["ALPHA"]["n_listings"] == 8
    assert a["bedrooms"]["Studio"] == 2 and a["bedrooms"]["5+"] == 1
    assert a["dwelling"]["Apartment / unit"] == 4  # apartments + studios


def test_crosswalk_attached():
    out = build_profiles(toy(), ["Alpha", "Beta-Delta"])["suburbs"]
    assert out["ALPHA"]["arima_suburb"] == "Alpha"
    assert out["BETA"]["arima_suburb"] == "Beta-Delta"
    assert out["GAMMA"]["arima_suburb"] is None
