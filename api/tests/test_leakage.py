"""No test-period rows may influence lookups, categories or interval quantiles."""
import pandas as pd
import pytest
from conftest import PARQUET

from rentmodel.data import load_and_split
from rentmodel.features import GLOBAL_KEY, build_suburb_lookup


def test_artifact_level_guards(meta, lookup):
    assert meta["train_date_range"][1] <= meta["test_date_range"][0]
    subs = set(k for k in lookup if k != GLOBAL_KEY)
    assert subs == set(meta["spec"]["suburb_categories"])
    assert meta["intervals"]["n_calibration"] < meta["n_train"]
    assert "days_since_start" not in meta["spec"]["feature_order"]


@pytest.mark.skipif(not PARQUET.exists(), reason="raw data not available (data/rentals_final.parquet)")
def test_rebuild_from_raw_train_split(meta, lookup):
    train_df, test_df = load_and_split(PARQUET)
    assert len(train_df) == meta["n_train"] and len(test_df) == meta["n_test"]
    assert train_df["date_listed"].max() <= test_df["date_listed"].min()

    # categories come from train only
    assert meta["spec"]["suburb_categories"] == sorted(train_df["suburb"].unique())
    test_only = set(test_df["suburb"]) - set(train_df["suburb"])
    assert test_only and not (test_only & set(lookup))

    # lookup equals a rebuild from train rows only, and differs from a train+test rebuild
    cols = meta["spec"]["lookup_features"]
    rebuilt = build_suburb_lookup(train_df, cols)
    assert rebuilt == lookup
    with_test = build_suburb_lookup(pd.concat([train_df, test_df]), cols)
    assert with_test != lookup
