import logging

from src.etl.loader import connect_db
from src.settings import get_settings

logger = logging.getLogger(__name__)


def review_random_companies(conn, n=5):
    tickers = [
        r[0]
        for r in conn.execute(
            "SELECT id FROM companies ORDER BY RANDOM() LIMIT ?", (n,)
        )
    ]
    logger.info("Reviewing %d random companies: %s", n, tickers)
    for ticker in tickers:
        logger.info("--- %s ---", ticker)
        for table in ("profitandloss", "balancesheet", "cashflow"):
            years = [
                r[0]
                for r in conn.execute(
                    f"SELECT year FROM {table} WHERE company_id = ? ORDER BY year",
                    (ticker,),
                )
            ]
            logger.info("  %s: %d years %s", table, len(years), years)
        bs = conn.execute(
            "SELECT year, total_assets, total_liabilities FROM balancesheet WHERE company_id = ? ORDER BY year DESC LIMIT 1",
            (ticker,),
        ).fetchone()
        if bs and bs[1] is not None and bs[2] is not None:
            logger.info(
                "  Latest BS (%s): Assets=%.1f, Liab=%.1f, Diff=%.1f",
                bs[0],
                bs[1],
                bs[2],
                bs[1] - bs[2],
            )


def review_coverage(conn):
    query = """
        WITH pl AS (SELECT company_id, COUNT(DISTINCT year) AS yrs FROM profitandloss GROUP BY company_id),
             bs AS (SELECT company_id, COUNT(DISTINCT year) AS yrs FROM balancesheet GROUP BY company_id),
             cf AS (SELECT company_id, COUNT(DISTINCT year) AS yrs FROM cashflow GROUP BY company_id)
        SELECT c.id, COALESCE(pl.yrs, 0), COALESCE(bs.yrs, 0), COALESCE(cf.yrs, 0)
        FROM companies c
        LEFT JOIN pl ON c.id = pl.company_id
        LEFT JOIN bs ON c.id = bs.company_id
        LEFT JOIN cf ON c.id = cf.company_id
    """
    coverage = conn.execute(query).fetchall()
    total = len(coverage)
    under_5 = [r for r in coverage if min(r[1], r[2], r[3]) < 5]
    over_10 = [r for r in coverage if min(r[1], r[2], r[3]) >= 10]

    logger.info("Total companies: %d", total)
    logger.info("Companies with < 5 years in any time-series table: %d", len(under_5))
    if under_5:
        logger.info("  Tickers: %s", [r[0] for r in under_5])

    pct_10 = (len(over_10) / total) * 100 if total else 0
    logger.info(
        "Companies with >= 10 years in all time-series tables: %d (%.1f%%) [AC-02 gate]",
        len(over_10),
        pct_10,
    )


def review_anomalies(conn):
    neg_sales = conn.execute("""
        SELECT p.company_id, p.year, p.sales, s.broad_sector 
        FROM profitandloss p 
        JOIN sectors s ON p.company_id = s.company_id 
        WHERE p.sales <= 0 AND s.broad_sector != 'Financials'
    """).fetchall()
    logger.info("Non-financial companies with sales <= 0: %d", len(neg_sales))
    for row in neg_sales[:5]:
        logger.info("  %s", row)


if __name__ == "__main__":
    logging.basicConfig(level=get_settings().log_level, format="%(message)s")
    conn = connect_db()
    try:
        review_random_companies(conn)
        review_coverage(conn)
        review_anomalies(conn)
    finally:
        conn.close()
