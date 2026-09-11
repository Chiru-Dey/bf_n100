"""KMeans clustering of companies by financial profile."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from src.analytics.cagr import cagr_ending_at
from src.analytics.cashflow_kpis import resolve_cashflow_columns
from src.analytics.ratios import DB_PATH

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_PATH = PROJECT_ROOT / "output" / "cluster_labels.csv"
ELBOW_PATH = PROJECT_ROOT / "reports" / "elbow_plot.png"

FEATURES = [
    "return_on_equity_pct",
    "debt_to_equity",
    "revenue_cagr_5yr",
    "fcf_cagr_5yr",
    "operating_profit_margin_pct",
]

N_CLUSTERS = 5
RANDOM_STATE = 42

CLUSTER_NAMES = {
    0: "Core Stable",
    1: "Defensive Dividend Payers",
    2: "Value Cyclicals",
    3: "High-Quality Compounders",
    4: "Emerging Growth",
}


def fetch_cluster_features(db_path: Path = DB_PATH) -> pd.DataFrame:
    """Return latest-year feature frame with sector for all companies."""
    with sqlite3.connect(db_path) as conn:
        ratios = pd.read_sql_query("SELECT * FROM financial_ratios", conn)
        sectors = pd.read_sql_query(
            "SELECT company_id, broad_sector FROM sectors", conn
        )
        cashflow = pd.read_sql_query("SELECT * FROM cashflow", conn)
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
    frame = latest.merge(sectors, on="company_id", how="left")
    resolved = resolve_cashflow_columns(cashflow)
    cf = cashflow.rename(
        columns={source: logical for logical, source in resolved.items()}
    )
    cf["fcf"] = cf["cfo"] + cf["cfi"]
    fcf_rows = []
    for company_id, group in cf.groupby("company_id"):
        series = group.set_index("year")["fcf"].dropna().sort_index()
        if series.empty:
            continue
        value, _ = cagr_ending_at(series, str(series.index[-1]), 5)
        fcf_rows.append({"company_id": company_id, "fcf_cagr_5yr": value})
    frame = frame.merge(pd.DataFrame(fcf_rows), on="company_id", how="left")
    return frame[["company_id", "broad_sector", *FEATURES]].copy()


def impute_sector_median(frame: pd.DataFrame) -> pd.DataFrame:
    """Impute missing feature values with sector then universe medians."""
    imputed = frame.copy()
    for feature in FEATURES:
        sector_medians = imputed.groupby("broad_sector")[feature].transform("median")
        imputed[feature] = imputed[feature].fillna(sector_medians)
        imputed[feature] = imputed[feature].fillna(imputed[feature].median())
    return imputed


def build_clusters(frame: pd.DataFrame) -> pd.DataFrame:
    """Run KMeans on scaled features and return labelled companies with distances."""
    scaler = StandardScaler()
    scaled = scaler.fit_transform(frame[list(FEATURES)])
    model = KMeans(n_clusters=N_CLUSTERS, random_state=RANDOM_STATE, n_init="auto")
    labels = model.fit_predict(scaled)
    centroids = model.cluster_centers_
    distances = [
        float(np.linalg.norm(scaled[i] - centroids[labels[i]]))
        for i in range(len(scaled))
    ]
    out = frame[["company_id"]].copy()
    out["cluster_id"] = labels
    out["cluster_name"] = [
        CLUSTER_NAMES.get(label, f"Cluster {label}") for label in labels
    ]
    out["distance_from_centroid"] = [round(distance, 4) for distance in distances]
    return out


def plot_elbow(frame: pd.DataFrame, path: Path = ELBOW_PATH) -> Path:
    """Save the KMeans elbow plot (inertia vs k) and return its path."""
    scaler = StandardScaler()
    scaled = scaler.fit_transform(frame[list(FEATURES)])
    ks = list(range(2, 11))
    inertias = [
        KMeans(n_clusters=k, random_state=RANDOM_STATE, n_init="auto")
        .fit(scaled)
        .inertia_
        for k in ks
    ]
    fig, ax = plt.subplots(figsize=(7.0, 4.5), dpi=110)
    ax.plot(ks, inertias, marker="o")
    ax.set_xlabel("Clusters (k)")
    ax.set_ylabel("Inertia")
    ax.set_title("KMeans Elbow Method")
    ax.set_xticks(ks)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    plt.close(fig)
    return path


def run_clustering(db_path: Path = DB_PATH) -> pd.DataFrame:
    """Cluster all companies, write labels CSV and elbow plot, return labels."""
    frame = impute_sector_median(fetch_cluster_features(db_path))
    labels = build_clusters(frame)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    labels.to_csv(OUTPUT_PATH, index=False)
    plot_elbow(frame)
    logger.info("Wrote cluster labels for %d companies to %s", len(labels), OUTPUT_PATH)
    return labels


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run_clustering()
    logger.info(
        "Cluster sizes:\n%s",
        result["cluster_id"].value_counts().sort_index().to_string(),
    )
