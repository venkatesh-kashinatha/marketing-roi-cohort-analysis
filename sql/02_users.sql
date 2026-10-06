-- 02_users.sql
-- One row per sign-up: cohort month, first purchase, conversion flags, and the orders,
-- revenue and gross profit each user generated within the horizon (days 0 to horizon-1).
-- is_mature = 1 when the user signed up early enough to have the full horizon of history.

CREATE OR REPLACE TABLE int_users AS
WITH first_orders AS (
    SELECT user_id, MIN(order_date) AS first_order_date
    FROM stg_orders
    GROUP BY user_id
),
value_in_horizon AS (
    SELECT
        o.user_id,
        COUNT(*)            AS orders_in_horizon,
        SUM(o.revenue)      AS revenue_in_horizon,
        SUM(o.gross_profit) AS gross_profit_in_horizon
    FROM stg_orders AS o
    JOIN stg_signups AS s ON s.user_id = o.user_id
    CROSS JOIN params AS p
    WHERE o.order_date - s.signup_date BETWEEN 0 AND p.horizon_days - 1
    GROUP BY o.user_id
)
SELECT
    s.user_id,
    s.signup_date,
    s.campaign_id,
    c.channel,
    CAST(DATE_TRUNC('month', s.signup_date) AS DATE)                                       AS cohort_month,
    f.first_order_date,
    f.first_order_date - s.signup_date                                                     AS days_to_first_order,
    CASE WHEN f.first_order_date - s.signup_date <= 6 THEN 1 ELSE 0 END                    AS converted_7d,
    CASE WHEN f.first_order_date - s.signup_date <= 29 THEN 1 ELSE 0 END                   AS converted_30d,
    CASE WHEN f.first_order_date - s.signup_date <= p.horizon_days - 1 THEN 1 ELSE 0 END   AS converted_in_horizon,
    COALESCE(v.orders_in_horizon, 0)                                                       AS orders_in_horizon,
    COALESCE(v.revenue_in_horizon, 0)                                                      AS revenue_in_horizon,
    COALESCE(v.gross_profit_in_horizon, 0)                                                 AS gross_profit_in_horizon,
    CASE WHEN s.signup_date <= p.mature_cutoff THEN 1 ELSE 0 END                           AS is_mature
FROM stg_signups AS s
JOIN stg_campaigns AS c ON c.campaign_id = s.campaign_id
LEFT JOIN first_orders AS f ON f.user_id = s.user_id
LEFT JOIN value_in_horizon AS v ON v.user_id = s.user_id
CROSS JOIN params AS p;
