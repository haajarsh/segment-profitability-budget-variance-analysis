-- =====================================================================
-- Meridian Move — Data Validation & Business Story Queries
-- Target: Microsoft Fabric Warehouse (wh_meridian)
--
-- Purpose:
--   Validate the data tells the intended business story before
--   building Power BI semantic model and dashboard. Each query
--   maps to one of the five business questions in the project spec.
--
--   These queries also form the logical basis for corresponding
--   DAX measures in the semantic model.
-- =====================================================================

-- ==================== QUERY 1 ====================
-- Business Question: Is the Group loss-making, and by how much?
-- Dashboard equivalent: Group P&L Waterfall (Page 1)
-- =====================================================================

SELECT
    a.account_category,
    SUM(f.amount_myr_thousands) AS total_myr_thousands,
    SUM(f.amount_myr_thousands) / 1000.0 AS total_myr_millions
FROM dbo.fact_financials f
INNER JOIN dbo.dim_account a ON f.account_key = a.account_key
INNER JOIN dbo.dim_date d ON f.date_key = d.date_key
WHERE d.year = 2025
  AND f.scenario_key = 1  -- Actual
GROUP BY a.account_category
ORDER BY
    CASE a.account_category
        WHEN 'Revenue'     THEN 1
        WHEN 'Direct Cost' THEN 2
        WHEN 'Staff'       THEN 3
        WHEN 'OPEX'        THEN 4
        WHEN 'Below-Line'  THEN 5
    END;


-- ==================== QUERY 2 ====================
-- Business Question: Which segments are profitable and which are losing money?
-- Dashboard equivalent: Segment Performance Scorecard (Page 1/2)
-- =====================================================================

SELECT
    s.segment_name,
    d.year,
    SUM(CASE WHEN a.is_revenue_flag = 1
             THEN f.amount_myr_thousands
             ELSE 0 END) / 1000.0 AS revenue_myr_m,
    SUM(CASE WHEN a.is_cost_flag = 1 AND a.account_category != 'Below-Line'
             THEN f.amount_myr_thousands
             ELSE 0 END) / 1000.0 AS total_opex_myr_m,
    (SUM(CASE WHEN a.is_revenue_flag = 1 THEN f.amount_myr_thousands ELSE 0 END)
     - SUM(CASE WHEN a.is_cost_flag = 1 AND a.account_category != 'Below-Line'
                THEN f.amount_myr_thousands ELSE 0 END)) / 1000.0 AS ebit_myr_m
FROM dbo.fact_financials f
INNER JOIN dbo.dim_account a  ON f.account_key = a.account_key
INNER JOIN dbo.dim_date d     ON f.date_key = d.date_key
INNER JOIN dbo.dim_segment s  ON f.segment_key = s.segment_key
WHERE f.scenario_key = 1  -- Actual
GROUP BY s.segment_name, s.display_order, d.year
ORDER BY s.display_order, d.year;


-- ==================== QUERY 3 ====================
-- Business Question: Is parcel volume growth translating to margin growth?
-- Dashboard equivalent: Parcel Economics Page (Page 3) — HEADLINE INSIGHT
-- =====================================================================

SELECT
    d.year,
    SUM(fp.parcels_delivered) / 1000000.0                            AS volume_millions,
    SUM(fp.net_revenue_myr) / 1000000.0                              AS net_revenue_myr_m,
    SUM(fp.net_revenue_myr) / SUM(fp.parcels_delivered)              AS revenue_per_parcel_myr,
    SUM(fp.variable_cost_myr) / SUM(fp.parcels_delivered)            AS cost_per_parcel_myr,
    (SUM(fp.net_revenue_myr) - SUM(fp.variable_cost_myr))
        / SUM(fp.parcels_delivered)                                  AS contribution_margin_per_parcel_myr
FROM dbo.fact_parcel_operations fp
INNER JOIN dbo.dim_date d ON fp.date_key = d.date_key
GROUP BY d.year
ORDER BY d.year;


-- ==================== QUERY 4 ====================
-- Business Question: How are we performing against budget?
-- Dashboard equivalent: Budget vs Actual Variance Visual (Page 1/2)
-- =====================================================================

SELECT
    s.segment_name,
    SUM(CASE WHEN f.scenario_key = 1 AND a.is_revenue_flag = 1
             THEN f.amount_myr_thousands ELSE 0 END) / 1000.0 AS actual_myr_m,
    SUM(CASE WHEN f.scenario_key = 2 AND a.is_revenue_flag = 1
             THEN f.amount_myr_thousands ELSE 0 END) / 1000.0 AS budget_myr_m,
    (SUM(CASE WHEN f.scenario_key = 1 AND a.is_revenue_flag = 1
              THEN f.amount_myr_thousands ELSE 0 END)
     - SUM(CASE WHEN f.scenario_key = 2 AND a.is_revenue_flag = 1
                THEN f.amount_myr_thousands ELSE 0 END)) / 1000.0 AS variance_myr_m,
    ROUND(
        (SUM(CASE WHEN f.scenario_key = 1 AND a.is_revenue_flag = 1
                  THEN f.amount_myr_thousands ELSE 0 END)
         / NULLIF(SUM(CASE WHEN f.scenario_key = 2 AND a.is_revenue_flag = 1
                           THEN f.amount_myr_thousands ELSE 0 END), 0) - 1) * 100
    , 1) AS variance_pct
FROM dbo.fact_financials f
INNER JOIN dbo.dim_account a  ON f.account_key = a.account_key
INNER JOIN dbo.dim_date d     ON f.date_key = d.date_key
INNER JOIN dbo.dim_segment s  ON f.segment_key = s.segment_key
WHERE d.year = 2025
GROUP BY s.segment_name, s.display_order
ORDER BY s.display_order;


-- ==================== QUERY 5 ====================
-- Business Question: Can the dashboard surface unusual events?
-- Dashboard equivalent: Segment Deep-Dive (Page 2) with drill-down
-- Tests: Marine Q2 2024 dry-dock event (revenue collapse + R&M spike)
-- =====================================================================

SELECT
    d.month_year_label,
    SUM(CASE WHEN a.account_code = '4400'
             THEN f.amount_myr_thousands ELSE 0 END) AS revenue_k,
    SUM(CASE WHEN a.account_code = '7600'
             THEN f.amount_myr_thousands ELSE 0 END) AS repairs_maintenance_k,
    SUM(CASE WHEN a.is_revenue_flag = 1
             THEN f.amount_myr_thousands ELSE 0 END)
    - SUM(CASE WHEN a.is_cost_flag = 1 AND a.account_category != 'Below-Line'
             THEN f.amount_myr_thousands ELSE 0 END) AS ebit_k
FROM dbo.fact_financials f
INNER JOIN dbo.dim_account a  ON f.account_key = a.account_key
INNER JOIN dbo.dim_date d     ON f.date_key = d.date_key
INNER JOIN dbo.dim_entity e   ON f.entity_key = e.entity_key
WHERE e.entity_code = 'MMR'
  AND f.scenario_key = 1
  AND d.year = 2024
GROUP BY d.month_year_label, d.month_number, d.year
ORDER BY d.year, d.month_number;


-- ==================== QUERY 6 ====================
-- Business Question: What are our top 5 biggest budget misses?
-- Dashboard equivalent: "Top 5 Unfavorable Variances" visual (Page 2)
-- =====================================================================

SELECT TOP 5
    s.segment_name,
    a.account_name,
    SUM(CASE WHEN f.scenario_key = 1 THEN f.amount_myr_thousands ELSE 0 END) AS actual_k,
    SUM(CASE WHEN f.scenario_key = 2 THEN f.amount_myr_thousands ELSE 0 END) AS budget_k,
    SUM(CASE WHEN f.scenario_key = 1 THEN f.amount_myr_thousands ELSE 0 END)
    - SUM(CASE WHEN f.scenario_key = 2 THEN f.amount_myr_thousands ELSE 0 END) AS unfav_variance_k
FROM dbo.fact_financials f
INNER JOIN dbo.dim_account a  ON f.account_key = a.account_key
INNER JOIN dbo.dim_date d     ON f.date_key = d.date_key
INNER JOIN dbo.dim_segment s  ON f.segment_key = s.segment_key
WHERE d.year = 2025
  AND a.is_cost_flag = 1
  AND a.account_category != 'Below-Line'
GROUP BY s.segment_name, a.account_name
HAVING SUM(CASE WHEN f.scenario_key = 1 THEN f.amount_myr_thousands ELSE 0 END)
     - SUM(CASE WHEN f.scenario_key = 2 THEN f.amount_myr_thousands ELSE 0 END) > 0
ORDER BY unfav_variance_k DESC;


-- =====================================================================
-- End of validation queries.
-- If all six return sensible, story-aligned results, the warehouse
-- is ready for semantic modeling in Power BI.
-- =====================================================================
