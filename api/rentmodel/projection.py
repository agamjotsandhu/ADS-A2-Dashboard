"""Combine the XGBoost 'Sep 2025' estimate with a suburb ARIMA trajectory.

    adj(t)               = ARIMA_mean(t)  / ARIMA_actual(2025Q3)
    projection_point(t)  = xgb_point * adj(t)
    projection_lower(t)  = xgb_lower * ARIMA_lower(t) / ARIMA_actual(2025Q3)
    projection_upper(t)  = xgb_upper * ARIMA_upper(t) / ARIMA_actual(2025Q3)

At horizon 0 (2025Q3) the ARIMA mean/lower/upper are all the observed actual,
so the band starts exactly at the XGBoost interval.

Caveat: this multiplies two separate uncertainty sources (listing-level model
error and suburb-median forecast error). It is a heuristic band, not a formal
joint prediction interval, and it assumes a listing's rent moves in proportion
to its suburb median.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

BASE_QUARTER = "2025Q3"
FIRST_FORECAST = "2025Q4"
LAST_FORECAST = "2031Q3"

_Q_RE = re.compile(r"^(\d{4})Q([1-4])$")


def parse_quarter(q: str) -> tuple[int, int]:
    m = _Q_RE.match(q)
    if not m:
        raise ValueError(f"bad quarter {q!r}, expected e.g. 2027Q1")
    return int(m.group(1)), int(m.group(2))


def quarter_index(q: str) -> int:
    y, n = parse_quarter(q)
    return y * 4 + (n - 1)


def quarter_from_index(i: int) -> str:
    return f"{i // 4}Q{i % 4 + 1}"


def quarters_between(start: str, end: str) -> list[str]:
    return [quarter_from_index(i) for i in range(quarter_index(start), quarter_index(end) + 1)]


def project(
    xgb_point: float,
    xgb_lower: float,
    xgb_upper: float,
    forecast: Mapping[str, Any],
    target: str,
) -> list[dict[str, Any]]:
    """Projection from BASE_QUARTER through ``target`` (inclusive).

    ``forecast`` is one suburb record from suburb_forecasts.json, with
    ``history`` {start, values} and ``forecast`` {start, mean, lower95, upper95}.
    """
    t_idx = quarter_index(target)
    if not quarter_index(BASE_QUARTER) <= t_idx <= quarter_index(LAST_FORECAST):
        raise ValueError(f"target must be between {BASE_QUARTER} and {LAST_FORECAST}")

    hist = forecast["history"]
    last_hist_q = quarter_from_index(quarter_index(hist["start"]) + len(hist["values"]) - 1)
    if last_hist_q != BASE_QUARTER:
        raise ValueError(f"ARIMA history ends {last_hist_q}, expected {BASE_QUARTER}")
    actual = float(hist["values"][-1])
    if not actual > 0:
        raise ValueError("ARIMA base actual must be positive")

    fc = forecast["forecast"]
    fc_start = quarter_index(fc["start"])
    out = [{
        "quarter": BASE_QUARTER,
        "point": xgb_point,
        "lower": xgb_lower,
        "upper": xgb_upper,
        "growth_factor": 1.0,
    }]
    for i in range(quarter_index(BASE_QUARTER) + 1, t_idx + 1):
        h = i - fc_start
        mean, lo, hi = fc["mean"][h], fc["lower95"][h], fc["upper95"][h]
        out.append({
            "quarter": quarter_from_index(i),
            "point": xgb_point * mean / actual,
            "lower": xgb_lower * lo / actual,
            "upper": xgb_upper * hi / actual,
            "growth_factor": mean / actual,
        })
    return out
