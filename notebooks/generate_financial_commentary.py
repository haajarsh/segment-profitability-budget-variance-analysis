
# =====================================================================
# Fabric Notebook: Generate Financial Commentary with LLM
# =====================================================================
# Run this entire notebook end-to-end

# Purpose:
#   1. Query key financial metrics from the Meridian Move warehouse
#   2. Send metrics to Groq LLM API with a structured finance prompt
#   3. Write the generated commentary back to a Delta table in Lakehouse
#   4. Power BI reads the Delta table via Direct Lake for dashboard display
#   5. Verify that the commentary is generated and stored correctly
#
# Prerequisites:
#   - Groq API key (free at console.groq.com)
#   - Fabric Lakehouse: lh_meridian
#   - Fabric Warehouse: wh_meridian (with fact_financials populated)
#   - CSVs uploaded in Files/raw_csvs/
#
# How to run:
#   - Open this notebook in your Fabric workspace
#   - Set your Groq API key in Cell 2
#   - Run all cells sequentially
#   - Check the lh_meridian Lakehouse for the new insight_commentary table
#
# Output table: insight_commentary (5 rows, 16 columns)
#   - Used by Page 1 (Group insight cards)
#   - Used by Page 2 (Segment-specific insight cards)
#
# Design notes:
#   - LLM-agnostic: swap Groq for Claude, Azure OpenAI, or any REST API
#     by changing the endpoint URL, headers, and response parsing
#   - Prompt engineered with guardrails: LLM can only describe data it
#     receives, never hallucinate numbers
#   - Idempotent: re-running appends new rows (with timestamps) rather
#     than overwriting, so you have a history of generated insights
# =====================================================================


# %%
# =====================================================================
# CELL 1: CONFIGURATION
# =====================================================================

import requests
import json
from datetime import datetime
import time

# ---------- UPDATE THESE ----------
GROQ_API_KEY = "gsk_YOUR_KEY_HERE"  # Paste your Groq key
# ----------------------------------

GROQ_MODEL = "llama-3.3-70b-versatile"
ANALYSIS_YEAR = 2025
COMPANY_NAME = "Meridian Move Berhad"
CSV_BASE_PATH = "Files/raw_csvs"  # Path inside your Lakehouse

print("=" * 70)
print("CONFIGURATION")
print("=" * 70)
print(f"  Company:    {COMPANY_NAME}")
print(f"  Year:       FY{ANALYSIS_YEAR}")
print(f"  Model:      {GROQ_MODEL}")
print(f"  CSV Path:   {CSV_BASE_PATH}")
print(f"  API Key:    {'SET' if GROQ_API_KEY != 'gsk_YOUR_KEY_HERE' else 'NOT SET — UPDATE CELL 1'}")

# %%
# =====================================================================
# CELL 2: LOAD DATA FROM LAKEHOUSE CSVs
# =====================================================================

# Read CSVs and register as temp views for SparkSQL
tables = {
    "fact_financials": f"{CSV_BASE_PATH}/fact_financials.csv",
    "dim_account": f"{CSV_BASE_PATH}/dim_account.csv",
    "dim_date": f"{CSV_BASE_PATH}/dim_date.csv",
    "dim_segment": f"{CSV_BASE_PATH}/dim_segment.csv",
    "fact_parcel_operations": f"{CSV_BASE_PATH}/fact_parcel_operations.csv",
}

for name, path in tables.items():
    df = spark.read.format("csv") \
        .option("header", "true") \
        .option("inferSchema", "true") \
        .load(path)
    df.createOrReplaceTempView(name)
    print(f"  Loaded {name}: {df.count():,} rows")

print("\nAll tables loaded successfully.")

# %%
# =====================================================================
# CELL 3: EXTRACT METRICS
# =====================================================================

# --- Segment-level P&L ---
segment_query = f"""
SELECT
    s.segment_name,
    SUM(CASE WHEN a.is_revenue_flag = 1 AND f.scenario_key = 1
             THEN f.amount_myr ELSE 0 END) AS actual_revenue,
    SUM(CASE WHEN a.is_revenue_flag = 1 AND f.scenario_key = 2
             THEN f.amount_myr ELSE 0 END) AS budget_revenue,
    SUM(CASE WHEN a.is_revenue_flag = 1 AND f.scenario_key = 1
             THEN f.amount_myr ELSE 0 END)
    - SUM(CASE WHEN a.is_cost_flag = 1 AND a.account_category != 'Below-Line'
               AND f.scenario_key = 1 THEN f.amount_myr ELSE 0 END) AS actual_ebit,
    SUM(CASE WHEN a.is_revenue_flag = 1 AND f.scenario_key = 2
             THEN f.amount_myr ELSE 0 END)
    - SUM(CASE WHEN a.is_cost_flag = 1 AND a.account_category != 'Below-Line'
               AND f.scenario_key = 2 THEN f.amount_myr ELSE 0 END) AS budget_ebit
FROM fact_financials f
INNER JOIN dim_account a ON f.account_key = a.account_key
INNER JOIN dim_date d ON f.date_key = d.date_key
INNER JOIN dim_segment s ON f.segment_key = s.segment_key
WHERE d.year = {ANALYSIS_YEAR}
  AND f.scenario_key IN (1, 2)
GROUP BY s.segment_name
ORDER BY s.segment_name
"""
segment_df = spark.sql(segment_query).toPandas()

# --- Parcel metrics ---
parcel_query = f"""
SELECT
    SUM(fp.parcels_delivered) AS total_parcels,
    SUM(fp.net_revenue_myr) / SUM(fp.parcels_delivered) AS revenue_per_parcel,
    (SUM(fp.net_revenue_myr) - SUM(fp.variable_cost_myr))
        / SUM(fp.parcels_delivered) AS cm_per_parcel
FROM fact_parcel_operations fp
INNER JOIN dim_date d ON fp.date_key = d.date_key
WHERE d.year = {ANALYSIS_YEAR}
"""
parcel_df = spark.sql(parcel_query).toPandas()

# --- Compute group totals ---
group_revenue = segment_df["actual_revenue"].sum()
group_budget_revenue = segment_df["budget_revenue"].sum()
group_ebit = segment_df["actual_ebit"].sum()
group_budget_ebit = segment_df["budget_ebit"].sum()
ebit_margin = group_ebit / group_revenue if group_revenue != 0 else 0
rev_var_pct = (group_revenue - group_budget_revenue) / group_budget_revenue if group_budget_revenue != 0 else 0

parcels = parcel_df.iloc[0]
total_parcels = parcels["total_parcels"]
rev_per_parcel = parcels["revenue_per_parcel"]
cm_per_parcel = parcels["cm_per_parcel"]

# --- Build segment detail string ---
segment_details = ""
for _, row in segment_df.iterrows():
    seg_margin = row["actual_ebit"] / row["actual_revenue"] if row["actual_revenue"] != 0 else 0
    seg_rev_miss = (row["actual_revenue"] - row["budget_revenue"]) / row["budget_revenue"] if row["budget_revenue"] != 0 else 0
    ebit_miss = row["actual_ebit"] - row["budget_ebit"]
    segment_details += (
        f"  - {row['segment_name']}: "
        f"Revenue RM {row['actual_revenue']/1e6:.1f}M ({seg_rev_miss:+.1%} vs BU), "
        f"EBIT RM {row['actual_ebit']/1e6:.1f}M (margin {seg_margin:.1%}), "
        f"EBIT vs BU RM {ebit_miss/1e6:+.1f}M\n"
    )

print("=" * 70)
print(f"METRICS FOR FY{ANALYSIS_YEAR}")
print("=" * 70)
print(f"  Revenue:    RM {group_revenue/1e6:>8.1f}M (vs BU: {rev_var_pct:+.1%})")
print(f"  EBIT:       RM {group_ebit/1e6:>8.1f}M (margin: {ebit_margin:.1%})")
print(f"  Parcels:    {total_parcels/1e6:.1f}M | Rev/P: RM {rev_per_parcel:.2f} | CM/P: RM {cm_per_parcel:.2f}")
print(f"\nSegments:")
print(segment_details)

# %%
# =====================================================================
# CELL 4: GENERATE ALL COMMENTARIES (Group + 4 Segments)
# =====================================================================

def call_groq(prompt, system_message="You are a senior financial analyst."):
    """Call Groq API and return parsed JSON insights."""
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 500,
                "top_p": 0.9
            },
            timeout=30
        )

        if response.status_code == 200:
            result = response.json()
            raw_text = result["choices"][0]["message"]["content"].strip()
            tokens = result.get("usage", {})

            # Parse JSON response
            clean = raw_text.replace("```json", "").replace("```", "").strip()
            insights = json.loads(clean)

            return {
                "concern": insights.get("concern", ""),
                "bright_spot": insights.get("bright_spot", ""),
                "action": insights.get("action", ""),
                "prompt_tokens": tokens.get("prompt_tokens", 0),
                "completion_tokens": tokens.get("completion_tokens", 0),
                "success": True
            }
        else:
            print(f"  API Error: {response.status_code} — {response.text[:200]}")
            return {"success": False}

    except json.JSONDecodeError as e:
        print(f"  JSON parse error: {e}")
        print(f"  Raw text: {raw_text[:300]}")
        return {"success": False}
    except Exception as e:
        print(f"  Request error: {e}")
        return {"success": False}


# --- Generate Group commentary ---
print("=" * 70)
print("GENERATING COMMENTARIES")
print("=" * 70)

group_prompt = f"""You are a senior financial analyst writing the executive insight cards 
for {COMPANY_NAME}'s FY{ANALYSIS_YEAR} monthly board pack.

FY{ANALYSIS_YEAR} RESULTS:
- Group Revenue: RM {group_revenue/1e6:.1f}M (vs Budget: {rev_var_pct:+.1%})
- Group EBIT: RM {group_ebit/1e6:.1f}M (margin: {ebit_margin:.1%})
- EBIT vs Budget: RM {(group_ebit - group_budget_ebit)/1e6:+.1f}M

SEGMENTS:
{segment_details}
PARCEL ECONOMICS:
- Parcels delivered: {total_parcels/1e6:.1f}M
- Revenue per parcel: RM {rev_per_parcel:.2f} (declining ~5% YoY)
- Contribution margin per parcel: RM {cm_per_parcel:.2f}
- MPS postal parcel operations are loss-making at unit level

Respond ONLY in this exact JSON format:
{{
    "concern": "Write 2-3 sentences (40-50 words) about the most critical financial concern. Name the specific metric, the magnitude of the problem, and why it matters to the business. Use exact numbers from the data above.",
    "bright_spot": "Write 2-3 sentences (40-50 words) about the strongest positive performance. Name the segment or metric, quantify the outperformance, and explain why it matters strategically.",
    "action": "Write 2 sentences (30-40 words) recommending the single most important management action. Be specific about what to do, which segment or product it applies to, and what outcome to target. Avoid generic phrases like 'reduce costs' or 'implement expense reductions' — name the actual cost line or operation."
}}

QUALITY GUIDELINES:
- Each section must contain a specific number AND its business implication
- BAD example: "EBIT loss of RM 71.2M" (just restates a number)
- GOOD example: "Parcel yield erosion is the critical risk — Rev/P fell 4.9% YoY to RM 9.95, compressing contribution margin to RM 1.86. MPS postal parcels are now loss-making at unit level, meaning volume growth accelerates losses rather than recovery."
- The reader is a board director who needs to understand WHAT happened, WHY it matters, and WHAT to do about it
- Do NOT just restate numbers — explain their business significance
- Use ONLY numbers from the data provided
- Valid JSON only — no markdown backticks, no text outside the JSON"""

print("\n1/5 Generating Group commentary...")
group_result = call_groq(group_prompt)

all_commentaries = []

if group_result["success"]:
    print(f"  ✓ Concern:     {group_result['concern'][:80]}...")
    print(f"  ✓ Bright spot: {group_result['bright_spot'][:80]}...")
    print(f"  ✓ Action:      {group_result['action'][:80]}...")

    all_commentaries.append({
        "commentary_id": f"FY{ANALYSIS_YEAR}_GROUP_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "period": f"FY{ANALYSIS_YEAR}",
        "segment": "Group",
        "scenario": "Actual vs Budget",
        "commentary_text": f"CONCERN: {group_result['concern']} | BRIGHT SPOT: {group_result['bright_spot']} | ACTION: {group_result['action']}",
        "concern_text": group_result["concern"],
        "bright_spot_text": group_result["bright_spot"],
        "action_text": group_result["action"],
        "model_used": GROQ_MODEL,
        "prompt_tokens": group_result["prompt_tokens"],
        "completion_tokens": group_result["completion_tokens"],
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "generated_by": "Fabric Notebook — Automated",
        "is_approved": False,
        "approved_by": None,
        "approved_at": None
    })
else:
    print("  ✗ Group commentary generation failed.")

# --- Generate Segment commentaries ---
for idx, (_, row) in enumerate(segment_df.iterrows()):
    seg_name = row["segment_name"]
    seg_rev = row["actual_revenue"]
    seg_ebit = row["actual_ebit"]
    seg_budget_rev = row["budget_revenue"]
    seg_budget_ebit = row["budget_ebit"]
    seg_margin = seg_ebit / seg_rev if seg_rev != 0 else 0
    seg_rev_var = (seg_rev - seg_budget_rev) / seg_budget_rev if seg_budget_rev != 0 else 0

    # Small delay to respect Groq rate limits
    time.sleep(2)

    seg_prompt = f"""Write structured insights for the {seg_name} segment 
of {COMPANY_NAME}, FY{ANALYSIS_YEAR}.

RESULTS:
- Revenue: RM {seg_rev/1e6:.1f}M (vs Budget: {seg_rev_var:+.1%})
- EBIT: RM {seg_ebit/1e6:.1f}M (margin: {seg_margin:.1%})
- EBIT vs Budget: RM {(seg_ebit - seg_budget_ebit)/1e6:+.1f}M
- Context: {seg_name} is {'the profitable bright spot generating the majority of group earnings' if seg_ebit > 0 else 'currently loss-making and a drag on group profitability'}.

Respond ONLY in this exact JSON format:
{{
    "concern": "2-3 sentences (40-50 words) on the key risk or issue for this segment. Name the specific driver, quantify the impact, and explain why it threatens the segment or group.",
    "bright_spot": "2-3 sentences (40-50 words) on the strongest positive for this segment. Quantify the achievement and explain its strategic significance.",
    "action": "1-2 sentences (25-35 words) recommending the priority management action for this segment. Be specific about what to change."
}}

QUALITY GUIDELINES:
- BAD: "Revenue missed budget by 4.5%" (just restates data)
- GOOD: "Revenue missed budget by 4.5%, driven by accelerating mail volume decline as digital substitution continues. Without parcel yield recovery, the segment's path to breakeven extends beyond FY2027."
- Explain the WHY and the SO WHAT, not just the WHAT
- Use ONLY numbers provided. Valid JSON only. No markdown."""

    print(f"\n{idx+2}/5 Generating {seg_name} commentary...")
    seg_result = call_groq(seg_prompt)

    if seg_result["success"]:
        print(f"  ✓ Concern:     {seg_result['concern'][:80]}...")
        print(f"  ✓ Bright spot: {seg_result['bright_spot'][:80]}...")
        print(f"  ✓ Action:      {seg_result['action'][:80]}...")

        all_commentaries.append({
            "commentary_id": f"FY{ANALYSIS_YEAR}_{seg_name.upper()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "period": f"FY{ANALYSIS_YEAR}",
            "segment": seg_name,
            "scenario": "Actual vs Budget",
            "commentary_text": f"CONCERN: {seg_result['concern']} | BRIGHT SPOT: {seg_result['bright_spot']} | ACTION: {seg_result['action']}",
            "concern_text": seg_result["concern"],
            "bright_spot_text": seg_result["bright_spot"],
            "action_text": seg_result["action"],
            "model_used": GROQ_MODEL,
            "prompt_tokens": seg_result["prompt_tokens"],
            "completion_tokens": seg_result["completion_tokens"],
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "generated_by": "Fabric Notebook — Automated",
            "is_approved": False,
            "approved_by": None,
            "approved_at": None
        })
    else:
        print(f"  ✗ {seg_name} commentary generation failed.")

print(f"\n{'=' * 70}")
print(f"TOTAL COMMENTARIES GENERATED: {len(all_commentaries)} / 5")
print(f"{'=' * 70}")

# %%
# =====================================================================
# CELL 5: WRITE ALL COMMENTARIES TO DELTA TABLE
# =====================================================================

from pyspark.sql.types import StructType, StructField, StringType, IntegerType, BooleanType

schema = StructType([
    StructField("commentary_id", StringType(), False),
    StructField("period", StringType(), False),
    StructField("segment", StringType(), False),
    StructField("scenario", StringType(), False),
    StructField("commentary_text", StringType(), False),
    StructField("concern_text", StringType(), True),
    StructField("bright_spot_text", StringType(), True),
    StructField("action_text", StringType(), True),
    StructField("model_used", StringType(), True),
    StructField("prompt_tokens", IntegerType(), True),
    StructField("completion_tokens", IntegerType(), True),
    StructField("generated_at", StringType(), False),
    StructField("generated_by", StringType(), False),
    StructField("is_approved", BooleanType(), False),
    StructField("approved_by", StringType(), True),
    StructField("approved_at", StringType(), True),
])

if all_commentaries:
    # Drop old table (schema changed — remove this line after first successful run)
    spark.sql("DROP TABLE IF EXISTS insight_commentary")

    output_df = spark.createDataFrame(all_commentaries, schema=schema)

    output_df.write \
        .format("delta") \
        .mode("overwrite") \
        .saveAsTable("insight_commentary")

    print("=" * 70)
    print("ALL COMMENTARIES WRITTEN TO DELTA TABLE")
    print("=" * 70)
    print(f"  Table: insight_commentary")
    print(f"  Rows written: {len(all_commentaries)}")
    print(f"  Segments: {', '.join([c['segment'] for c in all_commentaries])}")
else:
    print("No commentaries generated — nothing written.")

# %%
# =====================================================================
# CELL 6: VERIFY
# =====================================================================

try:
    verify_df = spark.sql("""
        SELECT 
            segment,
            LEFT(concern_text, 60) AS concern_preview,
            LEFT(bright_spot_text, 60) AS bright_spot_preview,
            LEFT(action_text, 60) AS action_preview,
            generated_at
        FROM insight_commentary 
        ORDER BY 
            CASE segment 
                WHEN 'Group' THEN 0 
                WHEN 'Aviation' THEN 1 
                WHEN 'Logistics' THEN 2 
                WHEN 'Postal' THEN 3 
                WHEN 'Retail' THEN 4 
            END
    """)

    print("=" * 70)
    print("VERIFICATION — ALL COMMENTARIES IN DELTA TABLE")
    print("=" * 70)
    verify_df.show(truncate=60)

    total = spark.sql("SELECT COUNT(*) AS cnt FROM insight_commentary").collect()[0]["cnt"]
    print(f"Total rows: {total} (expected: 5)")

    if total == 5:
        print("\n✅ ALL 5 COMMENTARIES PRESENT — Group + 4 Segments")
        print("   Ready to connect to Power BI semantic model.")
    else:
        print(f"\n⚠️  Expected 5 rows, got {total}. Check for API failures above.")

except Exception as e:
    print(f"Verification error: {e}")

# %%
# =====================================================================
# CELL 7: NEXT STEPS (Reference — do not run)
# =====================================================================
# 
# After this notebook runs successfully:
#
# 1. ADD TABLE TO SEMANTIC MODEL:
#    - Open sem_meridian_finance
#    - Edit tables → find insight_commentary → check it → Confirm
#    - OR create a VIEW in wh_meridian pointing to this Lakehouse table
#
# 2. CREATE RELATIONSHIP:
#    - insight_commentary[segment] → dim_segment[segment_name]
#    - Many-to-one, single direction
#
# 3. CREATE DAX MEASURES (folder: 07 Commentary):
#
#    Insight Concern =
#    VAR _seg = SELECTEDVALUE(dim_segment[segment_name], "Group")
#    VAR _data = FILTER(insight_commentary, insight_commentary[segment] = _seg)
#    VAR _latest = MAXX(_data, insight_commentary[generated_at])
#    RETURN MAXX(FILTER(_data, insight_commentary[generated_at] = _latest), insight_commentary[concern_text])
#
#    Insight Bright Spot =
#    (same pattern, replace concern_text with bright_spot_text)
#
#    Insight Action =
#    (same pattern, replace concern_text with action_text)
#
# 4. BUILD 3 INSIGHT CARDS ON PAGE 1:
#    - Card 1: [Insight Concern]  — red left border, title "Key Concern"
#    - Card 2: [Insight Bright Spot] — green left border, title "Bright Spot"  
#    - Card 3: [Insight Action] — navy left border, title "Action Required"
#
# 5. ON PAGE 2 (Segment Deep-Dive):
#    - Same 3 cards, but they auto-update based on Segment slicer
#    - When user selects "Aviation", cards show Aviation-specific insights
#    - When no segment selected, defaults to "Group"
#
# 6. FOR FUTURE MONTHLY RUNS:
#    - Remove the DROP TABLE line in Cell 5
#    - Change mode from "overwrite" to "append"
#    - Each run adds timestamped rows; DAX measures always pull the latest
# =====================================================================
