-- =====================================================================
-- Meridian Move — Updated fact_financials DDL
-- Change: amount_myr_thousands → amount_myr (now stores actuals, raw RM)
--
-- Run order:
--   1. DROP existing fact_financials table
--   2. CREATE with new column name
--   3. Reload via COPY INTO from refreshed CSV
-- =====================================================================

-- Step 1: Drop the existing table
DROP TABLE IF EXISTS dbo.fact_financials;

-- Step 2: Recreate with new column name
CREATE TABLE dbo.fact_financials (
    date_key                INT             NOT NULL,
    entity_key              INT             NOT NULL,
    segment_key             INT             NOT NULL,
    account_key             INT             NOT NULL,
    scenario_key            INT             NOT NULL,
    amount_myr              DECIMAL(18,2)   NOT NULL  -- Was: amount_myr_thousands
);

-- Step 3: Verify the new schema
SELECT COLUMN_NAME, DATA_TYPE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'fact_financials'
ORDER BY ORDINAL_POSITION;

-- Expected: 6 columns, last is amount_myr (DECIMAL)

-- Step 4: Reload from refreshed CSV
-- Replace <<YOUR_BASE_PATH>> with your ABFSS base path
COPY INTO dbo.fact_financials
FROM '<<YOUR_BASE_PATH>>fact_financials.csv'
WITH (
    FILE_TYPE = 'CSV',
    FIRSTROW = 2
);

-- Step 5: Verify row count and a sample sum
SELECT COUNT(*) AS total_rows FROM dbo.fact_financials;
-- Expected: 15,965

SELECT
    SUM(amount_myr) AS fy2025_total
FROM dbo.fact_financials f
INNER JOIN dbo.dim_account a ON f.account_key = a.account_key
INNER JOIN dbo.dim_date d ON f.date_key = d.date_key
WHERE d.year = 2025
  AND f.scenario_key = 1
  AND a.is_revenue_flag = 1;
-- Expected: ~1,224,320,754 (RM 1.22 billion)
