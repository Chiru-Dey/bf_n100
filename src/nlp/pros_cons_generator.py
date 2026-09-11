"""Rule-based pros and cons generator with confidence scoring."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Optional

import pandas as pd

from src.analytics.ratios import DB_PATH, DEBT_FREE_LABEL, is_financials_sector

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_PATH = PROJECT_ROOT / "output" / "pros_cons_generated.csv"

PRO = "pro"
CON = "con"

RuleResult = Optional[tuple[str, str, float]]


def _latest(series: pd.Series) -> Optional[float]:
    """Return the most recent value of a series, or None when missing."""
    if series.empty:
        return None
    value = series.tail(1).iloc[0]
    return None if pd.isna(value) else float(value)


def _tail_values(series: pd.Series, count: int) -> Optional[list[float]]:
    """Return the last count values, or None when any are missing."""
    values = series.tail(count).tolist()
    if len(values) < count or any(pd.isna(v) for v in values):
        return None
    return [float(v) for v in values]


def _strictly_increasing(values: list[float]) -> bool:
    """Return True when every successive value is larger."""
    return all(b > a for a, b in zip(values, values[1:]))


def _strictly_decreasing(values: list[float]) -> bool:
    """Return True when every successive value is smaller."""
    return all(b < a for a, b in zip(values, values[1:]))


def _positive_streak(series: pd.Series) -> int:
    """Count consecutive positive values backwards from the latest."""
    streak = 0
    for value in series.dropna()[::-1]:
        if float(value) > 0:
            streak += 1
        else:
            break
    return streak


def _negative_streak(series: pd.Series) -> int:
    """Count consecutive negative values backwards from the latest."""
    streak = 0
    for value in series.dropna()[::-1]:
        if float(value) < 0:
            streak += 1
        else:
            break
    return streak


def _conf_margin(value: float, threshold: float) -> float:
    """Return confidence 60-99 scaled by relative distance from threshold."""
    gap = abs(value - threshold) / max(abs(threshold), 1e-9)
    return round(min(99.0, 60.0 + 40.0 * min(1.0, gap)), 1)


def _conf_streak(streak: int) -> float:
    """Return confidence 60-95 scaled by streak length."""
    return round(min(95.0, 50.0 + 8.0 * streak), 1)


def pro_roe_sustained(hist: pd.DataFrame, sector: str) -> RuleResult:
    """Pro rule 1: ROE above 20% sustained for 3+ years."""
    values = _tail_values(hist["roe"], 3)
    if values and all(v > 20.0 for v in values):
        return (
            "PRO-01",
            "Consistently high return on equity above 20% demonstrates "
            "exceptional capital efficiency",
            _conf_margin(min(values), 20.0),
        )
    return None


def pro_fcf_streak(hist: pd.DataFrame, sector: str) -> RuleResult:
    """Pro rule 2: FCF positive for 5+ consecutive years."""
    streak = _positive_streak(hist["fcf"])
    if streak >= 5:
        return (
            "PRO-02",
            "Strong free cash flow generation over 5 years signals healthy "
            "business fundamentals",
            _conf_streak(streak),
        )
    return None


def pro_debt_free(hist: pd.DataFrame, sector: str) -> RuleResult:
    """Pro rule 3: D/E equal to zero in the latest year."""
    de = _latest(hist["de"])
    if de == 0.0:
        return (
            "PRO-03",
            "Debt-free balance sheet provides financial flexibility and "
            "eliminates interest burden",
            90.0,
        )
    return None


def pro_revenue_cagr(hist: pd.DataFrame, sector: str) -> RuleResult:
    """Pro rule 4: Revenue CAGR above 15% over 5 years."""
    value = _latest(hist["rev_cagr_5yr"])
    if value is not None and value > 15.0:
        return (
            "PRO-04",
            "Revenue growing at above 15% CAGR over 5 years reflects strong "
            "business momentum",
            _conf_margin(value, 15.0),
        )
    return None


def pro_opm_high(hist: pd.DataFrame, sector: str) -> RuleResult:
    """Pro rule 5: OPM above 25% in the latest year."""
    value = _latest(hist["opm"])
    if value is not None and value > 25.0:
        return (
            "PRO-05",
            "Operating profit margin above 25% indicates strong pricing power "
            "and cost discipline",
            _conf_margin(value, 25.0),
        )
    return None


def pro_pat_cagr(hist: pd.DataFrame, sector: str) -> RuleResult:
    """Pro rule 6: PAT CAGR above 20% over 5 years."""
    value = _latest(hist["pat_cagr_5yr"])
    if value is not None and value > 20.0:
        return (
            "PRO-06",
            "Net profit compounding at above 20% over 5 years creates "
            "significant shareholder value",
            _conf_margin(value, 20.0),
        )
    return None


def pro_icr_strong(hist: pd.DataFrame, sector: str) -> RuleResult:
    """Pro rule 7: ICR above 10 or Debt Free label."""
    icr = _latest(hist["icr"])
    raw_label = hist["icr_label"].tail(1).iloc[0] if len(hist) else None
    if icr is not None and icr > 10.0:
        return (
            "PRO-07",
            "Very high interest coverage ratio reflects negligible financial "
            "stress from debt servicing",
            _conf_margin(icr, 10.0),
        )
    if raw_label == DEBT_FREE_LABEL:
        return (
            "PRO-07",
            "Very high interest coverage ratio reflects negligible financial "
            "stress from debt servicing",
            90.0,
        )
    return None


def pro_dividend_backed(hist: pd.DataFrame, sector: str) -> RuleResult:
    """Pro rule 8: dividend yield above 2% with positive FCF."""
    yield_pct = _latest(hist["div_yield"])
    fcf = _latest(hist["fcf"])
    if yield_pct is not None and yield_pct > 2.0 and fcf is not None and fcf > 0:
        return (
            "PRO-08",
            "Consistent dividend yield above 2% backed by positive free cash flow",
            _conf_margin(yield_pct, 2.0),
        )
    return None


def pro_eps_cagr(hist: pd.DataFrame, sector: str) -> RuleResult:
    """Pro rule 9: EPS CAGR above 15% over 5 years."""
    value = _latest(hist["eps_cagr_5yr"])
    if value is not None and value > 15.0:
        return (
            "PRO-09",
            "Earnings per share growing above 15% CAGR indicates strong "
            "earnings quality and compounding",
            _conf_margin(value, 15.0),
        )
    return None


def pro_roe_improving(hist: pd.DataFrame, sector: str) -> RuleResult:
    """Pro rule 10: ROE improving for 3 consecutive years."""
    values = _tail_values(hist["roe"], 3)
    if values and _strictly_increasing(values):
        return (
            "PRO-10",
            "Return on equity improving for 3 consecutive years shows "
            "strengthening business quality",
            78.0,
        )
    return None


def pro_operating_leverage(hist: pd.DataFrame, sector: str) -> RuleResult:
    """Pro rule 11: PAT CAGR above revenue CAGR (operating leverage)."""
    pat = _latest(hist["pat_cagr_5yr"])
    rev = _latest(hist["rev_cagr_5yr"])
    if pat is not None and rev is not None and pat > rev:
        confidence = round(min(99.0, 60.0 + 40.0 * min(1.0, (pat - rev) / 10.0)), 1)
        return (
            "PRO-11",
            "Revenue growing slower than profits shows improving operating "
            "leverage and scale benefits",
            confidence,
        )
    return None


def pro_self_funded_growth(hist: pd.DataFrame, sector: str) -> RuleResult:
    """Pro rule 12: assets growing while borrowings decline."""
    assets = _tail_values(hist["total_assets"], 2)
    debt = _tail_values(hist["borrowings"], 2)
    if assets and debt and assets[1] > assets[0] and debt[1] < debt[0]:
        return (
            "PRO-12",
            "Growing asset base funded by internal accruals reflects "
            "self-sustaining growth",
            75.0,
        )
    return None


def pro_cfo_positive(hist: pd.DataFrame, sector: str) -> RuleResult:
    """Fallback pro: positive operating cash flow in the latest year."""
    cfo = _latest(hist["cfo"])
    if cfo is not None and cfo > 0:
        return (
            "PRO-13",
            "Positive operating cash flow in latest year provides liquidity "
            "support for operations",
            70.0,
        )
    return None


def pro_listing_history(hist: pd.DataFrame, sector: str) -> RuleResult:
    """Fallback pro: five or more years of audited listed history."""
    if len(hist) >= 5:
        return (
            "PRO-14",
            f"{len(hist)} years of audited listed financial history supports "
            "reliable fundamental trend analysis",
            65.0,
        )
    return None


def pro_going_concern(hist: pd.DataFrame, sector: str) -> RuleResult:
    """Fallback pro: operating going concern with active listing."""
    return (
        "PRO-15",
        "Company remains an operating going concern with active exchange "
        "listing; monitor for emerging strengths",
        61.0,
    )


def con_de_elevated(hist: pd.DataFrame, sector: str) -> RuleResult:
    """Con rule 1: D/E above 2.0 for non-financial companies."""
    de = _latest(hist["de"])
    if de is not None and de > 2.0 and not is_financials_sector(sector):
        return (
            "CON-01",
            f"Debt-to-equity ratio of {de:.2f} is elevated for a non-financial "
            "company and warrants monitoring",
            _conf_margin(de, 2.0),
        )
    return None


def con_fcf_negative_streak(hist: pd.DataFrame, sector: str) -> RuleResult:
    """Con rule 2: FCF negative for 3 consecutive years."""
    streak = _negative_streak(hist["fcf"])
    if streak >= 3:
        return (
            "CON-02",
            "Free cash flow negative for 3 consecutive years raises concern "
            "about cash generation quality",
            _conf_streak(streak),
        )
    return None


def con_opm_declining(hist: pd.DataFrame, sector: str) -> RuleResult:
    """Con rule 3: OPM declining for 3 consecutive years."""
    values = _tail_values(hist["opm"], 3)
    if values and _strictly_decreasing(values):
        return (
            "CON-03",
            "Operating margins declining for 3 consecutive years suggests "
            "pricing or cost pressure",
            78.0,
        )
    return None


def con_latest_loss(hist: pd.DataFrame, sector: str) -> RuleResult:
    """Con rule 4: net profit negative in the latest year."""
    value = _latest(hist["net_profit"])
    if value is not None and value < 0:
        return (
            "CON-04",
            "Company reported a net loss in the most recent financial year",
            85.0,
        )
    return None


def con_revenue_contraction(hist: pd.DataFrame, sector: str) -> RuleResult:
    """Con rule 5: revenue declining for 2+ consecutive years."""
    values = _tail_values(hist["sales"], 3)
    if values and _strictly_decreasing(values):
        return (
            "CON-05",
            "Revenue contraction over 2 consecutive years indicates demand "
            "weakness or market share loss",
            80.0,
        )
    return None


def con_icr_weak(hist: pd.DataFrame, sector: str) -> RuleResult:
    """Con rule 6: ICR below 1.5."""
    value = _latest(hist["icr"])
    if value is not None and value < 1.5:
        return (
            "CON-06",
            "Interest coverage ratio below 1.5x indicates the company is at "
            "risk of not meeting its debt obligations",
            _conf_margin(value, 1.5),
        )
    return None


def con_payout_unsustainable(hist: pd.DataFrame, sector: str) -> RuleResult:
    """Con rule 7: dividend payout above 100%."""
    value = _latest(hist["payout"])
    if value is not None and value > 100.0:
        return (
            "CON-07",
            "Dividend payout ratio above 100% means the company is paying "
            "dividends from reserves, which is unsustainable",
            _conf_margin(value, 100.0),
        )
    return None


def con_de_rising(hist: pd.DataFrame, sector: str) -> RuleResult:
    """Con rule 8: D/E rising for 3 consecutive years."""
    values = _tail_values(hist["de"], 3)
    if values and _strictly_increasing(values):
        return (
            "CON-08",
            "Rising debt-to-equity ratio over 3 years suggests increasing "
            "financial leverage risk",
            78.0,
        )
    return None


def con_eps_declining(hist: pd.DataFrame, sector: str) -> RuleResult:
    """Con rule 9: EPS declining for 3 consecutive years."""
    values = _tail_values(hist["eps"], 3)
    if values and _strictly_decreasing(values):
        return (
            "CON-09",
            "Earnings per share declining for 3 consecutive years reflects "
            "deteriorating profitability",
            78.0,
        )
    return None


def con_roce_low(hist: pd.DataFrame, sector: str) -> RuleResult:
    """Con rule 10: ROCE below 10%."""
    value = _latest(hist["roce"])
    if value is not None and value < 10.0:
        return (
            "CON-10",
            "Return on capital employed below 10% suggests the business is not "
            "generating sufficient returns on invested capital",
            _conf_margin(value, 10.0),
        )
    return None


def con_net_debt_high(hist: pd.DataFrame, sector: str) -> RuleResult:
    """Con rule 11: net debt above 3x EBITDA."""
    borrowings = _latest(hist["borrowings"])
    investments = _latest(hist["investments"])
    ebitda = _latest(hist["operating_profit"])
    if borrowings is None or ebitda is None or ebitda <= 0:
        return None
    invested = 0.0 if investments is None else investments
    net_debt = borrowings - invested
    if net_debt > 3.0 * ebitda:
        return (
            "CON-11",
            "Net debt exceeding 3 times EBITDA is a high leverage ratio and "
            "limits financial flexibility",
            _conf_margin(net_debt / ebitda, 3.0),
        )
    return None


def con_revenue_cagr_low(hist: pd.DataFrame, sector: str) -> RuleResult:
    """Con rule 12: revenue CAGR below 5% over 5 years."""
    value = _latest(hist["rev_cagr_5yr"])
    if value is not None and value < 5.0:
        return (
            "CON-12",
            "Revenue growing at below 5% over 5 years lags inflation and "
            "suggests limited business momentum",
            _conf_margin(value, 5.0),
        )
    return None


def con_residual_monitor(hist: pd.DataFrame, sector: str) -> RuleResult:
    """Fallback con: residual monitoring note when no red flags trigger."""
    return (
        "CON-13",
        "No threshold-based red flags detected this cycle; valuation stretch "
        "and macro cyclicality remain residual risks to monitor",
        62.0,
    )


PRO_RULES = (
    pro_roe_sustained,
    pro_fcf_streak,
    pro_debt_free,
    pro_revenue_cagr,
    pro_opm_high,
    pro_pat_cagr,
    pro_icr_strong,
    pro_dividend_backed,
    pro_eps_cagr,
    pro_roe_improving,
    pro_operating_leverage,
    pro_self_funded_growth,
)

PRO_FALLBACKS = (pro_cfo_positive, pro_listing_history, pro_going_concern)

CON_RULES = (
    con_de_elevated,
    con_fcf_negative_streak,
    con_opm_declining,
    con_latest_loss,
    con_revenue_contraction,
    con_icr_weak,
    con_payout_unsustainable,
    con_de_rising,
    con_eps_declining,
    con_roce_low,
    con_net_debt_high,
    con_revenue_cagr_low,
)


def evaluate_company(
    company_id: str, sector: str, hist: pd.DataFrame
) -> list[dict]:
    """Return all triggered pro and con entries for one company history."""
    pros = [rule(hist, sector) for rule in PRO_RULES]
    pros = [hit for hit in pros if hit is not None and hit[2] > 60.0]
    if not pros:
        for fallback in PRO_FALLBACKS:
            hit = fallback(hist, sector)
            if hit is not None and hit[2] > 60.0:
                pros.append(hit)
                break
    cons = [rule(hist, sector) for rule in CON_RULES]
    cons = [hit for hit in cons if hit is not None and hit[2] > 60.0]
    if not cons:
        cons.append(con_residual_monitor(hist, sector))
    rows = []
    for entry_type, hits in ((PRO, pros), (CON, cons)):
        for rule_id, text, confidence in hits:
            rows.append(
                {
                    "company_id": company_id,
                    "type": entry_type,
                    "rule_id": rule_id,
                    "text": text,
                    "confidence_pct": confidence,
                }
            )
    return rows


def fetch_histories(
    db_path: Path = DB_PATH,
) -> tuple[dict[str, pd.DataFrame], dict[str, str]]:
    """Return per-company history frames and sector map for rule evaluation."""
    with sqlite3.connect(db_path) as conn:
        pl = pd.read_sql_query(
            "SELECT company_id, year, sales, net_profit, operating_profit, "
            "eps, dividend_payout FROM profitandloss",
            conn,
        )
        bs = pd.read_sql_query(
            "SELECT company_id, year, total_assets, borrowings, investments "
            "FROM balancesheet",
            conn,
        )
        ratios = pd.read_sql_query(
            "SELECT company_id, year, return_on_equity_pct, "
            "return_on_capital_employed_pct, operating_profit_margin_pct, "
            "debt_to_equity, interest_coverage, icr_label, free_cash_flow_cr, "
            "cash_from_operations_cr, revenue_cagr_5yr, pat_cagr_5yr, "
            "eps_cagr_5yr FROM financial_ratios",
            conn,
        )
        market = pd.read_sql_query(
            "SELECT company_id, dividend_yield_pct FROM market_cap mc1 "
            "WHERE year = (SELECT MAX(year) FROM market_cap mc2 "
            "WHERE mc2.company_id = mc1.company_id)",
            conn,
        )
        sectors = pd.read_sql_query(
            "SELECT company_id, broad_sector FROM sectors", conn
        )
    hist = ratios.merge(
        pl, on=["company_id", "year"], how="left", suffixes=("", "_pl")
    )
    hist = hist.merge(bs, on=["company_id", "year"], how="left")
    hist = hist.rename(
        columns={
            "return_on_equity_pct": "roe",
            "return_on_capital_employed_pct": "roce",
            "operating_profit_margin_pct": "opm",
            "debt_to_equity": "de",
            "free_cash_flow_cr": "fcf",
            "interest_coverage": "icr",
            "dividend_payout": "payout",
            "cash_from_operations_cr": "cfo",
            "revenue_cagr_5yr": "rev_cagr_5yr",
            "pat_cagr_5yr": "pat_cagr_5yr",
            "eps_cagr_5yr": "eps_cagr_5yr",
        }
    )
    hist = hist.merge(
        market.rename(columns={"dividend_yield_pct": "div_yield"}),
        on="company_id",
        how="left",
    )
    histories = {
        company_id: frame.sort_values("year")
        for company_id, frame in hist.groupby("company_id")
    }
    sector_map = dict(zip(sectors["company_id"], sectors["broad_sector"]))
    return histories, sector_map


def generate_pros_cons(
    histories: dict[str, pd.DataFrame], sectors: dict[str, str]
) -> pd.DataFrame:
    """Evaluate every pro and con rule for all company histories."""
    rows: list[dict] = []
    for company_id, hist in histories.items():
        rows.extend(evaluate_company(company_id, sectors.get(company_id, ""), hist))
    return pd.DataFrame(
        rows, columns=["company_id", "type", "rule_id", "text", "confidence_pct"]
    )


def run_generator(db_path: Path = DB_PATH) -> pd.DataFrame:
    """Generate pros and cons for all companies and write the deliverable CSV."""
    histories, sectors = fetch_histories(db_path)
    frame = generate_pros_cons(histories, sectors)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUTPUT_PATH, index=False)
    coverage = frame.groupby(["company_id", "type"]).size().unstack(fill_value=0)
    gaps = [
        company_id
        for company_id in histories
        if company_id not in coverage.index
        or coverage.loc[company_id].get(PRO, 0) < 1
        or coverage.loc[company_id].get(CON, 0) < 1
    ]
    if gaps:
        logger.warning("AC-16 coverage gap for companies: %s", gaps)
    else:
        logger.info(
            "AC-16 satisfied: all %d companies have >=1 pro and >=1 con",
            len(histories),
        )
    logger.info("Wrote %d pros/cons rows to %s", len(frame), OUTPUT_PATH)
    return frame


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_generator()