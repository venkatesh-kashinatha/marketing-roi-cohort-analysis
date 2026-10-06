-- 06_channel_monthly.sql
-- Monthly trend by channel: spend, clicks, sign-ups and first purchases. Monthly CAC from this
-- table (spend in a month / first purchases in that month) is an operational view: it mixes
-- this month's spend with customers who may have signed up earlier.

CREATE OR REPLACE TABLE mart_channel_monthly AS
WITH spend AS (
    SELECT
        CAST(DATE_TRUNC('month', sp.spend_date) AS DATE) AS month,
        c.channel,
        SUM(sp.spend)  AS spend,
        SUM(sp.clicks) AS clicks
    FROM stg_spend AS sp
    JOIN stg_campaigns AS c ON c.campaign_id = sp.campaign_id
    GROUP BY CAST(DATE_TRUNC('month', sp.spend_date) AS DATE), c.channel
),
signups AS (
    SELECT cohort_month AS month, channel, COUNT(*) AS signups
    FROM int_users
    GROUP BY cohort_month, channel
),
first_purchases AS (
    SELECT CAST(DATE_TRUNC('month', first_order_date) AS DATE) AS month, channel, COUNT(*) AS new_customers
    FROM int_users
    WHERE first_order_date IS NOT NULL
    GROUP BY CAST(DATE_TRUNC('month', first_order_date) AS DATE), channel
),
grid AS (
    SELECT month, channel FROM spend
    UNION
    SELECT month, channel FROM signups
    UNION
    SELECT month, channel FROM first_purchases
)
SELECT
    g.month,
    g.channel,
    COALESCE(s.spend, 0)          AS spend,
    COALESCE(s.clicks, 0)         AS clicks,
    COALESCE(su.signups, 0)       AS signups,
    COALESCE(fp.new_customers, 0) AS new_customers
FROM grid AS g
LEFT JOIN spend AS s ON s.month = g.month AND s.channel = g.channel
LEFT JOIN signups AS su ON su.month = g.month AND su.channel = g.channel
LEFT JOIN first_purchases AS fp ON fp.month = g.month AND fp.channel = g.channel;
