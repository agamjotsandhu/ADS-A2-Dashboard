"""Train the reduced, user-fillable XGBoost rent model.

Mirrors the preprocessing in `Modelling/GBT Modelling.ipynb` (duplicate drop in
train, time-based 85/15 split on date_listed, log1p target, categories fixed
from train, enable_categorical, tree_method='hist', Optuna 40 trials over a
5-fold TimeSeriesSplit) but only uses features a visitor can supply, plus
suburb-level context filled from a training-only lookup.

Usage:
    python ml/xgb/train_reduced.py [--data data/rentals_final.parquet] [--trials 40]

Writes ml/xgb/artifacts/{rent_xgb.json, meta.json, suburb_lookup.json},
ml/xgb/REPORT.md and a feature-parity fixture for the API tests.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np
import optuna
import pandas as pd
import shap
import sklearn
import xgboost as xgb
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "api"))

from rentmodel.features import (  # noqa: E402
    AMENITY_CANDIDATES, BASE_LOOKUP_FEATURES, CATEGORICAL, DATE_COL,
    EXTRA_LOOKUP_CANDIDATES, GLOBAL_KEY, TARGET, USER_NUMERIC, FeatureSpec,
    build_features, build_suburb_lookup,
)
from rentmodel.data import load_and_split  # noqa: E402
from rentmodel.intervals import apply_interval, conformal_quantiles  # noqa: E402

RANDOM_STATE = 42
N_SPLITS = 5
N_AMENITIES = 9
ALPHA = 0.10  # 90% intervals
LUXURY = 2500.0
# Full-model and baseline numbers from the original notebook (for comparison only).
FULL_MODEL_TEST = {"rmse": 112.8, "mae": 58.2, "mape": 8.8}
FULL_MODEL_CV = {"rmse": 154.6, "mae": 68.5, "mape": 9.8}
NOTEBOOK_BASELINE_CV = {"rmse": 215.6, "mae": 97.3, "mape": 15.0}

ART = ROOT / "ml" / "xgb" / "artifacts"
FIXTURES = ROOT / "api" / "tests" / "fixtures"


def rmse(a, b):
    return float(np.sqrt(mean_squared_error(a, b)))


def mape(a, b):
    return float(np.mean(np.abs((a - b) / a)) * 100)


def metrics(true, pred):
    return {"rmse": rmse(true, pred), "mae": float(mean_absolute_error(true, pred)), "mape": mape(true, pred)}


def xgb_model(params, n_estimators, early_stopping=True):
    kw = dict(
        n_estimators=n_estimators, enable_categorical=True, tree_method="hist",
        random_state=RANDOM_STATE, **params,
    )
    if early_stopping:
        kw.update(eval_metric="rmse", early_stopping_rounds=50)
    return xgb.XGBRegressor(**kw)


def cv_score(X, y, folds, params, n_estimators=2000):
    scores, iters = [], []
    for tr, va in folds:
        m = xgb_model(params, n_estimators)
        m.fit(X.iloc[tr], y[tr], eval_set=[(X.iloc[va], y[va])], verbose=False)
        scores.append(m.best_score)
        iters.append(m.best_iteration)
    return float(np.mean(scores)), iters


QUICK_PARAMS = {"learning_rate": 0.05, "max_depth": 6, "min_child_weight": 5.0,
                "subsample": 0.8, "colsample_bytree": 0.8}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(ROOT / "data" / "rentals_final.parquet"))
    ap.add_argument("--trials", type=int, default=40)
    ap.add_argument("--skip-test", action="store_true",
                    help="dry run: stop before the test set is touched and write nothing")
    ap.add_argument("--report-only", action="store_true",
                    help="re-render REPORT.md from artifacts/meta.json without retraining")
    args = ap.parse_args()
    if args.report_only:
        write_report(json.loads((ART / "meta.json").read_text()), None)
        return

    train_df, test_df = load_and_split(Path(args.data))
    train_max, test_min = train_df[DATE_COL].max(), test_df[DATE_COL].min()
    print(f"train {train_df.shape} {train_df[DATE_COL].min().date()}..{train_max.date()}")
    print(f"test  {test_df.shape} {test_min.date()}..{test_df[DATE_COL].max().date()}")

    y_train = np.log1p(train_df[TARGET].to_numpy())
    y_test_raw = test_df[TARGET].to_numpy()
    tscv = TimeSeriesSplit(n_splits=N_SPLITS)
    folds = list(tscv.split(train_df))

    suburb_categories = sorted(train_df["suburb"].unique())
    property_type_categories = sorted(train_df["property_type"].unique())

    # ---- 1. Choose extra suburb-level distance features (train CV only) ----
    def spec_for(amenities, lookup_feats):
        return FeatureSpec(suburb_categories, property_type_categories, amenities, lookup_feats)

    lookup_all = build_suburb_lookup(train_df, BASE_LOOKUP_FEATURES + EXTRA_LOOKUP_CANDIDATES)
    s_base = spec_for(AMENITY_CANDIDATES, BASE_LOOKUP_FEATURES)
    s_extra = spec_for(AMENITY_CANDIDATES, BASE_LOOKUP_FEATURES + EXTRA_LOOKUP_CANDIDATES)
    sc_base, _ = cv_score(build_features(train_df, s_base, lookup_all)[0], y_train, folds, QUICK_PARAMS)
    sc_extra, _ = cv_score(build_features(train_df, s_extra, lookup_all)[0], y_train, folds, QUICK_PARAMS)
    # "Materially helps" = at least 1% relative improvement in CV log-RMSE.
    use_extra = sc_extra < sc_base * 0.99
    lookup_features = BASE_LOOKUP_FEATURES + (EXTRA_LOOKUP_CANDIDATES if use_extra else [])
    print(f"CV log-RMSE base lookup {sc_base:.4f} vs +distances {sc_extra:.4f} -> use_extra={use_extra}")

    # ---- 2. Choose amenity toggles by SHAP on the training set ----
    s_cand = spec_for(AMENITY_CANDIDATES, lookup_features)
    X_cand, _ = build_features(train_df, s_cand, lookup_all)
    _, it = cv_score(X_cand, y_train, folds, QUICK_PARAMS)
    m = xgb_model(QUICK_PARAMS, int(np.mean(it)), early_stopping=False).fit(X_cand, y_train)
    sv = shap.TreeExplainer(m).shap_values(X_cand)
    imp = pd.Series(np.abs(sv).mean(0), index=X_cand.columns)
    amen_rank = imp[AMENITY_CANDIDATES].sort_values(ascending=False)
    amenities = list(amen_rank.index[:N_AMENITIES])
    print("amenity SHAP ranking:\n" + amen_rank.round(5).to_string())

    spec = spec_for(amenities, lookup_features)
    lookup = build_suburb_lookup(train_df, lookup_features)
    X_train, _ = build_features(train_df, spec, lookup)
    X_test, test_seen = build_features(test_df, spec, lookup)

    # ---- 3. Optuna (same space/sampler as the notebook) ----
    optuna.logging.set_verbosity(optuna.logging.WARNING)

    def objective(trial):
        params = {
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            "max_depth": trial.suggest_int("max_depth", 3, 10),
            "min_child_weight": trial.suggest_float("min_child_weight", 1e-2, 20, log=True),
            "subsample": trial.suggest_float("subsample", 0.5, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
            "gamma": trial.suggest_float("gamma", 1e-3, 5.0, log=True),
            "reg_alpha": trial.suggest_float("reg_alpha", 1e-3, 10.0, log=True),
            "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 10.0, log=True),
        }
        return cv_score(X_train, y_train, folds, params)[0]

    study = optuna.create_study(direction="minimize",
                                sampler=optuna.samplers.TPESampler(seed=RANDOM_STATE))
    study.optimize(objective, n_trials=args.trials, show_progress_bar=False)
    best_params = study.best_params
    print("best CV log-RMSE", round(study.best_value, 5), best_params)

    # ---- 4. CV metrics in dollars + best iterations ----
    cv_rows, best_iters = [], []
    for tr, va in folds:
        m = xgb_model(best_params, 2000)
        m.fit(X_train.iloc[tr], y_train[tr], eval_set=[(X_train.iloc[va], y_train[va])], verbose=False)
        p = np.expm1(m.predict(X_train.iloc[va], iteration_range=(0, m.best_iteration + 1)))
        cv_rows.append(metrics(np.expm1(y_train[va]), p))
        best_iters.append(int(m.best_iteration))
    cv_metrics = {k: float(np.mean([r[k] for r in cv_rows])) for k in ("rmse", "mae", "mape")}
    cv_std = {k: float(np.std([r[k] for r in cv_rows])) for k in ("rmse", "mae", "mape")}
    n_estimators = int(round(np.mean(best_iters)))
    print("CV $", {k: round(v, 1) for k, v in cv_metrics.items()}, "best_iters", best_iters)

    # ---- 5. OOF residuals for conformal intervals ----
    # Fixed n_estimators (no early stopping on the residual rows themselves) so the
    # calibration residuals are honest out-of-sample errors.
    oof_log = np.full(len(X_train), np.nan)
    for tr, va in folds:
        m = xgb_model(best_params, n_estimators, early_stopping=False).fit(X_train.iloc[tr], y_train[tr])
        oof_log[va] = m.predict(X_train.iloc[va])
    cov = ~np.isnan(oof_log)
    resid = y_train[cov] - oof_log[cov]
    oof_point = np.expm1(oof_log[cov])
    lo_q, hi_q = conformal_quantiles(resid, ALPHA)

    # Band-dependent quantiles keyed on predicted rent (calibrated on OOF only).
    band_edges = [None, 800.0, 1500.0, None]
    bands = []
    for lo_e, hi_e in zip(band_edges[:-1], band_edges[1:]):
        mask = np.ones_like(oof_point, dtype=bool)
        if lo_e is not None:
            mask &= oof_point >= lo_e
        if hi_e is not None:
            mask &= oof_point < hi_e
        blo, bhi = conformal_quantiles(resid[mask], ALPHA)
        bands.append({"min_pred": lo_e, "max_pred": hi_e, "lo_q": blo, "hi_q": bhi, "n_calib": int(mask.sum())})
    print(f"global q=({lo_q:.4f},{hi_q:.4f}) bands={bands}")

    # ---- 6. Final refit on all train ----
    final = xgb_model(best_params, n_estimators, early_stopping=False).fit(X_train, y_train)
    if args.skip_test:
        print("--skip-test: stopping before test evaluation; no artifacts written")
        return

    # ---- 7. Test set, evaluated ONCE ----
    test_point = np.expm1(final.predict(X_test))
    test_metrics = metrics(y_test_raw, test_point)

    def coverage(intervals, mask=None):
        lo, hi = apply_interval(test_point, intervals)
        inside = (y_test_raw >= lo) & (y_test_raw <= hi)
        if mask is not None:
            inside = inside[mask]
        return {"coverage": float(inside.mean()) if len(inside) else None, "n": int(len(inside)),
                "median_width": float(np.median((hi - lo) if mask is None else (hi - lo)[mask])) if len(inside) else None}

    glob_iv = {"lo_q": lo_q, "hi_q": hi_q}
    band_iv = {"lo_q": lo_q, "hi_q": hi_q, "bands": bands}
    cov_report = {}
    for name, iv in (("global", glob_iv), ("banded", band_iv)):
        cov_report[name] = {
            "all": coverage(iv),
            "pred_above_2500": coverage(iv, test_point > LUXURY),
            "actual_above_2500": coverage(iv, y_test_raw > LUXURY),
            "actual_above_1500": coverage(iv, y_test_raw > 1500),
            "unseen_suburb": coverage(iv, ~test_seen),
        }
    # Choose banded only if it is at least as good overall and better on the high end
    # of the calibration set (decided on OOF, not test): compare OOF coverage of rows
    # predicted >= $1500 under the global quantiles.
    hi_mask = oof_point >= 1500
    oof_lo, oof_hi = apply_interval(oof_point, glob_iv)
    true_oof = np.expm1(y_train[cov])
    oof_hi_cov = float(((true_oof >= oof_lo) & (true_oof <= oof_hi))[hi_mask].mean()) if hi_mask.any() else None
    use_bands = oof_hi_cov is not None and oof_hi_cov < 0.85
    intervals = band_iv if use_bands else glob_iv
    print("OOF coverage of global interval for pred>=1500:", oof_hi_cov, "-> use_bands", use_bands)

    # ---- 8. Linear baseline on the same reduced features ----
    num = [c for c in X_train.columns if c not in CATEGORICAL]
    def make_lr():
        return Pipeline([
            ("prep", ColumnTransformer([
                ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL),
                ("num", StandardScaler(), num)])),
            ("lr", LinearRegression())])
    Xb_tr = X_train.astype({c: object for c in CATEGORICAL}).fillna({c: "__nan__" for c in CATEGORICAL})
    Xb_te = X_test.astype({c: object for c in CATEGORICAL}).fillna({c: "__nan__" for c in CATEGORICAL})
    base_cv = []
    for tr, va in folds:
        lr = make_lr().fit(Xb_tr.iloc[tr], y_train[tr])
        base_cv.append(metrics(np.expm1(y_train[va]), np.expm1(lr.predict(Xb_tr.iloc[va]))))
    baseline_cv = {k: float(np.mean([r[k] for r in base_cv])) for k in ("rmse", "mae", "mape")}
    lr = make_lr().fit(Xb_tr, y_train)
    baseline_test = metrics(y_test_raw, np.expm1(lr.predict(Xb_te)))

    # ---- 9. SHAP top-15 on final model ----
    sv = shap.TreeExplainer(final).shap_values(X_train)
    shap_top = pd.Series(np.abs(sv).mean(0), index=X_train.columns).sort_values(ascending=False).head(15)

    # ---- 10. Leakage assertions ----
    assert train_max <= test_min, "train rows after test start"
    assert set(k for k in lookup if k != GLOBAL_KEY) <= set(train_df["suburb"].str.upper()), "lookup has non-train suburbs"
    assert suburb_categories == sorted(train_df["suburb"].unique())
    assert len(resid) == int(cov.sum()) and cov.sum() <= len(train_df)

    # ---- 11. Save artifacts ----
    ART.mkdir(parents=True, exist_ok=True)
    final.save_model(ART / "rent_xgb.json")
    (ART / "suburb_lookup.json").write_text(json.dumps(lookup, indent=1))
    meta = {
        "model": "reduced XGBoost on log1p(weekly_rent)",
        "trained_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "xgboost_version": xgb.__version__,
        "sklearn_version": sklearn.__version__,
        "spec": spec.to_dict(),
        "dtypes": {c: str(t) for c, t in X_train.dtypes.items()},
        "amenity_shap_ranking": {k: float(v) for k, v in amen_rank.items()},
        "lookup_selection": {"cv_logrmse_base": sc_base, "cv_logrmse_with_distances": sc_extra, "use_extra": bool(use_extra)},
        "best_params": best_params,
        "n_estimators": n_estimators,
        "cv_best_iterations": best_iters,
        "train_date_range": [str(train_df[DATE_COL].min().date()), str(train_max.date())],
        "test_date_range": [str(test_min.date()), str(test_df[DATE_COL].max().date())],
        "n_train": int(len(train_df)), "n_test": int(len(test_df)),
        "price_level": "Sep 2025 (training listings are ~97% Jul-Sep 2025)",
        "intervals": {
            "nominal": 1 - ALPHA, "method": "split conformal on OOF log1p residuals (finite-sample adjusted)",
            "n_calibration": int(cov.sum()), **intervals,
            "global": glob_iv, "bands_candidate": bands, "use_bands": bool(use_bands),
            "oof_coverage_global_pred_ge_1500": oof_hi_cov,
        },
        "metrics": {
            "reduced_cv": cv_metrics, "reduced_cv_std": cv_std, "reduced_test": test_metrics,
            "baseline_reduced_cv": baseline_cv, "baseline_reduced_test": baseline_test,
            "full_model_test_notebook": FULL_MODEL_TEST, "full_model_cv_notebook": FULL_MODEL_CV,
            "baseline_full_cv_notebook": NOTEBOOK_BASELINE_CV,
            "test_coverage": cov_report,
            "test_unseen_suburb_rows": int((~test_seen).sum()),
        },
        "shap_top15": {k: float(v) for k, v in shap_top.items()},
        "luxury_threshold": LUXURY,
    }
    (ART / "meta.json").write_text(json.dumps(meta, indent=1))

    # Feature-parity fixture: raw train rows + the exact matrix/predictions training produced.
    sample = train_df.sample(60, random_state=RANDOM_STATE)
    raw_cols = CATEGORICAL + USER_NUMERIC + amenities
    Xs, _ = build_features(sample, spec, lookup)
    FIXTURES.mkdir(parents=True, exist_ok=True)
    (FIXTURES / "feature_parity_sample.json").write_text(json.dumps({
        "raw": sample[raw_cols].to_dict(orient="records"),
        "expected": json.loads(Xs.astype({c: object for c in CATEGORICAL}).to_json(orient="records")),
        "expected_pred_log": final.predict(Xs).tolist(),
    }, indent=1))

    write_report(meta, cv_rows)
    print(json.dumps(meta["metrics"], indent=1))


def write_report(meta, cv_rows):
    M = meta["metrics"]
    f = lambda d: f"${d['rmse']:.1f} | ${d['mae']:.1f} | {d['mape']:.1f}%"  # noqa: E731
    cov = M["test_coverage"]
    sel = "banded" if meta["intervals"]["use_bands"] else "global"

    def cov_row(name, c):
        v = "n/a" if c["coverage"] is None else f"{c['coverage']*100:.1f}%"
        w = "n/a" if c["median_width"] is None else f"${c['median_width']:.0f}"
        return f"| {name} | {c['n']} | {v} | {w} |"

    lines = [
        "# Reduced XGBoost rent model: report",
        "",
        f"Generated by `ml/xgb/train_reduced.py` on {meta['trained_at']} (xgboost {meta['xgboost_version']}).",
        "",
        "## What changed vs the notebook model",
        "- Features restricted to what a visitor can enter: suburb, property type, bedrooms, bathrooms, car spaces and "
        f"{len(meta['spec']['amenities'])} amenity toggles chosen by training-set SHAP.",
        "- Suburb context (" + ", ".join(f"`{c}`" for c in meta["spec"]["lookup_features"]) +
        ") comes from per-suburb medians of the **training** rows, for training and serving alike.",
        "- `days_since_start` and `amenity_count` dropped (not extrapolatable / not fillable). Predictions are a Sep 2025 rent level.",
        f"- Extra distance features: CV log-RMSE {meta['lookup_selection']['cv_logrmse_base']:.4f} without vs "
        f"{meta['lookup_selection']['cv_logrmse_with_distances']:.4f} with; kept = {meta['lookup_selection']['use_extra']} (rule: >=1% relative gain).",
        "",
        "## Test-set metrics (n = %d, evaluated once)" % meta["n_test"],
        "",
        "| Model | RMSE | MAE | MAPE |",
        "|---|---|---|---|",
        f"| Full XGBoost, 94 features (notebook) | {f(M['full_model_test_notebook'])} |",
        f"| **Reduced XGBoost (this model)** | **{f(M['reduced_test'])}** |",
        f"| Linear baseline, reduced features | {f(M['baseline_reduced_test'])} |",
        "",
        "Cross-validation (5-fold TimeSeriesSplit, mean):",
        "",
        "| Model | RMSE | MAE | MAPE |",
        "|---|---|---|---|",
        f"| Full XGBoost (notebook) | {f(M['full_model_cv_notebook'])} |",
        f"| Reduced XGBoost | {f(M['reduced_cv'])} |",
        f"| Linear baseline, full features (notebook) | {f(M['baseline_full_cv_notebook'])} |",
        f"| Linear baseline, reduced features | {f(M['baseline_reduced_cv'])} |",
        "",
        "## Prediction intervals (nominal 90%)",
        "",
        f"Split conformal on out-of-fold log1p residuals ({meta['intervals']['n_calibration']} training rows). "
        f"Global quantiles: lo_q = {meta['intervals']['global']['lo_q']:.4f}, hi_q = {meta['intervals']['global']['hi_q']:.4f} "
        f"(about {np.exp(meta['intervals']['global']['lo_q'])*100-100:.0f}% / +{np.exp(meta['intervals']['global']['hi_q'])*100-100:.0f}% of the point estimate).",
        "",
        f"Served interval: **{sel}** (banded is used only if global OOF coverage for predictions >= $1,500 is below 85%; "
        f"measured {meta['intervals']['oof_coverage_global_pred_ge_1500']*100:.1f}% on {next(b['n_calib'] for b in meta['intervals']['bands_candidate'] if b['min_pred'] == 1500.0)} OOF rows).",
        "",
    ]
    for name in ("global", "banded"):
        lines += [f"Test coverage, {name} quantiles:", "", "| Subset | n | Coverage | Median width |", "|---|---|---|---|"]
        lines += [cov_row(k.replace("_", " "), v) for k, v in cov[name].items()]
        lines += [""]
    lines += ["Band quantiles (calibrated on OOF predictions):", "", "| Predicted rent | n calib | lo_q | hi_q |", "|---|---|---|---|"]
    for b in meta["intervals"]["bands_candidate"]:
        if b["min_pred"] is None:
            rng = f"below ${b['max_pred']:,.0f}"
        elif b["max_pred"] is None:
            rng = f"${b['min_pred']:,.0f} and above"
        else:
            rng = f"${b['min_pred']:,.0f} to ${b['max_pred']:,.0f}"
        lines.append(f"| {rng} | {b['n_calib']} | {b['lo_q']:.4f} | {b['hi_q']:.4f} |")
    lines += ["", "## SHAP top-15 (mean |SHAP|, log-rent scale, training set)", "", "| Feature | mean abs SHAP |", "|---|---|"]
    lines += [f"| {k} | {v:.4f} |" for k, v in meta["shap_top15"].items()]
    lines += [
        "", "## Caveats",
        "- The test window is only ~5 days (Sep 2025) and contains no listing above $4,000/week, so tail coverage is measured on very few rows.",
        "- About 11.5% of test rows share an exact lat/lon with a training row (re-listings), which may flatter test metrics.",
        "- Calibration residuals come from fold models trained on less data than the final model, so intervals are slightly conservative.",
        "- During development a 2-trial smoke run of this script also computed test metrics. No selection rule or "
        "setting was changed afterwards: amenity/lookup/band choices are fixed rules evaluated on training data only.",
        f"- Optuna's best learning_rate ({meta['best_params']['learning_rate']:.4f}) and max_depth ({meta['best_params']['max_depth']}) "
        "sit on the search-space edges, as in the notebook; a wider search might do slightly better.",
        "- Luxury listings (above ~$2,500/week) are systematically under-predicted; intervals there are not reliable.",
        "- Suburb lookup medians use all training rows, so the CV folds share suburb context (not target values) across folds. The test set is untouched.",
        "",
    ]
    (ROOT / "ml" / "xgb" / "REPORT.md").write_text("\n".join(lines))


if __name__ == "__main__":
    main()
