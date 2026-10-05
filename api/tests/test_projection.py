import pytest

from rentmodel.projection import project, quarter_index, quarters_between

TOY = {
    "history": {"start": "2025Q1", "values": [380.0, 390.0, 400.0]},  # ends 2025Q3 at $400
    "forecast": {
        "start": "2025Q4",
        "mean": [410.0, 420.0] + [430.0] * 22,
        "lower95": [390.0, 380.0] + [360.0] * 22,
        "upper95": [430.0, 460.0] + [500.0] * 22,
    },
}


def test_projection_toy_example():
    out = project(500.0, 400.0, 620.0, TOY, "2026Q1")
    assert [p["quarter"] for p in out] == ["2025Q3", "2025Q4", "2026Q1"]
    # horizon 0 is exactly the XGB interval
    assert out[0] == {"quarter": "2025Q3", "point": 500.0, "lower": 400.0, "upper": 620.0, "growth_factor": 1.0}
    q4 = out[1]
    assert q4["point"] == pytest.approx(500 * 410 / 400)
    assert q4["lower"] == pytest.approx(400 * 390 / 400)
    assert q4["upper"] == pytest.approx(620 * 430 / 400)
    q1 = out[2]
    assert q1["point"] == pytest.approx(525.0)
    assert q1["lower"] == pytest.approx(380.0)
    assert q1["upper"] == pytest.approx(713.0)
    for p in out:
        assert p["lower"] <= p["point"] <= p["upper"]


def test_projection_full_horizon_length():
    out = project(500.0, 400.0, 620.0, TOY, "2031Q3")
    assert len(out) == 25 and out[-1]["quarter"] == "2031Q3"


@pytest.mark.parametrize("bad", ["2025Q2", "2031Q4", "2040Q1"])
def test_projection_rejects_out_of_range(bad):
    with pytest.raises(ValueError):
        project(500.0, 400.0, 620.0, TOY, bad)


def test_projection_requires_history_to_end_2025q3():
    bad = {**TOY, "history": {"start": "2025Q1", "values": [380.0, 390.0]}}
    with pytest.raises(ValueError):
        project(500.0, 400.0, 620.0, bad, "2026Q1")


def test_quarter_helpers():
    assert quarters_between("2025Q3", "2026Q2") == ["2025Q3", "2025Q4", "2026Q1", "2026Q2"]
    assert quarter_index("2026Q1") - quarter_index("2025Q4") == 1
