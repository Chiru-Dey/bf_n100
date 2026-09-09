SELECT 'companies' AS table_name, COUNT(*) AS row_count FROM companies
UNION ALL SELECT 'profitandloss', COUNT(*) FROM profitandloss
UNION ALL SELECT 'balancesheet', COUNT(*) FROM balancesheet
UNION ALL SELECT 'cashflow', COUNT(*) FROM cashflow
UNION ALL SELECT 'analysis', COUNT(*) FROM analysis
UNION ALL SELECT 'documents', COUNT(*) FROM documents
UNION ALL SELECT 'prosandcons', COUNT(*) FROM prosandcons
UNION ALL SELECT 'sectors', COUNT(*) FROM sectors
UNION ALL SELECT 'stock_prices', COUNT(*) FROM stock_prices
UNION ALL SELECT 'market_cap', COUNT(*) FROM market_cap;

SELECT 'profitandloss.sales' AS column_ref, COUNT(*) AS nulls FROM profitandloss WHERE sales IS NULL
UNION ALL SELECT 'profitandloss.net_profit', COUNT(*) FROM profitandloss WHERE net_profit IS NULL
UNION ALL SELECT 'profitandloss.eps', COUNT(*) FROM profitandloss WHERE eps IS NULL
UNION ALL SELECT 'balancesheet.total_assets', COUNT(*) FROM balancesheet WHERE total_assets IS NULL
UNION ALL SELECT 'balancesheet.total_liabilities', COUNT(*) FROM balancesheet WHERE total_liabilities IS NULL
UNION ALL SELECT 'cashflow.operating_activity', COUNT(*) FROM cashflow WHERE operating_activity IS NULL
UNION ALL SELECT 'cashflow.net_cash_flow', COUNT(*) FROM cashflow WHERE net_cash_flow IS NULL
UNION ALL SELECT 'companies.face_value', COUNT(*) FROM companies WHERE face_value IS NULL;

SELECT year, COUNT(*) AS row_count
FROM profitandloss
GROUP BY year
ORDER BY year;

WITH pl AS (
    SELECT company_id, COUNT(DISTINCT year) AS yrs FROM profitandloss GROUP BY company_id
),
bs AS (
    SELECT company_id, COUNT(DISTINCT year) AS yrs FROM balancesheet GROUP BY company_id
),
cf AS (
    SELECT company_id, COUNT(DISTINCT year) AS yrs FROM cashflow GROUP BY company_id
)
SELECT c.id, COALESCE(pl.yrs, 0) AS pl_years, COALESCE(bs.yrs, 0) AS bs_years, COALESCE(cf.yrs, 0) AS cf_years
FROM companies c
LEFT JOIN pl ON pl.company_id = c.id
LEFT JOIN bs ON bs.company_id = c.id
LEFT JOIN cf ON cf.company_id = c.id
ORDER BY pl_years, c.id;

WITH pl AS (
    SELECT company_id, COUNT(DISTINCT year) AS yrs FROM profitandloss GROUP BY company_id
),
bs AS (
    SELECT company_id, COUNT(DISTINCT year) AS yrs FROM balancesheet GROUP BY company_id
),
cf AS (
    SELECT company_id, COUNT(DISTINCT year) AS yrs FROM cashflow GROUP BY company_id
)
SELECT c.id
FROM companies c
LEFT JOIN pl ON pl.company_id = c.id
LEFT JOIN bs ON bs.company_id = c.id
LEFT JOIN cf ON cf.company_id = c.id
WHERE COALESCE(pl.yrs, 0) < 5 OR COALESCE(bs.yrs, 0) < 5 OR COALESCE(cf.yrs, 0) < 5;

SELECT broad_sector, COUNT(*) AS company_count
FROM sectors
GROUP BY broad_sector
ORDER BY company_count DESC;

SELECT p.company_id, p.year, p.sales
FROM profitandloss p
JOIN (
    SELECT company_id, MAX(year) AS latest
    FROM profitandloss
    GROUP BY company_id
) m ON m.company_id = p.company_id AND m.latest = p.year
ORDER BY p.sales DESC
LIMIT 10;

SELECT company_id, year, total_assets, total_liabilities
FROM balancesheet
WHERE total_assets IS NOT NULL AND total_assets != 0
  AND ABS(total_assets - total_liabilities) / ABS(total_assets) >= 0.01
ORDER BY ABS(total_assets - total_liabilities) / ABS(total_assets) DESC;

SELECT COUNT(*) AS companies_with_60_month_price_history
FROM (
    SELECT company_id
    FROM stock_prices
    GROUP BY company_id
    HAVING COUNT(*) = 60
);

SELECT company_id, year, COUNT(*) AS duplicates
FROM profitandloss
GROUP BY company_id, year
HAVING COUNT(*) > 1;