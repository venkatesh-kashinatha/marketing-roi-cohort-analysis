-- 07_powerbi_views.sql
-- Tables for the Power BI model: two dimensions and three facts at their natural grain.
-- Power BI computes CAC, ROAS and ROI from these with DAX (see powerbi/measures.dax).

CREATE OR REPLACE VIEW dim_channel AS
SELECT DISTINCT channel FROM stg_campaigns;

CREATE OR REPLACE VIEW dim_campaign AS
SELECT * FROM stg_campaigns;

CREATE OR REPLACE VIEW fact_spend AS
SELECT
    sp.*,
    CASE WHEN sp.spend_date <= p.mature_cutoff THEN 1 ELSE 0 END AS in_mature_window
FROM stg_spend AS sp
CROSS JOIN params AS p;

CREATE OR REPLACE VIEW fact_users AS
SELECT * FROM int_users;

CREATE OR REPLACE VIEW fact_orders AS
SELECT
    o.*,
    u.campaign_id,
    u.channel,
    o.order_date - u.signup_date AS days_since_signup
FROM stg_orders AS o
JOIN int_users AS u ON u.user_id = o.user_id;
