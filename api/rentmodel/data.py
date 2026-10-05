"""Train/test split shared by training and the leakage tests (pandas only)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .features import DATE_COL


def load_and_split(path: Path | str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Identical to the notebook: sort by date_listed, earliest 85% train, latest
    15% test, then drop exact duplicates (ignoring listing_id/date_listed) in train only."""
    df = pd.read_parquet(path)
    df[DATE_COL] = pd.to_datetime(df[DATE_COL])
    df_sorted = df.sort_values(DATE_COL).reset_index(drop=True)
    split_idx = int(len(df_sorted) * 0.85)
    train_df = df_sorted.iloc[:split_idx].copy()
    test_df = df_sorted.iloc[split_idx:].copy()
    dup_cols = [c for c in train_df.columns if c not in ("listing_id", DATE_COL)]
    train_df = train_df.drop_duplicates(subset=dup_cols).reset_index(drop=True)
    return train_df, test_df.reset_index(drop=True)
