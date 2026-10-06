-- 05_campaign_scorecard.sql
-- One row per campaign, measured over the mature window: sign-ups (and the spend that bought
-- them) on or before the mature cutoff, with outcomes counted within the horizon. Comparing
-- campaigns on equal footing avoids flattering old campaigns or punishing new ones.

CREATE OR REPLACE TABLE mart_campaign_scorecard AS
WITH spend AS (
    SELECT
        sp.campaign_id,
        SUM(sp.spend)       AS spend,
        SUM(sp.impressions) AS impressions,
        SUM(sp.clicks)      AS clicks
    FROM stg_spend AS sp
    CROSS JOIN params AS p
    WHERE sp.spend_date <= p.mature_cutoff
    GROUP BY sp.campaign_id
),
recent AS (
    -- Spend over the last 12 months: the starting point for budget scenarios. Using a full
    -- year keeps seasonal campaigns at their true annual budget.
    SELECT sp.campaign_id, SUM(sp.spend) AS spend_last_12m
    FROM stg_spend AS sp
    CROSS JOIN params AS p
    WHERE sp.spend_date > p.end_date - 365
    GROUP BY sp.campaign_id
),
users AS (
    SELECT
        campaign_id,
        COUNT(*)                     AS signups,
        SUM(converted_7d)            AS customers_7d,
        SUM(converted_in_horizon)    AS customers,
        SUM(orders_in_horizon)       AS orders,
        SUM(revenue_in_horizon)      AS revenue,
        SUM(gross_profit_in_horizon) AS gross_profit
    FROM int_users
    WHERE is_mature = 1
    GROUP BY campaign_id
),
payback AS (
    -- First 30-day period in which cumulative gross profit covered the spend.
    SELECT campaign_id, MIN(period) AS payback_period
    FROM mart_payback
    WHERE payback_ratio >= 1
    GROUP BY campaign_id
)
SELECT
    c.campaign_id,
    c.campaign_name,
    c.channel,
    c.objective,
    c.start_date,
    c.end_date,
    COALESCE(s.spend, 0)                              AS spend,
    COALESCE(s.impressions, 0)                        AS impressions,
    COALESCE(s.clicks, 0)                             AS clicks,
    COALESCE(u.signups, 0)                            AS signups,
    COALESCE(u.customers_7d, 0)                       AS customers_7d,
    COALESCE(u.customers, 0)                          AS customers,
    COALESCE(u.orders, 0)                             AS orders,
    COALESCE(u.revenue, 0)                            AS revenue,
    COALESCE(u.gross_profit, 0)                       AS gross_profit,
    pb.payback_period + 1                             AS payback_months,
    CASE WHEN c.end_date >= p.end_date
         THEN COALESCE(r.spend_last_12m, 0) ELSE 0 END AS current_annual_spend,  -- 0 once a campaign has ended
    s.spend / NULLIF(u.customers, 0)                  AS cac,
    u.revenue / NULLIF(s.spend, 0)                    AS roas,
    (u.gross_profit - s.spend) / NULLIF(s.spend, 0)   AS roi
FROM stg_campaigns AS c
LEFT JOIN spend AS s ON s.campaign_id = c.campaign_id
LEFT JOIN users AS u ON u.campaign_id = c.campaign_id
LEFT JOIN payback AS pb ON pb.campaign_id = c.campaign_id
LEFT JOIN recent AS r ON r.campaign_id = c.campaign_id
CROSS JOIN params AS p;
