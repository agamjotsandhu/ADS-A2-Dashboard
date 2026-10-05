"""Split-conformal style prediction intervals on the log1p scale.

Residuals are ``log1p(actual) - log1p(predicted)`` from out-of-fold CV
predictions on the training set. The interval for a new point is
``point * exp(lo_q)`` to ``point * exp(hi_q)``, optionally with band-specific
quantiles keyed on the predicted rent.
"""
from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

import numpy as np


def conformal_quantiles(residuals: np.ndarray, alpha: float = 0.10) -> tuple[float, float]:
    """Lower/upper residual quantiles with the finite-sample adjustment.

    For n calibration residuals the upper quantile uses rank ceil((n+1)(1-alpha/2))
    and the lower uses floor((n+1)(alpha/2)), i.e. a slightly conservative
    two-sided (1-alpha) interval.
    """
    r = np.sort(np.asarray(residuals, dtype=float))
    r = r[np.isfinite(r)]
    n = len(r)
    if n == 0:
        raise ValueError("no residuals")
    k_hi = min(n, math.ceil((n + 1) * (1 - alpha / 2)))
    k_lo = max(1, math.floor((n + 1) * (alpha / 2)))
    return float(r[k_lo - 1]), float(r[k_hi - 1])


def band_for(point: float, bands: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
    """Pick the band whose [min_pred, max_pred) contains ``point``."""
    for b in bands:
        lo = b["min_pred"] if b["min_pred"] is not None else -math.inf
        hi = b["max_pred"] if b["max_pred"] is not None else math.inf
        if lo <= point < hi:
            return b
    return bands[-1]


def apply_interval(
    point: np.ndarray | float,
    intervals: Mapping[str, Any],
) -> tuple[np.ndarray, np.ndarray]:
    """Return (lower, upper) in dollars for point predictions in dollars."""
    p = np.atleast_1d(np.asarray(point, dtype=float))
    bands = intervals.get("bands")
    if bands:
        lo_q = np.array([band_for(x, bands)["lo_q"] for x in p])
        hi_q = np.array([band_for(x, bands)["hi_q"] for x in p])
    else:
        lo_q = np.full_like(p, intervals["lo_q"])
        hi_q = np.full_like(p, intervals["hi_q"])
    return p * np.exp(lo_q), p * np.exp(hi_q)
