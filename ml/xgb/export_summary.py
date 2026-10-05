"""Publish the measured model metrics the website's methodology panel shows.

Reads ml/xgb/artifacts/meta.json and writes web/public/data/model_summary.json,
so the page never hard-codes numbers that could drift from the trained model.
Run after train_reduced.py.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
meta = json.loads((ROOT / "ml" / "xgb" / "artifacts" / "meta.json").read_text())
m = meta["metrics"]
iv = meta["intervals"]
cov = m["test_coverage"]["banded" if iv["use_bands"] else "global"]
summary = {
    "train_date_range": meta["train_date_range"],
    "test_date_range": meta["test_date_range"],
    "n_train": meta["n_train"],
    "n_test": meta["n_test"],
    "reduced_test": m["reduced_test"],
    "full_model_test": m["full_model_test_notebook"],
    "baseline_test": m["baseline_reduced_test"],
    "interval_level": iv["nominal"],
    "test_coverage": cov["all"]["coverage"],
    "test_coverage_actual_above_1500": cov["actual_above_1500"],
    "luxury_threshold": meta["luxury_threshold"],
    "amenities": meta["spec"]["amenities"],
}
out = ROOT / "web" / "public" / "data" / "model_summary.json"
out.write_text(json.dumps(summary, indent=1))
print("wrote", out)
