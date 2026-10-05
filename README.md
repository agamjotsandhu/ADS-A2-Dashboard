# Melbourne Rent Insights: rent forecast

A `/rent-forecast` page that combines two models:

- **Suburb forecasts (ARIMA, R):** quarterly median weekly rent per suburb/suburb group, 2000Q1 to 2025Q3, forecast to 2031Q3 with 95% intervals. Precomputed to static JSON.
- **Property estimates (XGBoost, Python):** weekly rent for a described listing at the Sep 2025 level, with a 90% conformal prediction interval. Served by a small FastAPI service. If a suburb forecast exists, the estimate is projected forward by the suburb's forecast growth.

```
api/                FastAPI service + shared `rentmodel` package (features, split, intervals, projection) + pytest suite
  rentmodel/        imported by BOTH training and serving (no train/serve skew)
ml/arima/           export_forecasts.R  -> web/public/data/suburb_forecasts.json, suburb_index.json
ml/xgb/             train_reduced.py, export_summary.py, REPORT.md, artifacts/ (model JSON + metadata, no pickle)
ml/crosswalk/       build_crosswalk.py  -> ml/xgb/artifacts/suburb_crosswalk.json (+ ml/crosswalk_review.csv)
web/                Vite + React + TypeScript site (home + /rent-forecast/), Recharts, vitest
render.yaml         Render blueprint (static site + Docker API). Not deployed.
```

The original `Modelling/` notebook and qmd and the raw data are git-ignored and never modified.

## Run locally

```bash
# API (Python 3.11+)
python3 -m venv api/.venv && api/.venv/bin/pip install -r api/requirements-dev.txt
PYTHONPATH=api api/.venv/bin/uvicorn app.main:app --reload --port 8000

# Site
cd web && npm ci && cp .env.example .env.local   # VITE_API_URL=http://localhost:8000
npm run dev                                       # http://localhost:5173/rent-forecast/
```

### Tests and checks

```bash
cd api && .venv/bin/python -m pytest -q          # 42 tests; leakage rebuild test needs data/rentals_final.parquet
cd web && npm run typecheck && npm run lint && npm test
cd web && API_URL=http://localhost:8000 npm run smoke   # e2e smoke against a running API
```

## Environment variables

| Where | Variable | Default | Purpose |
|---|---|---|---|
| API | `ALLOWED_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated CORS allow-list. Set it to the site's origin in production. |
| API | `RATE_LIMIT_PER_MINUTE` | `60` | Per-IP limit on `POST /predict` (in memory, per process). `0` disables it. |
| API | `TRUST_PROXY` | `false` | Use `X-Forwarded-For` for the client IP. Only enable it behind a trusted proxy. |
| API | `ARTIFACTS_DIR` | `ml/xgb/artifacts` | Model, metadata, lookup and crosswalk. |
| API | `FORECASTS_PATH` | `web/public/data/suburb_forecasts.json` | ARIMA forecasts for projections. If the file is missing, projections are disabled with a warning. |
| Site | `VITE_API_URL` | `http://localhost:8000` | API base URL, baked in at build time. |

The code holds no secrets.

## Refit / update pipeline

Run from the repo root, in this order:

1. **ARIMA export (R 4.4, forecast 9.0.2, jsonlite 2.0.0):**
   `Rscript ml/arima/export_forecasts.R path/to/rent_by_qtr_suburb_refactored.csv`
   This takes a long time: about 2 x 100 ARIMA fits plus 20,000-rep simulated ADF tests per suburb, spread over all cores. It validates its output and exits non-zero on NaN/Inf, non-positive values, `lower < mean < upper` violations or a wrong history end. For a quick smoke run, use `ARIMA_PMAX=2 ARIMA_QMAX=2 ADF_REPS=300`.
2. **Crosswalk:** `python3 ml/crosswalk/build_crosswalk.py`. Read the printed stats. If more than 10% of suburbs are unresolved, review `ml/crosswalk_review.csv`.
3. **XGBoost:** `pip install -r ml/requirements.txt`, then `python3 ml/xgb/train_reduced.py --data data/rentals_final.parquet`. This takes about 10 minutes and evaluates the test set once. Use `--skip-test` for dry runs and `--report-only` to re-render `REPORT.md` from `meta.json`. Rebuild the crosswalk afterwards, since it uses the new lookup.
4. **Publish metrics:** `python3 ml/xgb/export_summary.py`, which writes `web/public/data/model_summary.json` for the methodology panel.
5. Run the tests above, commit, then redeploy the API image and the static site.

### When new quarterly data arrives (ABS / DFFH)

The pipeline is anchored to 2025Q3 as "now". To roll it forward by a quarter, update these constants together:

- `ml/arima/export_forecasts.R`: the expected column count (`103`), `FirstForecast` (`2025.75`), the break-search windows, the `"2025Q4"` forecast start and the `"2025Q3"` validation check.
- `api/rentmodel/projection.py`: `BASE_QUARTER`, `FIRST_FORECAST`, `LAST_FORECAST`.
- `web`: the "Sep 2025" / "Sep 2026" / "Sep 2031" labels in `SuburbForecastSection.tsx` and `PropertyEstimator.tsx`, and the horizons 4 and 24 in `lib/forecasts.ts`.
- XGBoost: retrain only when new listings exist. Its price level is whenever its listings were collected (currently Sep 2025), and the projection assumes that matches the ARIMA base quarter. If the two drift apart, the projection is biased.

## Known limitations

- **Luxury under-prediction:** listings above about $2,500/week are systematically under-predicted (e.g. a $10,000 Toorak listing predicted at about $2,100 in the original notebook). Interval coverage for test listings above $1,500 is about 65% (n = 23), against 90% nominal. The API warns above $2,500.
- **Lat/lon overlap:** 11.5% of test rows share an exact lat/lon with a training row (re-listings), which may flatter test metrics for both models.
- **Short test window:** the test set covers 2025-09-04 to 2025-09-09 (1,848 rows), with no rent above $4,000.
- **Backfilled upstream data:** in the source data you can't tell genuine values from backfilled defaults for `crime_rate`, `median_weekly_income` and `population`.
- **Suburb crosswalk gaps:** ARIMA areas are DFFH suburb groups, so some listing suburbs won't map, and a component match applies the group's growth to every member suburb.
- **Combined projection band:** it multiplies the property interval by the suburb forecast interval. It is a heuristic, not a joint prediction interval.
- **Unseen suburbs:** they fall back to Victoria-wide medians. Coverage was poor on the 18 such test rows.
- **Rate limiting is in memory and per process.** Use a shared store if the API is scaled to several instances.

## Decisions and deviations from the brief

- **No ARIMA input data.** `rent_by_qtr_suburb_refactored.csv` wasn't available, so the R export was built and smoke-tested on a synthetic CSV with the same layout (with the Docklands NA pattern), but it has not been run on real data. Until it is, the suburb section shows a "not published yet" state, every listing suburb is unmatched in the crosswalk, and projections are disabled with a warning. The synthetic output exists only as a clearly labelled test fixture.
- **Crosswalk review threshold (Phase 3) not evaluated** for the same reason. The matching rules are unit-tested.
- **qmd bug fixed in the copy:** `fit_suburb_future` used `next` inside a function (an R error when no model passes Ljung-Box). The export returns `NULL` and lists the failure under `meta.failed_suburbs`.
- **Interval formula:** `point * exp(q)` as specified, with residuals on the log1p scale. Band-dependent quantiles (below $800 / $800 to $1,500 / $1,500 and up) are served because, on out-of-fold training predictions, the global interval covered only 46% of rows predicted at $1,500 or more. That decision rule was fixed in code before test evaluation.
- **OOF residuals** use fixed `n_estimators` rather than early stopping on the residual rows, so the calibration errors aren't optimistically biased.
- **`amenity_count` dropped** as well as `days_since_start`, because a visitor can't fill the 52 underlying flags.
- **Extra distance features:** beach, train and national-park distances were tested and didn't improve CV by 1% or more, so they're excluded.
- **Disclosure:** a 2-trial smoke run of the training script also computed test metrics during development. No setting was changed afterwards.
- **Hosting:** the repo had no site or host config, so a Vite static site plus Docker API on Render (`render.yaml`) was chosen. Both are portable to Vercel/Netlify plus Fly/Cloud Run.
