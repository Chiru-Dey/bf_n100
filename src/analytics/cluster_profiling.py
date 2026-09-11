"""Cluster profiling, correlation heatmap, outlier detection, and portfolio stats."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from src.analytics.clustering import (
    FEATURES,
    build_clusters,
    fetch_cluster_features,
    impute_sector_median,
)
from src.analytics.ratios import DB_PATH

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROFILE_PATH = PROJECT_ROOT / "output" / "cluster_profiles.csv"
OUTLIER_PATH = PROJECT_ROOT / "output" / "outlier_report.csv"
STATS_PATH = PROJECT_ROOT / "output" / "portfolio_stats.csv"
HEATMAP_PATH = PROJECT_ROOT / "reports" / "correlation_heatmap.png"

CORRELATION_KPIS = [
    "return_on_equity_pct",
    "return_on_capital_employed_pct",
    "net_profit_margin_pct",
    "debt_to_equity",
    "interest_coverage",
    "asset_turnover",
    "free_cash_flow_cr",
    "revenue_cagr_5yr",
    "pat_cagr_5yr",
    "composite_quality_score",
]


def profile_clusters(frame: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame:
    """Compute mean and median of features per cluster."""
    merged = frame.merge(labels, on="company_id")
    profiles = []
    for cluster_id, group in merged.groupby("cluster_id"):
        row = {
            "cluster_id": cluster_id,
            "cluster_name": group["cluster_name"].iloc[0],
            "count": len(group),
        }
        for feature in FEATURES:
            row[f"{feature}_mean"] = round(group[feature].mean(), 2)
            row[f"{feature}_median"] = round(group[feature].median(), 2)
        profiles.append(row)
    return pd.DataFrame(profiles)


def detect_outliers(frame: pd.DataFrame) -> pd.DataFrame:
    """Flag companies with absolute Z-score > 3 per sector."""
    outliers = []
    for sector, group in frame.groupby("broad_sector"):
        for feature in FEATURES:
            mean = group[feature].mean()
            std = group[feature].std()
            if std == 0 or pd.isna(std):
                continue
            z_scores = (group[feature] - mean) / std
            sector_outliers = group[z_scores.abs() > 3]
            for idx, row in sector_outliers.iterrows():
                outliers.append(
                    {
                        "company_id": row["company_id"],
                        "metric": feature,
                        "value": round(row[feature], 2),
                        "z_score": round(z_scores[idx], 2),
                        "sector": sector,
                        "sector_mean": round(mean, 2),
                        "sector_std": round(std, 2),
                    }
                )
    return pd.DataFrame(outliers)


def portfolio_statistics(frame: pd.DataFrame) -> pd.DataFrame:
    """Compute P10-P90, mean, and std for core KPIs."""
    stats = []
    for kpi in CORRELATION_KPIS:
        if kpi not in frame.columns:
            continue
        series = frame[kpi].dropna()
        if series.empty:
            continue
        stats.append(
            {
                "Metric": kpi,
                "P10": round(np.percentile(series, 10), 2),
                "P25": round(np.percentile(series, 25), 2),
                "P50": round(np.percentile(series, 50), 2),
                "P75": round(np.percentile(series, 75), 2),
                "P90": round(np.percentile(series, 90), 2),
                "Mean": round(series.mean(), 2),
                "Std": round(series.std(), 2),
            }
        )
    return pd.DataFrame(stats)


def plot_correlation_heatmap(frame: pd.DataFrame, path: Path = HEATMAP_PATH) -> Path:
    """Generate and save the Pearson correlation heatmap."""
    available_kpis = [kpi for kpi in CORRELATION_KPIS if kpi in frame.columns]
    corr = frame[available_kpis].corr()

    fig, ax = plt.subplots(figsize=(10, 8), dpi=110)
    sns.heatmap(corr, annot=True, fmt=".2f", cmap="coolwarm", center=0, ax=ax)
    ax.set_title("Pearson Correlation Matrix (Latest Year KPIs)")
    plt.xticks(rotation=45, ha="right")
    plt.yticks(rotation=0)
    fig.tight_layout()

    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    plt.close(fig)
    return path


def fetch_latest_ratios(db_path: Path = DB_PATH) -> pd.DataFrame:
    """Return the latest annual ratios joined with sectors for all companies."""
    with sqlite3.connect(db_path) as conn:
        ratios = pd.read_sql_query("SELECT * FROM financial_ratios", conn)
        sectors = pd.read_sql_query(
            "SELECT company_id, broad_sector FROM sectors", conn
        )
    march = ratios[ratios["year"].str.endswith("-03")]
    latest = march.sort_values("year").groupby("company_id").tail(1)
    missing = set(ratios["company_id"]) - set(latest["company_id"])
    if missing:
        fallback = (
            ratios[ratios["company_id"].isin(missing)]
            .sort_values("year")
            .groupby("company_id")
            .tail(1)
        )
        latest = pd.concat([latest, fallback])
    return latest.merge(sectors, on="company_id", how="left")


def run_profiling(db_path: Path = DB_PATH) -> None:
    """Execute cluster profiling, outlier detection, and portfolio stats."""
    frame = impute_sector_median(fetch_cluster_features(db_path))
    labels = build_clusters(frame)

    profiles = profile_clusters(frame, labels)
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    profiles.to_csv(PROFILE_PATH, index=False)
    logger.info("Wrote cluster profiles to %s", PROFILE_PATH)

    outliers = detect_outliers(frame)
    outliers.to_csv(OUTLIER_PATH, index=False)
    logger.info("Detected %d outliers (|Z| > 3)", len(outliers))

    latest = fetch_latest_ratios(db_path)
    plot_correlation_heatmap(latest)
    logger.info("Saved correlation heatmap to %s", HEATMAP_PATH)

    stats = portfolio_statistics(latest)
    stats.to_csv(STATS_PATH, index=False)
    logger.info("Wrote portfolio statistics to %s", STATS_PATH)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_profiling()
