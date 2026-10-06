-- 01_staging.sql
-- Load the raw CSV files into typed staging tables and record the run parameters.
-- This is the only DuckDB-specific file (read_csv). In PostgreSQL, create the same tables
-- and load them with COPY; files 02-07 then run with little or no change.

CREATE OR REPLACE TABLE stg_campaigns AS
SELECT
    TRIM(campaign_id)             AS campaign_id,
    TRIM(campaign_name)           AS campaign_name,
    TRIM(channel)                 AS channel,
    TRIM(objective)               AS objective,
    CAST(start_date AS DATE)      AS start_date,
    CAST(end_date AS DATE)        AS end_date
FROM read_csv('{{RAW_DIR}}/campaigns.csv', header = true, all_varchar = true);

CREATE OR REPLACE TABLE stg_spend AS
SELECT
    CAST(spend_date AS DATE)      AS spend_date,
    TRIM(campaign_id)             AS campaign_id,
    CAST(spend AS DOUBLE)         AS spend,
    CAST(impressions AS BIGINT)   AS impressions,
    CAST(clicks AS BIGINT)        AS clicks
FROM read_csv('{{RAW_DIR}}/daily_spend.csv', header = true, all_varchar = true);

CREATE OR REPLACE TABLE stg_signups AS
SELECT
    TRIM(user_id)                 AS user_id,
    CAST(signup_date AS DATE)     AS signup_date,
    TRIM(campaign_id)             AS campaign_id
FROM read_csv('{{RAW_DIR}}/signups.csv', header = true, all_varchar = true);

CREATE OR REPLACE TABLE stg_orders AS
SELECT
    TRIM(order_id)                AS order_id,
    TRIM(user_id)                 AS user_id,
    CAST(order_date AS DATE)      AS order_date,
    CAST(revenue AS DOUBLE)       AS revenue,
    CAST(cost_of_goods AS DOUBLE) AS cost_of_goods,
    CAST(revenue AS DOUBLE) - CAST(cost_of_goods AS DOUBLE) AS gross_profit
FROM read_csv('{{RAW_DIR}}/orders.csv', header = true, all_varchar = true);

-- One-row table used by every later query.
--   end_date      last date seen in any table
--   horizon_days  outcome window per sign-up (default 180 days)
--   mature_cutoff last sign-up date with a full horizon of history
CREATE OR REPLACE TABLE params AS
SELECT
    MAX(d)                        AS end_date,
    {{HORIZON}}                   AS horizon_days,
    MAX(d) - ({{HORIZON}} - 1)    AS mature_cutoff
FROM (
    SELECT MAX(spend_date) AS d FROM stg_spend
    UNION ALL SELECT MAX(signup_date) FROM stg_signups
    UNION ALL SELECT MAX(order_date) FROM stg_orders
) AS all_dates;
