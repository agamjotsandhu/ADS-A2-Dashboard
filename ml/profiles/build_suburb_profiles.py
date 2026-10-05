"""Build per-suburb profiles for the /suburb-profile/ page.

For each listing suburb:
  - property profile: rental listings by dwelling group and by bedrooms
  - affordability: median asking rent / median weekly income (lower = more affordable),
    ranked only for suburbs with at least MIN_LISTINGS_AFFORD listings
  - livability: equal-weight mean of seven domain scores (0-100, higher = better), each
    the percentile rank of the suburb's median value among all suburbs
  - arima_suburb: matched ARIMA area (same crosswalk rules as the API), used by the page
    to show the rent forecast and rank its forecast growth

Descriptive only: this does not feed the rent model, so it uses every listing.

Usage:
    python ml/profiles/build_suburb_profiles.py [--data data/rentals_final.parquet]
Writes web/public/data/suburb_profiles.json.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml" / "crosswalk"))
from build_crosswalk import build as build_crosswalk  # noqa: E402

MIN_LISTINGS_AFFORD = 5

DWELLING_GROUPS = {
    "House": ["House", "New House & Land", "Acreage / Semi-Rural", "Farm"],
    "Townhouse / semi": ["Townhouse", "Villa", "Duplex", "Terrace", "Semi-Detached"],
    "Apartment / unit": ["Apartment / Unit / Flat", "New Apartments / Off the Plan", "Block of Units", "Studio"],
}
BEDROOM_BINS = ["Studio", "1", "2", "3", "4", "5+"]

# domain -> (columns, higher_is_better). Every domain gets equal weight.
LIVABILITY_DOMAINS: dict[str, tuple[list[str], bool]] = {
    "Safety": (["crime_rate"], False),
    "Public transport": (["train_stations_PTV_road_distance_m", "bus_stops_PTV_road_distance_m"], False),
    "Schools": (["school_primary_road_distance_m", "school_secondary_road_distance_m"], False),
    "Health care": (["medical_doctors_road_distance_m", "hospital_road_distance_m"], False),
    "Shopping": (["shopping_centre_road_distance_m"], False),
    "Parks": (["park_local_road_distance_m"], False),
    "CBD access": (["dist_to_cbd_km_driving"], False),
}


def dwelling_group(pt: str) -> str:
    for g, members in DWELLING_GROUPS.items():
        if pt in members:
            return g
    return "House"


def bedroom_bin(b: float) -> str:
    if b <= 0:
        return "Studio"
    return "5+" if b >= 5 else str(int(b))


def percentile_score(s: pd.Series, higher_is_better: bool) -> pd.Series:
    """0-100, 100 = best suburb on this measure (average rank for ties)."""
    r = s.rank(pct=True, ascending=higher_is_better, method="average")
    return (r - r.min()) / (r.max() - r.min()) * 100 if r.max() > r.min() else r * 0 + 50


def build_profiles(df: pd.DataFrame, arima_names: list[str]) -> dict:
    df = df.copy()
    df["suburb"] = df["suburb"].str.strip().str.upper()
    df["dwelling"] = df["property_type"].map(dwelling_group)
    df["beds_bin"] = df["bedrooms"].map(bedroom_bin)
    g = df.groupby("suburb")

    cols = sorted({c for cs, _ in LIVABILITY_DOMAINS.values() for c in cs})
    med = g[cols + ["weekly_rent", "median_weekly_income", "population"]].median()
    med["n"] = g.size()

    # livability
    domain_scores = pd.DataFrame(index=med.index)
    for domain, (dcols, hib) in LIVABILITY_DOMAINS.items():
        domain_scores[domain] = pd.concat([percentile_score(med[c], hib) for c in dcols], axis=1).mean(axis=1)
    livability = domain_scores.mean(axis=1)
    liv_rank = livability.rank(ascending=False, method="min").astype(int)

    # affordability
    ratio = med["weekly_rent"] / med["median_weekly_income"] * 100
    eligible = med["n"] >= MIN_LISTINGS_AFFORD
    aff_rank = ratio[eligible].rank(ascending=True, method="min").astype(int)

    cw = build_crosswalk(list(med.index), arima_names) if arima_names else {"listing_to_arima": {}}

    suburbs = {}
    for sub, row in med.iterrows():
        sd = df[df["suburb"] == sub]
        dwell = sd["dwelling"].value_counts()
        beds = sd["beds_bin"].value_counts()
        m = cw["listing_to_arima"].get(sub)
        suburbs[sub] = {
            "name": sub,
            "display": sub.title(),
            "n_listings": int(row["n"]),
            "median_rent": float(row["weekly_rent"]),
            "median_weekly_income": float(row["median_weekly_income"]),
            "population": float(row["population"]),
            "dist_to_cbd_km": round(float(row["dist_to_cbd_km_driving"]), 1),
            "affordability": {
                "rent_to_income_pct": round(float(ratio[sub]), 1),
                "rank": int(aff_rank[sub]) if sub in aff_rank.index else None,
            },
            "livability": {
                "score": round(float(livability[sub]), 1),
                "rank": int(liv_rank[sub]),
                "domains": {d: round(float(domain_scores.loc[sub, d]), 1) for d in LIVABILITY_DOMAINS},
            },
            "property_profile": {
                "dwelling": {k: int(dwell.get(k, 0)) for k in DWELLING_GROUPS},
                "property_type": {k: int(v) for k, v in sd["property_type"].value_counts().items()},
                "bedrooms": {k: int(beds.get(k, 0)) for k in BEDROOM_BINS},
                "median_rent_by_bedrooms": {
                    k: float(sd.loc[sd["beds_bin"] == k, "weekly_rent"].median())
                    for k in BEDROOM_BINS if (sd["beds_bin"] == k).sum() >= 3
                },
            },
            "arima_suburb": m["arima"] if m else None,
        }

    dates = pd.to_datetime(df["date_listed"])
    return {
        "meta": {
            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "n_listings": int(len(df)),
            "listing_dates": [str(dates.min().date()), str(dates.max().date())],
            "n_suburbs": int(len(med)),
            "n_affordability_ranked": int(eligible.sum()),
            "min_listings_affordability": MIN_LISTINGS_AFFORD,
            "livability_domains": {d: {"columns": c, "higher_is_better": h} for d, (c, h) in LIVABILITY_DOMAINS.items()},
            "dwelling_groups": DWELLING_GROUPS,
            "arima_matched": int(sum(1 for s in suburbs.values() if s["arima_suburb"])),
        },
        "suburbs": suburbs,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(ROOT / "data" / "rentals_final.parquet"))
    ap.add_argument("--arima-index", default=str(ROOT / "web" / "public" / "data" / "suburb_index.json"))
    ap.add_argument("--out", default=str(ROOT / "web" / "public" / "data" / "suburb_profiles.json"))
    args = ap.parse_args()

    idx = Path(args.arima_index)
    arima = json.loads(idx.read_text()) if idx.exists() else []
    out = build_profiles(pd.read_parquet(args.data), arima)
    Path(args.out).write_text(json.dumps(out, separators=(",", ":")))
    m = out["meta"]
    print(f"{m['n_suburbs']} suburbs | affordability ranked {m['n_affordability_ranked']} "
          f"(>= {m['min_listings_affordability']} listings) | ARIMA matched {m['arima_matched']} -> {args.out}")


if __name__ == "__main__":
    main()
