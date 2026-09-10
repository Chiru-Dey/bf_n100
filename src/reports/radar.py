"""Radar chart generation for peer group comparison."""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.analytics.peer import load_peer_groups
from src.screener.engine import build_screener_universe

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "reports" / "radar_charts"

RADAR_AXES = (
    ("return_on_equity_pct", "ROE", False),
    ("return_on_capital_employed_pct", "ROCE", False),
    ("net_profit_margin_pct", "NPM", False),
    ("debt_to_equity", "D/E", True),
    ("fcf_margin_pct", "FCF Score", False),
    ("pat_cagr_5yr", "PAT CAGR 5yr", False),
    ("revenue_cagr_5yr", "Revenue CAGR 5yr", False),
    ("composite_quality_score", "Composite", False),
)


def add_fcf_margin(frame: pd.DataFrame) -> pd.DataFrame:
    """Return frame with FCF margin percent column added."""
    enriched = frame.copy()
    enriched["fcf_margin_pct"] = np.where(
        enriched["sales"].notna() & (enriched["sales"] != 0),
        enriched["free_cash_flow_cr"] / enriched["sales"] * 100.0,
        np.nan,
    )
    return enriched


def min_max_normalise(series: pd.Series, inverted: bool = False) -> pd.Series:
    """Scale a series to 0-1 via min-max, optionally inverting direction."""
    clean = series.dropna()
    if clean.empty:
        return pd.Series(np.nan, index=series.index)
    low = clean.min()
    high = clean.max()
    if high == low:
        return pd.Series(0.5, index=series.index)
    scaled = (series - low) / (high - low)
    return (1.0 - scaled) if inverted else scaled


def build_radar_frame(universe: pd.DataFrame) -> pd.DataFrame:
    """Return universe with 0-1 normalised columns for each radar axis."""
    enriched = add_fcf_margin(universe)
    for column, _, inverted in RADAR_AXES:
        enriched[f"{column}_norm"] = min_max_normalise(enriched[column], inverted)
    return enriched


def _group_map(peer_groups: pd.DataFrame) -> dict[str, str]:
    """Return company to peer group mapping, first group wins."""
    return dict(zip(peer_groups["company_id"], peer_groups["peer_group_name"]))


def render_radar_chart(
    row: pd.Series,
    reference: pd.DataFrame,
    ticker: str,
    group_label: str,
    path: Path,
) -> Path:
    """Render one company radar PNG with peer average overlay."""
    labels = [label for _, label, _ in RADAR_AXES]
    values = [row[f"{column}_norm"] for column, _, _ in RADAR_AXES]
    values = [0.5 if pd.isna(v) else float(v) for v in values]
    peer_values = [reference[f"{column}_norm"].mean() for column, _, _ in RADAR_AXES]
    peer_values = [0.5 if pd.isna(v) else float(v) for v in peer_values]

    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    values += values[:1]
    peer_values += peer_values[:1]
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw={"polar": True})
    ax.plot(angles, values, linewidth=2, label=ticker)
    ax.fill(angles, values, alpha=0.3)
    ax.plot(angles, peer_values, linewidth=2, linestyle="--", label=group_label)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, fontsize=10)
    ax.set_yticklabels([])
    ax.set_title(f"{ticker} vs {group_label}", fontsize=12, pad=20)
    ax.legend(loc="upper right", bbox_to_anchor=(1.25, 1.1), fontsize=9)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)
    return path


def generate_radar_charts(output_dir: Path = OUTPUT_DIR) -> int:
    """Generate radar PNGs for all companies with peer or universe overlay."""
    universe = build_radar_frame(build_screener_universe())
    groups = _group_map(load_peer_groups())
    count = 0
    for _, row in universe.iterrows():
        ticker = row["company_id"]
        group = groups.get(ticker)
        if group:
            members = universe[
                universe["company_id"].isin(
                    [key for key, value in groups.items() if value == group]
                )
            ]
            label = f"{group} average"
        else:
            members = universe
            label = "Nifty 100 average"
        render_radar_chart(
            row, members, ticker, label, output_dir / f"{ticker}_radar.png"
        )
        count += 1
    logger.info("Generated %d radar charts in %s", count, output_dir)
    return count


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    generate_radar_charts()