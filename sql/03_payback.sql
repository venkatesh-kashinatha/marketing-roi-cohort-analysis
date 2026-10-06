-- 03_payback.sql
-- Payback curves: cumulative gross profit from a campaign's sign-ups vs the spend that bought
-- them, by 30-day period since sign-up. Period k covers days 0 to 30(k+1)-1.
-- For each period, only sign-ups and spend on or before that period's cutoff are counted, so
-- every user included has the full window of history (no half-observed cohorts).

CREATE OR REPLACE TABLE mart_payback AS
WITH periods AS (
    SELECT period FROM (VALUES (0), (1), (2), (3), (4), (5), (6), (7), (8), (9), (10), (11)) AS t (period)
),
cutoffs AS (
    SELECT pr.period, p.end_date - (30 * (pr.period + 1) - 1) AS signup_cutoff
    FROM periods AS pr
    CROSS JOIN params AS p
),
spend AS (
    SELECT co.period, sp.campaign_id, SUM(sp.spend) AS spend
    FROM cutoffs AS co
    JOIN stg_spend AS sp ON sp.spend_date <= co.signup_cutoff
    GROUP BY co.period, sp.campaign_id
),
signups AS (
    SELECT co.period, u.campaign_id, COUNT(*) AS signups
    FROM cutoffs AS co
    JOIN int_users AS u ON u.signup_date <= co.signup_cutoff
    GROUP BY co.period, u.campaign_id
),
profit AS (
    SELECT
        co.period,
        u.campaign_id,
        SUM(o.revenue)      AS revenue_cum,
        SUM(o.gross_profit) AS gross_profit_cum
    FROM cutoffs AS co
    JOIN int_users AS u ON u.signup_date <= co.signup_cutoff
    JOIN stg_orders AS o
      ON o.user_id = u.user_id
     AND o.order_date - u.signup_date BETWEEN 0 AND 30 * (co.period + 1) - 1
    GROUP BY co.period, u.campaign_id
)
SELECT
    sp.campaign_id,
    c.channel,
    sp.period,
    30 * (sp.period + 1)                                     AS days_since_signup,
    sp.spend,
    COALESCE(su.signups, 0)                                  AS signups,
    COALESCE(pf.revenue_cum, 0)                              AS revenue_cum,
    COALESCE(pf.gross_profit_cum, 0)                         AS gross_profit_cum,
    COALESCE(pf.gross_profit_cum, 0) / NULLIF(sp.spend, 0)   AS payback_ratio
FROM spend AS sp
JOIN stg_campaigns AS c ON c.campaign_id = sp.campaign_id
LEFT JOIN signups AS su ON su.period = sp.period AND su.campaign_id = sp.campaign_id
LEFT JOIN profit AS pf ON pf.period = sp.period AND pf.campaign_id = sp.campaign_id;
