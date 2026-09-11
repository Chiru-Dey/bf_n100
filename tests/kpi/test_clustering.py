"""Unit tests for the KMeans clustering pipeline."""

import numpy as np
import pandas as pd

from src.analytics.clustering import FEATURES, build_clusters, impute_sector_median


def _frame() -> pd.DataFrame:
    rng = np.random.default_rng(42)
    size = 30
    return pd.DataFrame(
        {
            "company_id": [f"C{i:02d}" for i in range(size)],
            "broad_sector": ["Information Technology", "Financials", "Energy"] * 10,
            FEATURES[0]: rng.normal(20, 5, size),
            FEATURES[1]: rng.normal(1, 0.5, size),
            FEATURES[2]: rng.normal(10, 3, size),
            FEATURES[3]: rng.normal(8, 4, size),
            FEATURES[4]: rng.normal(20, 6, size),
        }
    )


def test_impute_sector_median_fills_nan() -> None:
    frame = _frame()
    frame.loc[0, FEATURES[0]] = np.nan
    mask = frame["broad_sector"] == frame.loc[0, "broad_sector"]
    expected = frame.loc[mask, FEATURES[0]].median()
    imputed = impute_sector_median(frame)
    assert imputed.loc[0, FEATURES[0]] == expected


def test_impute_sector_median_no_nan_remaining() -> None:
    frame = _frame()
    frame.loc[1, FEATURES[2]] = np.nan
    assert impute_sector_median(frame)[FEATURES].notna().all().all()


def test_build_clusters_covers_all_companies() -> None:
    labels = build_clusters(impute_sector_median(_frame()))
    assert len(labels) == 30
    assert labels["cluster_id"].notna().all()
    assert set(labels["cluster_id"].unique()) <= set(range(5))


def test_build_clusters_columns_and_distance() -> None:
    labels = build_clusters(impute_sector_median(_frame()))
    assert list(labels.columns) == [
        "company_id",
        "cluster_id",
        "cluster_name",
        "distance_from_centroid",
    ]
    assert (labels["distance_from_centroid"] >= 0).all()
