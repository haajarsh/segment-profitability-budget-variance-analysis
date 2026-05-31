"""
===============================================================================
Meridian Move — Finance Data Generator
===============================================================================
Purpose:
    Generate 36 months of realistic synthetic financial data for a fictitious
    regional postal & logistics group called "Meridian Move Berhad".

    The data is shaped to tell a real business story when visualized:
        - Postal segment is structurally declining (~3% per year)
        - Parcel volumes growing strongly BUT yield (revenue per parcel) falling
        - Aviation is the profitable bright spot, but volatile
        - Logistics is loss-making with occasional maintenance spikes
        - Retail is slowly improving toward breakeven
        - Budgets are consistently more optimistic than actuals

Output:
    Seven CSV files in the /output folder, ready to be loaded into DuckDB:
        - dim_date.csv
        - dim_entity.csv
        - dim_segment.csv
        - dim_account.csv
        - dim_scenario.csv
        - dim_service_tier.csv
        - fact_financials.csv
        - fact_parcel_operations.csv
        - commentary_placeholder.csv

How to run:
    python generate_meridian_data.py

Learning notes (for Python beginners):
    - We use "pandas" to handle tabular data — think of it as Excel in code.
    - "numpy" gives us random numbers and math functions.
    - "datetime" handles dates properly (don't use strings for dates!).
    - The `random.seed(42)` line makes the data reproducible — the same
      "random" numbers every time you run the script. Essential for a
      portfolio project so reviewers see consistent results.
===============================================================================
"""

import os
import random
from datetime import date
from dataclasses import dataclass

import numpy as np
import pandas as pd

# -----------------------------------------------------------------------------
# CONFIGURATION — change these if you want to tweak the dataset
# -----------------------------------------------------------------------------
OUTPUT_DIR = "output"
START_YEAR = 2023
END_YEAR = 2025          # inclusive → 36 months total (Jan 2023 – Dec 2025)
REPORTING_CURRENCY = "MYR"
RANDOM_SEED = 42         # Reproducibility — don't change unless you want different data

# Seed both random libraries so results are identical every run
random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)


# -----------------------------------------------------------------------------
# 1. DIM_DATE — Calendar dimension
# -----------------------------------------------------------------------------
# A proper date dimension is non-negotiable for finance reporting.
# Power BI's auto-date/time features are limited — a real dim_date table
# gives you full control over fiscal periods, YoY comparisons, and custom
# period logic.
# -----------------------------------------------------------------------------
def build_dim_date():
    """Build a monthly grain date dimension from START_YEAR to END_YEAR."""
    # We build at month-end grain because finance reports monthly, not daily.
    # (If you ever need daily grain, swap 'M' for 'D' in the date_range.)
    dates = pd.date_range(
        start=f"{START_YEAR}-01-31",
        end=f"{END_YEAR}-12-31",
        freq="ME"  # 'ME' = Month End (pandas 2.x syntax)
    )

    df = pd.DataFrame({"full_date": dates})
    df["date_key"] = df["full_date"].dt.strftime("%Y%m").astype(int)  # e.g., 202301
    df["year"] = df["full_date"].dt.year
    df["quarter"] = df["full_date"].dt.quarter
    df["quarter_label"] = "Q" + df["quarter"].astype(str) + " " + df["year"].astype(str)
    df["month_number"] = df["full_date"].dt.month
    df["month_name"] = df["full_date"].dt.strftime("%b")  # Jan, Feb, Mar...
    df["month_year_label"] = df["full_date"].dt.strftime("%b %Y")  # Jan 2023
    df["fiscal_year"] = df["year"]  # Calendar = Fiscal for Meridian Move
    df["is_quarter_end"] = df["month_number"].isin([3, 6, 9, 12])
    df["is_year_end"] = df["month_number"] == 12

    # Reorder columns for readability
    df = df[[
        "date_key", "full_date", "year", "quarter", "quarter_label",
        "month_number", "month_name", "month_year_label",
        "fiscal_year", "is_quarter_end", "is_year_end"
    ]]
    return df


# -----------------------------------------------------------------------------
# 2. DIM_SEGMENT — The 4 business segments
# -----------------------------------------------------------------------------
def build_dim_segment():
    """Four operating segments rolling up to Group."""
    data = [
        {"segment_key": 1, "segment_name": "Postal",
         "segment_description": "Mail, direct mail, and postal services",
         "display_order": 1},
        {"segment_key": 2, "segment_name": "Aviation",
         "segment_description": "Cargo handling, engineering, in-flight catering",
         "display_order": 2},
        {"segment_key": 3, "segment_name": "Logistics",
         "segment_description": "3PL, freight forwarding, marine logistics",
         "display_order": 3},
        {"segment_key": 4, "segment_name": "Retail",
         "segment_description": "Retail outlets, digital services, financial products",
         "display_order": 4},
    ]
    return pd.DataFrame(data)


# -----------------------------------------------------------------------------
# 3. DIM_ENTITY — Legal entities rolling up to segments
# -----------------------------------------------------------------------------
# 8 legal entities, 2 per segment. Names reflect the "Meridian Move" branding.
# In real life, "Meridian" would be the group holding company and each subsidiary
# would have its own local registration.
# -----------------------------------------------------------------------------
def build_dim_entity():
    """Eight legal entities under Meridian Move Berhad."""
    data = [
        # Postal segment
        {"entity_key": 1, "entity_code": "MPS", "entity_name": "Meridian Postal Services",
         "segment_key": 1, "entity_type": "Operating", "is_active": True},
        {"entity_key": 2, "entity_code": "MDM", "entity_name": "Meridian Direct Mail",
         "segment_key": 1, "entity_type": "Operating", "is_active": True},

        # Aviation segment
        {"entity_key": 3, "entity_code": "MAC", "entity_name": "Meridian Aviation Cargo",
         "segment_key": 2, "entity_type": "Operating", "is_active": True},
        {"entity_key": 4, "entity_code": "MIS", "entity_name": "Meridian Inflight Services",
         "segment_key": 2, "entity_type": "Operating", "is_active": True},

        # Logistics segment
        {"entity_key": 5, "entity_code": "MLG", "entity_name": "Meridian Logistics",
         "segment_key": 3, "entity_type": "Operating", "is_active": True},
        {"entity_key": 6, "entity_code": "MMR", "entity_name": "Meridian Marine",
         "segment_key": 3, "entity_type": "Operating", "is_active": True},

        # Retail segment
        {"entity_key": 7, "entity_code": "MRT", "entity_name": "Meridian Retail",
         "segment_key": 4, "entity_type": "Operating", "is_active": True},
        {"entity_key": 8, "entity_code": "MDS", "entity_name": "Meridian Digital Services",
         "segment_key": 4, "entity_type": "Operating", "is_active": True},
    ]
    return pd.DataFrame(data)


# -----------------------------------------------------------------------------
# 4. DIM_ACCOUNT — Management P&L structure
# -----------------------------------------------------------------------------
# ~30 accounts mapped into 5 categories. This mirrors how a real management P&L
# is structured: Revenue → Direct Costs → Staff → OPEX → Below-the-line.
# -----------------------------------------------------------------------------
def build_dim_account():
    """Management P&L account structure."""
    accounts = [
        # === REVENUE (positive = good) ===
        ("4100", "Postal Revenue", "Revenue", "Mail", 1, True, False),
        ("4200", "Parcel Revenue", "Revenue", "Parcel", 2, True, False),
        ("4300", "Cargo Revenue", "Revenue", "Aviation", 3, True, False),
        ("4310", "Catering Revenue", "Revenue", "Aviation", 4, True, False),
        ("4400", "Logistics Revenue", "Revenue", "Logistics", 5, True, False),
        ("4500", "Retail Revenue", "Revenue", "Retail", 6, True, False),
        ("4900", "Other Revenue", "Revenue", "Other", 7, True, False),

        # === DIRECT COSTS (variable with volume) ===
        ("5100", "Linehaul Cost", "Direct Cost", "Transport", 10, False, True),
        ("5110", "Last-Mile Delivery Cost", "Direct Cost", "Transport", 11, False, True),
        ("5120", "Fuel — Ground", "Direct Cost", "Transport", 12, False, True),
        ("5130", "Aviation Fuel", "Direct Cost", "Aviation", 13, False, True),
        ("5140", "Ground Handling", "Direct Cost", "Aviation", 14, False, True),
        ("5200", "Cost of Goods Sold — Retail", "Direct Cost", "Retail", 15, False, True),
        ("5300", "Subcontractor Costs", "Direct Cost", "Transport", 16, False, True),

        # === STAFF COSTS ===
        ("6100", "Operations Salaries", "Staff", "Salaries", 20, False, True),
        ("6200", "Corporate Salaries", "Staff", "Salaries", 21, False, True),
        ("6300", "Benefits & EPF", "Staff", "Benefits", 22, False, True),

        # === OPEX (fixed overheads) ===
        ("7100", "Facilities Rent", "OPEX", "Facilities", 30, False, True),
        ("7200", "Utilities", "OPEX", "Facilities", 31, False, True),
        ("7300", "IT & Software", "OPEX", "Technology", 32, False, True),
        ("7400", "Professional Fees", "OPEX", "Corporate", 33, False, True),
        ("7500", "Marketing", "OPEX", "Commercial", 34, False, True),
        ("7600", "Repairs & Maintenance", "OPEX", "Operations", 35, False, True),
        ("7700", "Insurance", "OPEX", "Corporate", 36, False, True),
        ("7800", "Depreciation & Amortization", "OPEX", "Non-Cash", 37, False, True),
        ("7900", "Other OPEX", "OPEX", "Other", 38, False, True),

        # === BELOW THE LINE ===
        ("8100", "Interest Expense", "Below-Line", "Finance", 50, False, True),
        ("8200", "FX Gain/Loss", "Below-Line", "Finance", 51, False, False),
        ("8900", "Tax Expense", "Below-Line", "Tax", 52, False, True),
    ]

    df = pd.DataFrame(accounts, columns=[
        "account_code", "account_name", "account_category",
        "account_subcategory", "pnl_display_order",
        "is_revenue_flag", "is_cost_flag"
    ])
    # Generate account_key as the row number + 1
    df.insert(0, "account_key", range(1, len(df) + 1))
    return df


# -----------------------------------------------------------------------------
# 5. DIM_SCENARIO — Actual / Budget / Forecast / Prior Year
# -----------------------------------------------------------------------------
def build_dim_scenario():
    data = [
        {"scenario_key": 1, "scenario_name": "Actual", "is_comparable_flag": True},
        {"scenario_key": 2, "scenario_name": "Budget", "is_comparable_flag": True},
        {"scenario_key": 3, "scenario_name": "Forecast", "is_comparable_flag": True},
        {"scenario_key": 4, "scenario_name": "Prior Year", "is_comparable_flag": True},
    ]
    return pd.DataFrame(data)


# -----------------------------------------------------------------------------
# 6. DIM_SERVICE_TIER — For parcel operations
# -----------------------------------------------------------------------------
def build_dim_service_tier():
    data = [
        {"service_tier_key": 1, "tier_name": "Standard", "target_sla_hours": 72},
        {"service_tier_key": 2, "tier_name": "Express", "target_sla_hours": 48},
        {"service_tier_key": 3, "tier_name": "Next-Day", "target_sla_hours": 24},
    ]
    return pd.DataFrame(data)


# -----------------------------------------------------------------------------
# 7. BUSINESS LOGIC — The "shape" of Meridian Move's P&L
# -----------------------------------------------------------------------------
# This is where the STORY lives. We define baseline monthly values per entity
# per account, then apply growth/decline trends, seasonality, noise, and
# specific "events" that make the dashboard interesting.
#
# All baseline values are in MYR '000 (thousands). They are multiplied by 1000
# in the output to give actual ringgit values, matching fact_parcel_operations
# convention. So baseline 12500 = output RM 12,500,000 (RM 12.5 million).
# -----------------------------------------------------------------------------

# Baseline monthly figures (Jan 2023 starting point) in MYR '000
# Structure: entity_code → account_code → monthly baseline
BASELINE_JAN_2023 = {
    # ===== MPS (Meridian Postal Services) — structurally declining =====
    "MPS": {
        "4100": 28000,   # Postal Revenue
        "5100": 8500,    # Linehaul
        "5110": 6200,    # Last-mile
        "5120": 1800,    # Fuel
        "5300": 2100,    # Subcontractors
        "6100": 8200,    # Operations salaries
        "6200": 1500,    # Corporate salaries
        "6300": 1800,    # Benefits
        "7100": 1200,    # Rent
        "7200": 450,     # Utilities
        "7300": 680,     # IT
        "7400": 220,     # Professional fees
        "7500": 180,     # Marketing
        "7600": 320,     # R&M
        "7700": 140,     # Insurance
        "7800": 1400,    # D&A
        "7900": 380,     # Other OPEX
        "8100": 420,     # Interest
    },
    # ===== MDM (Meridian Direct Mail) — small, stable =====
    "MDM": {
        "4100": 3200,
        "5100": 580,
        "5110": 420,
        "5120": 120,
        "6100": 680,
        "6200": 180,
        "6300": 150,
        "7100": 120,
        "7200": 45,
        "7300": 90,
        "7500": 380,    # Marketing-heavy (direct mail business)
        "7800": 85,
        "7900": 60,
    },
    # ===== MAC (Meridian Aviation Cargo) — profitable =====
    "MAC": {
        "4200": 4500,    # Some parcel handling through cargo
        "4300": 18500,   # Cargo revenue
        "5130": 6800,    # Aviation fuel
        "5140": 2400,    # Ground handling
        "5300": 1200,    # Subcontractors
        "6100": 3200,    # Ops salaries
        "6200": 850,
        "6300": 650,
        "7100": 580,
        "7200": 220,
        "7300": 420,
        "7400": 180,
        "7600": 680,    # Higher R&M for aviation
        "7700": 420,    # Higher insurance for aviation
        "7800": 1800,
        "7900": 180,
        "8100": 240,
    },
    # ===== MIS (Meridian Inflight Services) — catering, steady growth =====
    "MIS": {
        "4310": 8200,    # Catering revenue
        "5200": 3400,    # COGS (food)
        "6100": 1850,
        "6200": 320,
        "6300": 380,
        "7100": 420,
        "7200": 280,    # High utilities (kitchens)
        "7300": 120,
        "7600": 220,
        "7700": 85,
        "7800": 380,
        "7900": 140,
    },
    # ===== MLG (Meridian Logistics) — loss-making =====
    "MLG": {
        "4200": 6800,    # Parcel handling
        "4400": 9500,    # Logistics revenue
        "5100": 4200,    # Heavy linehaul
        "5110": 2800,
        "5120": 1400,
        "5300": 3200,    # Heavy subcontractor use
        "6100": 2800,
        "6200": 480,
        "6300": 420,
        "7100": 680,
        "7200": 180,
        "7300": 220,
        "7600": 420,
        "7700": 180,
        "7800": 850,
        "7900": 220,
        "8100": 380,
    },
    # ===== MMR (Meridian Marine) — volatile, maintenance-heavy =====
    "MMR": {
        "4400": 5200,    # Marine logistics revenue
        "5100": 1800,    # Transport
        "5300": 980,
        "6100": 1200,    # Crew salaries
        "6200": 220,
        "6300": 180,
        "7100": 180,
        "7200": 120,
        "7600": 680,    # HIGH R&M (vessel maintenance)
        "7700": 320,    # Marine insurance
        "7800": 1200,   # Heavy depreciation (vessels)
        "7900": 120,
        "8100": 420,
    },
    # ===== MRT (Meridian Retail) — near breakeven =====
    "MRT": {
        "4500": 7800,    # Retail revenue
        "5200": 4800,    # COGS
        "6100": 1400,
        "6200": 280,
        "6300": 220,
        "7100": 980,    # Lots of retail outlets = high rent
        "7200": 220,
        "7300": 180,
        "7500": 280,
        "7600": 120,
        "7800": 420,
        "7900": 180,
        "8100": 180,
    },
    # ===== MDS (Meridian Digital Services) — growing =====
    "MDS": {
        "4500": 1800,    # Digital services revenue
        "4900": 920,     # Other (digital certs, printing)
        "5200": 680,
        "6100": 820,
        "6200": 180,
        "6300": 140,
        "7100": 85,
        "7300": 380,    # Higher IT costs
        "7500": 120,
        "7800": 180,
        "7900": 80,
    },
}


# -----------------------------------------------------------------------------
# Monthly growth/decline patterns per entity (annual rate, compounded monthly)
# -----------------------------------------------------------------------------
ANNUAL_GROWTH_RATES = {
    # Postal declining, but parcel within MPS growing
    "MPS": {"default": -0.03, "4200": 0.15, "5110": 0.08, "5120": 0.05},
    "MDM": {"default": -0.05},                              # Direct mail declining faster
    "MAC": {"default": 0.04, "4300": 0.06, "5130": 0.05},  # Aviation growing healthily
    "MIS": {"default": 0.05, "4310": 0.07},                # Catering growing
    "MLG": {"default": 0.02, "4400": 0.03, "5100": 0.04},  # Logistics slow growth, cost growing faster
    "MMR": {"default": 0.01},                              # Marine flat
    "MRT": {"default": 0.01, "4500": 0.02},                # Retail slight growth
    "MDS": {"default": 0.12, "4500": 0.18, "4900": 0.15},  # Digital growing fast
}

# -----------------------------------------------------------------------------
# Seasonality — multiplicative factors applied to revenue accounts
# Dec/Nov = peak (e-commerce, year-end mailings), Feb = low
# -----------------------------------------------------------------------------
SEASONALITY_REVENUE = {
    1: 0.92,  2: 0.85,  3: 0.98,  4: 0.95,  5: 1.00,  6: 0.98,
    7: 1.02,  8: 1.00,  9: 1.05, 10: 1.08, 11: 1.18, 12: 1.25
}

SEASONALITY_COSTS = {
    1: 0.95,  2: 0.90,  3: 0.98,  4: 0.96,  5: 1.00,  6: 0.99,
    7: 1.01,  8: 1.00,  9: 1.03, 10: 1.06, 11: 1.12, 12: 1.15
}


def months_between(start_date, current_date):
    """How many months from start_date to current_date (0-indexed)."""
    return (current_date.year - start_date.year) * 12 + (current_date.month - start_date.month)


def apply_growth(baseline, annual_rate, month_offset):
    """Compound monthly growth from a baseline."""
    monthly_rate = (1 + annual_rate) ** (1 / 12) - 1
    return baseline * ((1 + monthly_rate) ** month_offset)


def add_noise(value, noise_pct=0.05):
    """Add random noise to make data look real, not mathematically perfect."""
    return value * np.random.uniform(1 - noise_pct, 1 + noise_pct)


# -----------------------------------------------------------------------------
# 8. BUILD FACT_FINANCIALS — The main fact table
# -----------------------------------------------------------------------------
def build_fact_financials(dim_date, dim_entity, dim_account, dim_scenario):
    """Generate Actual, Budget, Forecast, and Prior Year scenarios."""

    # Build lookup dictionaries for fast key resolution
    entity_lookup = dict(zip(dim_entity["entity_code"], dim_entity["entity_key"]))
    segment_lookup = dict(zip(dim_entity["entity_code"], dim_entity["segment_key"]))
    account_lookup = dict(zip(dim_account["account_code"], dim_account["account_key"]))

    rows = []
    start_date = date(START_YEAR, 1, 31)

    for _, date_row in dim_date.iterrows():
        current_date = date_row["full_date"].date()
        month_offset = months_between(start_date, current_date)
        month_num = date_row["month_number"]

        for entity_code, accounts_dict in BASELINE_JAN_2023.items():
            entity_key = entity_lookup[entity_code]
            segment_key = segment_lookup[entity_code]
            growth_rules = ANNUAL_GROWTH_RATES[entity_code]

            for account_code, baseline_value in accounts_dict.items():
                account_key = account_lookup[account_code]
                is_revenue = account_code.startswith("4")

                # Apply the right growth rate for this account
                growth_rate = growth_rules.get(account_code, growth_rules["default"])
                trended_value = apply_growth(baseline_value, growth_rate, month_offset)

                # Apply seasonality
                if is_revenue:
                    seasonal_value = trended_value * SEASONALITY_REVENUE[month_num]
                else:
                    seasonal_value = trended_value * SEASONALITY_COSTS[month_num]

                # ----- ACTUAL -----
                actual_value = add_noise(seasonal_value, 0.05)

                # Special event: MAC (Aviation Cargo) wins a bonus contract
                # in Q3 2024 — revenue spikes for 3 months
                if entity_code == "MAC" and account_code == "4300":
                    if current_date.year == 2024 and current_date.month in [7, 8, 9]:
                        actual_value *= 1.28  # 28% uplift

                # Special event: MMR (Marine) has a major dry-docking
                # in Q2 2024 — R&M expense spikes, revenue drops
                if entity_code == "MMR":
                    if current_date.year == 2024 and current_date.month in [4, 5, 6]:
                        if account_code == "4400":
                            actual_value *= 0.55  # Revenue drops — vessels out of service
                        if account_code == "7600":
                            actual_value *= 3.2   # R&M spikes hard

                # Special event: Parcel yield erosion in MPS accelerates in 2025
                # (this is the key story for the parcel economics page)
                if entity_code == "MPS" and account_code == "4200":
                    if current_date.year == 2025:
                        actual_value *= 0.94  # Price pressure dents revenue

                rows.append({
                    "date_key": date_row["date_key"],
                    "entity_key": entity_key,
                    "segment_key": segment_key,
                    "account_key": account_key,
                    "scenario_key": 1,  # Actual
                    "amount_myr": round(actual_value * 1000, 2)
                })

                # ----- BUDGET -----
                # Budgets are set in advance and tend to be optimistic:
                # revenue ~3–8% above what actuals end up being,
                # costs ~2–5% below what actuals end up being.
                # We model budget as a "clean" trended value + optimism bias.
                if is_revenue:
                    budget_value = seasonal_value * 1.05  # 5% more optimistic on revenue
                else:
                    budget_value = seasonal_value * 0.97  # 3% leaner cost assumption

                rows.append({
                    "date_key": date_row["date_key"],
                    "entity_key": entity_key,
                    "segment_key": segment_key,
                    "account_key": account_key,
                    "scenario_key": 2,  # Budget
                    "amount_myr": round(budget_value * 1000, 2)
                })

                # ----- FORECAST -----
                # Forecast is a rolling view — sits between Budget and Actual.
                # Conceptually: "we updated budget mid-year based on actuals to date"
                forecast_value = (actual_value * 0.6) + (budget_value * 0.4)
                rows.append({
                    "date_key": date_row["date_key"],
                    "entity_key": entity_key,
                    "segment_key": segment_key,
                    "account_key": account_key,
                    "scenario_key": 3,  # Forecast
                    "amount_myr": round(forecast_value * 1000, 2)
                })

    df = pd.DataFrame(rows)

    # -------------------------------------------------------------------------
    # ADD TAX & FX (post-processing)
    # -------------------------------------------------------------------------
    # Real P&Ls have Tax (8900) and FX Gain/Loss (8200) at the below-the-line
    # level. We compute these AFTER the main P&L is built because:
    #   - Tax is a function of profitability (no profit = no tax)
    #   - FX exposure varies by entity (international vs domestic)
    # This is more realistic than hardcoding monthly baseline figures.
    # -------------------------------------------------------------------------

    tax_fx_rows = build_tax_and_fx(df, dim_date, dim_entity, dim_account)
    df = pd.concat([df, tax_fx_rows], ignore_index=True)

    # ----- PRIOR YEAR scenario -----
    # Built by taking Actuals and shifting the date forward by 12 months.
    # This gives us a clean "prior year same period" comparison.
    pr = df[df["scenario_key"] == 1].copy()
    pr["date_key"] = pr["date_key"] + 100  # YYYYMM + 100 = next year same month
    pr["scenario_key"] = 4  # Prior Year

    # Only keep prior year rows that fall within our date window
    valid_date_keys = set(dim_date["date_key"])
    pr = pr[pr["date_key"].isin(valid_date_keys)]

    df = pd.concat([df, pr], ignore_index=True)
    return df


# -----------------------------------------------------------------------------
# 8b. BUILD TAX & FX — derived from P&L profitability
# -----------------------------------------------------------------------------
# Tax: Approximate corporate tax on positive PBT, by entity, monthly.
#      Malaysian corporate tax is 24% — we use 22% to account for typical
#      effective rate (some deductions, reliefs, etc.). Loss-making entities
#      pay no tax in the period.
#
# FX: Random monthly exposure for entities with international business.
#     Aviation & Logistics segments have FX (cargo, marine logistics).
#     Postal & Retail are domestic-only — no FX entries.
# -----------------------------------------------------------------------------

CORPORATE_TAX_RATE = 0.22  # 22% effective rate

# Which entities have FX exposure (and the typical monthly volatility in MYR '000)
FX_EXPOSURE = {
    "MAC": 180_000,  # Aviation Cargo — international shipments (RM, monthly volatility)
    "MIS": 60_000,   # Inflight Services — some imported food/equipment
    "MLG": 220_000,  # Logistics — international freight
    "MMR": 380_000,  # Marine — heavy USD exposure
}


def build_tax_and_fx(df, dim_date, dim_entity, dim_account):
    """Compute Tax and FX rows derived from existing P&L data.

    Approach:
        1. For each entity-month-scenario, compute pre-tax profit
        2. Generate FX gain/loss as random noise for exposed entities
        3. Compute tax as 22% of (pre-tax profit + FX) when positive

    Returns:
        DataFrame with same schema as fact_financials, containing only
        Tax (8900) and FX (8200) rows for Actual + Budget + Forecast.
    """
    # Lookups
    account_lookup = dict(zip(dim_account["account_code"], dim_account["account_key"]))
    entity_lookup = dict(zip(dim_entity["entity_code"], dim_entity["entity_key"]))
    entity_segment_lookup = dict(zip(dim_entity["entity_code"], dim_entity["segment_key"]))
    entity_code_by_key = {v: k for k, v in entity_lookup.items()}

    fx_account_key = account_lookup["8200"]
    tax_account_key = account_lookup["8900"]

    # Build account_category lookup for fast classification
    account_category_lookup = dict(
        zip(dim_account["account_key"], dim_account["account_category"])
    )
    cost_categories = {"Direct Cost", "Staff", "OPEX"}

    # Add entity_code column for filtering
    df_with_code = df.copy()
    df_with_code["entity_code"] = df_with_code["entity_key"].map(entity_code_by_key)
    df_with_code["account_category"] = df_with_code["account_key"].map(account_category_lookup)

    new_rows = []

    # Group by entity-date-scenario for efficient computation
    for entity_code, entity_key in entity_lookup.items():
        segment_key = entity_segment_lookup[entity_code]
        entity_data = df_with_code[df_with_code["entity_code"] == entity_code]

        if entity_data.empty:
            continue

        for date_key in entity_data["date_key"].unique():
            for scenario_key in [1, 2, 3]:  # Actual, Budget, Forecast
                period_data = entity_data[
                    (entity_data["date_key"] == date_key)
                    & (entity_data["scenario_key"] == scenario_key)
                ]
                if period_data.empty:
                    continue

                # Aggregate by category
                revenue = period_data[period_data["account_category"] == "Revenue"][
                    "amount_myr"
                ].sum()
                operating_cost = period_data[period_data["account_category"].isin(cost_categories)][
                    "amount_myr"
                ].sum()
                interest = period_data[period_data["account_category"] == "Below-Line"][
                    "amount_myr"
                ].sum()

                ebit = revenue - operating_cost
                pbt_before_fx = ebit - interest

                # ----- FX Gain/Loss -----
                fx_value = 0
                if entity_code in FX_EXPOSURE:
                    base_fx_volatility = FX_EXPOSURE[entity_code]
                    if scenario_key == 1:  # Actual — full randomness
                        fx_value = np.random.uniform(-base_fx_volatility, base_fx_volatility)
                    elif scenario_key == 2:  # Budget — assume zero FX
                        fx_value = 0
                    else:  # Forecast — dampened
                        fx_value = np.random.uniform(
                            -base_fx_volatility * 0.4,
                            base_fx_volatility * 0.4,
                        )

                    if fx_value != 0:
                        new_rows.append({
                            "date_key": int(date_key),
                            "entity_key": entity_key,
                            "segment_key": segment_key,
                            "account_key": fx_account_key,
                            "scenario_key": scenario_key,
                            "amount_myr": round(fx_value, 2),  # already in actuals
                        })

                pbt_with_fx = pbt_before_fx + fx_value

                # ----- Tax -----
                # Only profitable entities pay tax in the period
                if pbt_with_fx > 0:
                    effective_rate = CORPORATE_TAX_RATE * np.random.uniform(0.92, 1.08)
                    tax_amount = pbt_with_fx * effective_rate

                    new_rows.append({
                        "date_key": int(date_key),
                        "entity_key": entity_key,
                        "segment_key": segment_key,
                        "account_key": tax_account_key,
                        "scenario_key": scenario_key,
                        "amount_myr": round(tax_amount, 2),  # already in actuals
                    })

    return pd.DataFrame(new_rows)


# -----------------------------------------------------------------------------
# 9. BUILD FACT_PARCEL_OPERATIONS — Operational metrics for parcel segment
# -----------------------------------------------------------------------------
# This is where we make the "volume up, yield down" story visible at the
# operational level — the key insight the dashboard will surface.
# -----------------------------------------------------------------------------
def build_fact_parcel_operations(dim_date, dim_entity):
    """Build operational parcel data by service tier."""
    # Entities that handle parcels: MPS, MAC, MLG
    parcel_entities = {
        "MPS": {"base_volume": 1_200_000, "base_yield": 8.50},  # parcels/month, RM/parcel
        "MAC": {"base_volume":   180_000, "base_yield": 22.00},
        "MLG": {"base_volume":   480_000, "base_yield": 12.00},
    }

    service_tier_mix = {
        1: 0.65,  # Standard
        2: 0.25,  # Express
        3: 0.10,  # Next-Day
    }

    # Cost per parcel (varies by tier — faster = more expensive)
    cost_per_parcel_by_tier = {
        1: 5.80,   # Standard
        2: 9.20,   # Express
        3: 14.50,  # Next-Day
    }

    entity_lookup = dict(zip(dim_entity["entity_code"], dim_entity["entity_key"]))
    rows = []
    start_date = date(START_YEAR, 1, 31)

    for _, date_row in dim_date.iterrows():
        current_date = date_row["full_date"].date()
        month_offset = months_between(start_date, current_date)
        month_num = date_row["month_number"]

        for entity_code, params in parcel_entities.items():
            entity_key = entity_lookup[entity_code]

            # VOLUME: growing ~15% per year
            volume_growth = apply_growth(params["base_volume"], 0.15, month_offset)
            volume = volume_growth * SEASONALITY_REVENUE[month_num]

            # YIELD: declining ~5% per year (the critical business insight)
            yield_decline = apply_growth(params["base_yield"], -0.05, month_offset)

            # Cost per parcel inflating ~3% per year
            cost_inflation = apply_growth(1.0, 0.03, month_offset)

            for tier_key, mix_pct in service_tier_mix.items():
                tier_volume = int(volume * mix_pct * np.random.uniform(0.95, 1.05))

                # Yield varies by tier: Express/Next-Day command premium pricing
                tier_yield_multiplier = {1: 1.00, 2: 1.35, 3: 1.80}[tier_key]
                tier_yield = yield_decline * tier_yield_multiplier * np.random.uniform(0.97, 1.03)

                gross_revenue = tier_volume * tier_yield
                # Discounts: larger for Standard (commodity), smaller for Next-Day
                discount_rate = {1: 0.12, 2: 0.08, 3: 0.04}[tier_key]
                net_revenue = gross_revenue * (1 - discount_rate)

                variable_cost = tier_volume * cost_per_parcel_by_tier[tier_key] * cost_inflation

                rows.append({
                    "date_key": date_row["date_key"],
                    "entity_key": entity_key,
                    "service_tier_key": tier_key,
                    "parcels_delivered": tier_volume,
                    "gross_revenue_myr": round(gross_revenue, 2),
                    "net_revenue_myr": round(net_revenue, 2),
                    "variable_cost_myr": round(variable_cost, 2),
                })

    return pd.DataFrame(rows)


# -----------------------------------------------------------------------------
# 10. BUILD COMMENTARY PLACEHOLDER
# -----------------------------------------------------------------------------
def build_commentary(dim_date, dim_entity):
    """Pre-written commentary for the last 6 months — mocks the writeback feature."""
    commentaries = [
        ("MPS", 202510, "Postal volumes continue structural decline; parcel growth partially offsetting. Yield erosion persists.", "S. Tan", "2025-11-05"),
        ("MPS", 202511, "Peak season demand lifted parcel volumes 18% MoM, but yield per parcel fell 2.3% vs prior year.", "S. Tan", "2025-12-04"),
        ("MAC", 202510, "Cargo segment performing strongly; new Q3 2024 contract fully annualised. Margin ahead of budget.", "R. Lim", "2025-11-06"),
        ("MAC", 202511, "Aviation fuel costs increased 4% in month due to regional pricing; partially hedged.", "R. Lim", "2025-12-05"),
        ("MMR", 202510, "Marine fleet fully back in service post-dry-docking. Revenue recovery on track.", "A. Raj", "2025-11-05"),
        ("MLG", 202510, "Logistics margin under pressure — subcontractor cost inflation running ahead of price recovery.", "K. Wong", "2025-11-07"),
        ("MRT", 202510, "Retail footprint rationalisation completed; like-for-like sales up 3% YoY.", "J. Chen", "2025-11-05"),
        ("MDS", 202511, "Digital certificates volume up 22% YoY, driving segment profitability inflection.", "J. Chen", "2025-12-04"),
    ]
    entity_lookup = dict(zip(dim_entity["entity_code"], dim_entity["entity_key"]))

    rows = []
    for entity_code, date_key, text, author, date_written in commentaries:
        rows.append({
            "entity_key": entity_lookup[entity_code],
            "date_key": date_key,
            "commentary_text": text,
            "commentary_author": author,
            "commentary_date": date_written,
        })
    return pd.DataFrame(rows)


# -----------------------------------------------------------------------------
# MAIN — Orchestrate everything and write to CSV
# -----------------------------------------------------------------------------
def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("Building dimension tables...")
    dim_date = build_dim_date()
    dim_segment = build_dim_segment()
    dim_entity = build_dim_entity()
    dim_account = build_dim_account()
    dim_scenario = build_dim_scenario()
    dim_service_tier = build_dim_service_tier()

    print("Building fact_financials (this may take a few seconds)...")
    fact_financials = build_fact_financials(dim_date, dim_entity, dim_account, dim_scenario)

    print("Building fact_parcel_operations...")
    fact_parcel = build_fact_parcel_operations(dim_date, dim_entity)

    print("Building commentary...")
    commentary = build_commentary(dim_date, dim_entity)

    # Write everything to CSV
    outputs = {
        "dim_date.csv": dim_date,
        "dim_segment.csv": dim_segment,
        "dim_entity.csv": dim_entity,
        "dim_account.csv": dim_account,
        "dim_scenario.csv": dim_scenario,
        "dim_service_tier.csv": dim_service_tier,
        "fact_financials.csv": fact_financials,
        "fact_parcel_operations.csv": fact_parcel,
        "commentary_placeholder.csv": commentary,
    }

    print("\nWriting CSV files to ./output/ ...")
    for filename, df in outputs.items():
        path = os.path.join(OUTPUT_DIR, filename)
        df.to_csv(path, index=False)
        print(f"  {filename:35s} {len(df):>8,} rows")

    print(f"\nDone. {len(outputs)} files written to ./{OUTPUT_DIR}/")
    print("\nSanity check — Group P&L snapshot for Dec 2025 (Actual):")

    # Quick sanity check: join fact to dim and compute a Dec 2025 actual P&L
    snapshot = (
        fact_financials[
            (fact_financials["date_key"] == 202512) &
            (fact_financials["scenario_key"] == 1)
        ]
        .merge(dim_account[["account_key", "account_category"]], on="account_key")
        .groupby("account_category")["amount_myr"].sum()
        .round(0)
    )
    print(snapshot.to_string())

    revenue = snapshot.get("Revenue", 0)
    total_cost = snapshot.drop("Revenue", errors="ignore").sum()
    ebit = revenue - total_cost
    print(f"\n  Revenue total:   RM {revenue:>12,.0f}k")
    print(f"  Total costs:     RM {total_cost:>15,.0f}")
    print(f"  Implied EBIT:    RM {ebit:>15,.0f}  ({'loss' if ebit < 0 else 'profit'})")


if __name__ == "__main__":
    main()
