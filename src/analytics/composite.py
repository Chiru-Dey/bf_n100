"""Composite quality score with winsorised normalisation and piecewise scoring."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.analytics.ratios import DEBT_FREE_LABEL, load_ratio_config

WINSORISED_METRICS = (
    ("return_on_equity_pct", "roe"),
    ("return_on_capital_employed_pct", "roce"),
    ("net_profit_margin_pct", "npm"),
    ("fcf_cagr_5yr", "fcf_cagr_5yr"),
    ("cfo_quality_score", "cfo_pat"),
    ("revenue_cagr_5yr", "revenue_cagr_5yr"),
    ("pat_cagr_5yr", "pat_cagr_5yr"),
)


def winsorised_scale(values: pd.Series) -> pd.Series:
    """Scale a series to 0-100 using P10/P90 winsorisation."""
    clean = values.dropna()
    if clean.empty:
        return pd.Series(0.0, index=values.index)
    p10 = clean.quantile(0.10)
    p90 = clean.quantile(0.90)
    if p90 == p10:
        return pd.Series(50.0, index=values.index)
    clipped = values.clip(lower=p10, upper=p90)
    return (clipped - p10) / (p90 - p10) * 100.0


def piecewise_score(value: float | None, anchors: list[list[float]]) -> float | None:
    """Return an interpolated 0-100 score from piecewise linear anchors."""
    if value is None or bool(pd.isna(value)):
        return None
    xs = [point[0] for point in anchors]
    ys = [point[1] for point in anchors]
    return float(np.interp(float(value), xs, ys))


def compute_composite_score(frame: pd.DataFrame) -> pd.Series:
    """Return the 0-100 composite quality score for each row of a KPI frame."""
    config = load_ratio_config()["composite"]
    weights = config["weights"]
    scores = pd.DataFrame(0.0, index=frame.index, columns=list(weights))
    for column, key in WINSORISED_METRICS:
        if column in frame.columns:
            scores[key] = winsorised_scale(frame[column]).fillna(0.0)
    if "free_cash_flow_cr" in frame.columns:
        scores["fcf_positive"] = (frame["free_cash_flow_cr"] > 0).map(
            lambda flag: 100.0 if flag else 0.0
        )
    if "debt_to_equity" in frame.columns:
        scores["de"] = frame["debt_to_equity"].map(
            lambda value: piecewise_score(value, config["de_anchors"]) or 0.0
        )
    if "interest_coverage" in frame.columns:
        if "icr_label" in frame.columns:
            debt_free = frame["icr_label"] == DEBT_FREE_LABEL
        else:
            debt_free = pd.Series(False, index=frame.index)
        scores["icr"] = [
            100.0 if free else (piecewise_score(value, config["icr_anchors"]) or 0.0)
            for value, free in zip(frame["interest_coverage"], debt_free)
        ]
    total = sum(scores[key] * float(weights[key]) for key in weights) / 100.0
    return total.round(2)
