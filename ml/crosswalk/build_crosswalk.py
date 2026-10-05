"""Map listing suburbs (e.g. "SOUTH KINGSVILLE") to ARIMA suburbs
(e.g. "South Kingsville-Altona North").

Rule, in order (first rule that gives a unique answer wins):
  1. exact match after normalisation (case, punctuation, "(Vic.)", Mt/St expansions)
  2. same words in a different order ("Bendigo North" == "North Bendigo")
  3. match against a component of a hyphenated ARIMA name
  4. fuzzy match (difflib ratio >= FUZZY_MIN, and >= FUZZY_GAP better than the runner-up)
Anything with several candidates is "ambiguous"; nothing found is "unmatched".

Usage:
    python ml/crosswalk/build_crosswalk.py [--arima-index web/public/data/suburb_index.json]
Writes ml/xgb/artifacts/suburb_crosswalk.json and ml/crosswalk_review.csv.
"""
from __future__ import annotations

import argparse
import csv
import difflib
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FUZZY_MIN = 0.92
FUZZY_GAP = 0.04
REVIEW_THRESHOLD = 0.10

_ABBREV = {"mt": "mount", "st": "saint", "pt": "point", "nth": "north", "sth": "south", "e": "east", "w": "west"}


def normalise(name: str) -> str:
    s = name.lower()
    s = re.sub(r"\(vic\.?\)", " ", s)
    s = s.replace("&", " and ")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    words = [_ABBREV.get(w, w) for w in s.split()]
    return " ".join(words)


def components(arima_name: str) -> list[str]:
    return [normalise(p) for p in arima_name.split("-") if p.strip()]


def match_one(listing: str, arima_names: list[str]) -> tuple[str, list[str], str]:
    """Return (status, candidates, rule)."""
    n = normalise(listing)
    full = {a: normalise(a) for a in arima_names}

    exact = [a for a, v in full.items() if v == n]
    if len(exact) == 1:
        return "matched", exact, "exact"
    if len(exact) > 1:
        return "ambiguous", exact, "exact"

    tokens = sorted(n.split())
    reorder = [a for a, v in full.items() if sorted(v.split()) == tokens]
    if len(reorder) == 1:
        return "matched", reorder, "word_order"

    comp = [a for a in arima_names if "-" in a and n in components(a)]
    if len(comp) == 1:
        return "matched", comp, "component"
    if len(comp) > 1:
        return "ambiguous", comp, "component"

    scored = []
    for a in arima_names:
        targets = [full[a]] + (components(a) if "-" in a else [])
        scored.append((max(difflib.SequenceMatcher(None, n, t).ratio() for t in targets), a))
    scored.sort(reverse=True)
    if scored and scored[0][0] >= FUZZY_MIN:
        if len(scored) == 1 or scored[0][0] - scored[1][0] >= FUZZY_GAP:
            return "matched", [scored[0][1]], f"fuzzy({scored[0][0]:.2f})"
        return "ambiguous", [a for s, a in scored[:3] if s >= FUZZY_MIN], "fuzzy"
    near = [a for s, a in scored[:3] if s >= 0.75]
    return "unmatched", near, "none"


def build(listing_suburbs: list[str], arima_names: list[str]) -> dict:
    to_arima, review = {}, []
    counts = defaultdict(int)
    for ls in sorted(set(listing_suburbs)):
        status, cands, rule = match_one(ls, arima_names) if arima_names else ("unmatched", [], "no_arima_data")
        counts[status] += 1
        if status == "matched":
            to_arima[ls] = {"arima": cands[0], "rule": rule}
        else:
            review.append({"listing_suburb": ls, "status": status, "rule": rule, "candidates": " | ".join(cands)})
    from_arima = defaultdict(list)
    for ls, m in to_arima.items():
        from_arima[m["arima"]].append(ls)
    total = len(set(listing_suburbs))
    return {
        "listing_to_arima": to_arima,
        "arima_to_listing": {k: sorted(v) for k, v in sorted(from_arima.items())},
        "stats": {
            "listing_suburbs": total,
            "arima_suburbs": len(arima_names),
            "matched": counts["matched"],
            "ambiguous": counts["ambiguous"],
            "unmatched": counts["unmatched"],
            "unresolved_share": (counts["ambiguous"] + counts["unmatched"]) / total if total else 0.0,
            "arima_with_listing": len(from_arima),
            "rules": {"fuzzy_min": FUZZY_MIN, "fuzzy_gap": FUZZY_GAP},
        },
        "_review": review,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arima-index", default=str(ROOT / "web" / "public" / "data" / "suburb_index.json"))
    ap.add_argument("--lookup", default=str(ROOT / "ml" / "xgb" / "artifacts" / "suburb_lookup.json"))
    ap.add_argument("--out", default=str(ROOT / "ml" / "xgb" / "artifacts" / "suburb_crosswalk.json"))
    ap.add_argument("--review", default=str(ROOT / "ml" / "crosswalk_review.csv"))
    args = ap.parse_args()

    listing = [k for k in json.loads(Path(args.lookup).read_text()) if not k.startswith("__")]
    idx = Path(args.arima_index)
    arima = json.loads(idx.read_text()) if idx.exists() else []
    if not arima:
        print(f"WARNING: no ARIMA suburb index at {idx}; every listing suburb will be unmatched "
              "and forward projections are disabled until ml/arima/export_forecasts.R is run.")

    cw = build(listing, arima)
    review = cw.pop("_review")
    Path(args.out).write_text(json.dumps(cw, indent=1))
    with open(args.review, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["listing_suburb", "status", "rule", "candidates"])
        w.writeheader()
        w.writerows(review)
    s = cw["stats"]
    print(f"listing suburbs {s['listing_suburbs']} | ARIMA suburbs {s['arima_suburbs']} | matched {s['matched']} "
          f"| ambiguous {s['ambiguous']} | unmatched {s['unmatched']} | unresolved {s['unresolved_share']:.1%}")
    if arima and s["unresolved_share"] > REVIEW_THRESHOLD:
        print(f"REVIEW NEEDED: more than {REVIEW_THRESHOLD:.0%} unresolved, see {args.review}")


if __name__ == "__main__":
    main()
