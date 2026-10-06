-- 04_cohort_conversion.sql
-- Cohort conversion: for each monthly sign-up cohort (and channel), how many sign-ups had made
-- a first purchase within 30, 60, ... 360 days. A cohort gets a value for a window only when
-- every member has had that long since signing up, which keeps the triangle honest.

CREATE OR REPLACE TABLE mart_cohort_conversion AS
WITH periods AS (
    SELECT period FROM (VALUES (0), (1), (2), (3), (4), (5), (6), (7), (8), (9), (10), (11)) AS t (period)
),
cohorts AS (
    SELECT DISTINCT
        cohort_month,
        CAST(cohort_month + INTERVAL '1 month' - INTERVAL '1 day' AS DATE) AS cohort_month_end
    FROM int_users
)
SELECT
    u.cohort_month,
    u.channel,
    pr.period,
    30 * (pr.period + 1)                                                              AS within_days,
    COUNT(*)                                                                          AS signups,
    SUM(CASE WHEN u.days_to_first_order <= 30 * (pr.period + 1) - 1 THEN 1 ELSE 0 END) AS customers_cum
FROM int_users AS u
JOIN cohorts AS co ON co.cohort_month = u.cohort_month
CROSS JOIN periods AS pr
CROSS JOIN params AS p
WHERE co.cohort_month_end + (30 * (pr.period + 1) - 1) <= p.end_date
GROUP BY u.cohort_month, u.channel, pr.period;
