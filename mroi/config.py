"""Project settings."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SQL_DIR = PROJECT_ROOT / "sql"

DEFAULT_HORIZON = 180   # days of outcomes measured per sign-up

# Decision rules for each campaign (also editable on the Excel Summary sheet).
SCALE_ROI = 0.50        # scale campaigns returning at least 50% ROI on 180-day gross profit
CUT_ROI = 0.0           # cut or rework campaigns that lose money at 180 days
MIN_SIGNUPS = 300       # fewer measured sign-ups than this is too early to judge

# Default budget scenario: halve the campaigns to cut and grow the ones to scale by half.
# Bigger jumps would likely raise CAC, so increases are capped and tested in steps.
CUT_CHANGE = -0.50
SCALE_CHANGE = 0.50

SQL_PIPELINE = [
    "01_staging.sql",
    "02_users.sql",
    "03_payback.sql",
    "04_cohort_conversion.sql",
    "05_campaign_scorecard.sql",
    "06_channel_monthly.sql",
    "07_powerbi_views.sql",
]

# Tables exported to output/marts as the Power BI feed.
EXPORTS = {
    "dim_channel": "SELECT * FROM dim_channel ORDER BY channel",
    "dim_campaign": "SELECT * FROM dim_campaign ORDER BY campaign_id",
    "fact_spend": "SELECT * FROM fact_spend ORDER BY spend_date, campaign_id",
    "fact_users": "SELECT * FROM fact_users ORDER BY signup_date, user_id",
    "fact_orders": "SELECT * FROM fact_orders ORDER BY order_date, order_id",
    "mart_campaign_scorecard": "SELECT * FROM mart_campaign_scorecard ORDER BY campaign_id",
    "mart_cohort_conversion": "SELECT * FROM mart_cohort_conversion ORDER BY cohort_month, channel, period",
    "mart_payback": "SELECT * FROM mart_payback ORDER BY campaign_id, period",
    "mart_channel_monthly": "SELECT * FROM mart_channel_monthly ORDER BY month, channel",
}
