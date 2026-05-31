-- =====================================================================
-- Meridian Move — Warehouse Star Schema DDL
-- Target: Microsoft Fabric Warehouse (wh_meridian)
-- Author: Portfolio Project
-- Purpose: Create dimensional star schema for Segment P&L dashboard
--
-- Design Notes:
--   - Fabric Warehouse does not enforce PRIMARY KEY / FOREIGN KEY
--     constraints (distributed system trade-off). Constraints below
--     are documented via NOT NULL and naming convention.
--   - DECIMAL(18,2) chosen for financial amounts — avoids floating-point
--     precision issues common in finance calculations.
--   - Amount stored in thousands (RM '000) — display unit switching
--     is handled downstream in Power BI via DAX.
--   - Date grain is monthly (month-end) — matches management reporting
--     cadence. Use date_key (YYYYMM integer) for fast joins.
-- =====================================================================

-- ==================== DIMENSION TABLES ====================

-- dim_date: Monthly grain date dimension
-- Grain: one row per month-end date
CREATE TABLE dbo.dim_date (
    date_key            INT             NOT NULL,  -- YYYYMM (e.g., 202512)
    full_date           DATE            NOT NULL,  -- actual month-end date
    year                INT             NOT NULL,
    quarter             INT             NOT NULL,  -- 1-4
    quarter_label       VARCHAR(20)     NOT NULL,  -- "Q4 2025"
    month_number        INT             NOT NULL,  -- 1-12
    month_name          VARCHAR(10)     NOT NULL,  -- "Dec"
    month_year_label    VARCHAR(20)     NOT NULL,  -- "Dec 2025"
    fiscal_year         INT             NOT NULL,  -- Meridian Move FY = calendar year
    is_quarter_end      BIT             NOT NULL,
    is_year_end         BIT             NOT NULL
);

-- dim_segment: 4 business segments
-- Grain: one row per operating segment
CREATE TABLE dbo.dim_segment (
    segment_key         INT             NOT NULL,
    segment_name        VARCHAR(50)     NOT NULL,  -- Postal, Aviation, Logistics, Retail
    segment_description VARCHAR(200)    NOT NULL,
    display_order       INT             NOT NULL   -- Controls segment order in visuals
);

-- dim_entity: 8 legal entities, rolling up to segments
-- Grain: one row per legal entity
CREATE TABLE dbo.dim_entity (
    entity_key          INT             NOT NULL,
    entity_code         VARCHAR(10)     NOT NULL,  -- 3-letter code (MPS, MAC, etc.)
    entity_name         VARCHAR(100)    NOT NULL,
    segment_key         INT             NOT NULL,  -- FK to dim_segment
    entity_type         VARCHAR(20)     NOT NULL,  -- Operating, Holding, etc.
    is_active           BIT             NOT NULL
);

-- dim_account: Management P&L chart of accounts
-- Grain: one row per management P&L line item
CREATE TABLE dbo.dim_account (
    account_key         INT             NOT NULL,
    account_code        VARCHAR(10)     NOT NULL,  -- 4-digit code (4100, 5110, etc.)
    account_name        VARCHAR(100)    NOT NULL,
    account_category    VARCHAR(30)     NOT NULL,  -- Revenue, Direct Cost, Staff, OPEX, Below-Line
    account_subcategory VARCHAR(30)     NOT NULL,  -- Finer categorization
    pnl_display_order   INT             NOT NULL,  -- Row order in P&L display
    is_revenue_flag     BIT             NOT NULL,  -- TRUE for revenue accounts
    is_cost_flag        BIT             NOT NULL   -- TRUE for cost accounts
);

-- dim_scenario: Actual / Budget / Forecast / Prior Year
-- Grain: one row per scenario type
CREATE TABLE dbo.dim_scenario (
    scenario_key        INT             NOT NULL,
    scenario_name       VARCHAR(20)     NOT NULL,  -- Actual, Budget, Forecast, Prior Year
    is_comparable_flag  BIT             NOT NULL   -- All currently TRUE; placeholder for future
);

-- dim_service_tier: Parcel delivery service tiers
-- Grain: one row per service tier
CREATE TABLE dbo.dim_service_tier (
    service_tier_key    INT             NOT NULL,
    tier_name           VARCHAR(20)     NOT NULL,  -- Standard, Express, Next-Day
    target_sla_hours    INT             NOT NULL   -- SLA commitment in hours
);

-- dim_metric 
-- metric registry
CREATE TABLE dbo.dim_metric (
    metric_id           INT             NOT NULL,
    metric_name         VARCHAR(100)    NOT NULL,
    display_name        VARCHAR(100)    NOT NULL,
    display_order       INT             NOT NULL,
    metric_type         VARCHAR(30)     NOT NULL,
    pnl_section         VARCHAR(30)     NOT NULL,
    sign_convention     VARCHAR(20)     NOT NULL,
    unit_type           VARCHAR(30)     NOT NULL,
    decimal_places      INT             NOT NULL,
    format_string       VARCHAR(100)    NOT NULL,
    dax_reference       VARCHAR(100)    NOT NULL,
    description         VARCHAR(500)    NOT NULL,
    is_kpi              VARCHAR(10)     NOT NULL,
    category_group      VARCHAR(30)     NOT NULL
);

-- ==================== FACT TABLES ====================

-- fact_financials: Main financial fact table
-- Grain: one row per month per entity per account per scenario
-- Expected row count: 36 months x 8 entities x ~30 accounts x 4 scenarios
--                  =~ 35,000 rows (actual: 15,048 due to sparse account/entity matrix)
CREATE TABLE dbo.fact_financials (
    date_key                INT             NOT NULL,  -- FK to dim_date
    entity_key              INT             NOT NULL,  -- FK to dim_entity
    segment_key             INT             NOT NULL,  -- FK to dim_segment (denormalized for speed)
    account_key             INT             NOT NULL,  -- FK to dim_account
    scenario_key            INT             NOT NULL,  -- FK to dim_scenario
    amount_myr_thousands    DECIMAL(18,2)   NOT NULL   -- Amount in RM '000
);

-- fact_parcel_operations: Operational parcel metrics
-- Grain: one row per month per parcel-handling entity per service tier
-- Purpose: Enables parcel yield analysis (volume vs revenue per parcel)
CREATE TABLE dbo.fact_parcel_operations (
    date_key                INT             NOT NULL,  -- FK to dim_date
    entity_key              INT             NOT NULL,  -- FK to dim_entity (parcel entities only)
    service_tier_key        INT             NOT NULL,  -- FK to dim_service_tier
    parcels_delivered       INT             NOT NULL,  -- Volume metric
    gross_revenue_myr       DECIMAL(18,2)   NOT NULL,  -- Before discounts (in full RM, not thousands)
    net_revenue_myr         DECIMAL(18,2)   NOT NULL,  -- After discounts
    variable_cost_myr       DECIMAL(18,2)   NOT NULL   -- Linehaul + last-mile variable cost
);

-- ==================== COMMENTARY TABLE ====================

-- commentary_placeholder: Pre-written commentary by segment/period
-- Purpose: Mocks the Power Apps writeback feature in the final dashboard
CREATE TABLE dbo.commentary_placeholder (
    entity_key          INT             NOT NULL,
    date_key            INT             NOT NULL,
    commentary_text     VARCHAR(1000)   NOT NULL,
    commentary_author   VARCHAR(50)     NOT NULL,
    commentary_date     DATE            NOT NULL
);

-- ==================== VALIDATION ====================

-- Verify all 9 tables were created successfully
SELECT
    TABLE_NAME,
    (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS c
     WHERE c.TABLE_NAME = t.TABLE_NAME) AS column_count
FROM INFORMATION_SCHEMA.TABLES t
WHERE TABLE_TYPE = 'BASE TABLE'
ORDER BY TABLE_NAME;
