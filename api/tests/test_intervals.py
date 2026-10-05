import math

import numpy as np
import pytest

from rentmodel.intervals import apply_interval, band_for, conformal_quantiles


def test_conformal_finite_sample_ranks():
    r = np.arange(1, 100, dtype=float)  # n = 99
    lo, hi = conformal_quantiles(r, alpha=0.10)
    assert lo == r[math.floor(100 * 0.05) - 1]
    assert hi == r[math.ceil(100 * 0.95) - 1]


def test_conformal_coverage_on_synthetic_data():
    rng = np.random.default_rng(0)
    calib, new = rng.normal(0, 0.15, 5000), rng.normal(0, 0.15, 20000)
    lo, hi = conformal_quantiles(calib, 0.10)
    cov = np.mean((new >= lo) & (new <= hi))
    assert 0.88 < cov < 0.92


def test_interval_ordering_global_and_banded(meta):
    pts = np.array([250.0, 600.0, 799.99, 800.0, 1200.0, 1500.0, 4000.0])
    for iv in (meta["intervals"]["global"], meta["intervals"]):
        lo, hi = apply_interval(pts, iv)
        assert np.all(lo < pts) and np.all(pts < hi) and np.all(lo > 0)


def test_band_selection_edges():
    bands = [{"min_pred": None, "max_pred": 800.0, "lo_q": -0.1, "hi_q": 0.1},
             {"min_pred": 800.0, "max_pred": None, "lo_q": -0.3, "hi_q": 0.5}]
    assert band_for(799.0, bands) is bands[0]
    assert band_for(800.0, bands) is bands[1]
    lo, hi = apply_interval(1000.0, {"bands": bands})
    assert lo[0] == pytest.approx(1000 * math.exp(-0.3))
    assert hi[0] == pytest.approx(1000 * math.exp(0.5))
