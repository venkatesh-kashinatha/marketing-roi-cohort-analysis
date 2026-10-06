-- checks.sql
-- Data quality checks. Each row is one check, and failing_rows should be 0.
SELECT 'Sign-ups with an unknown campaign' AS check_name, COUNT(*) AS failing_rows
FROM stg_signups AS s LEFT JOIN stg_campaigns AS c ON c.campaign_id = s.campaign_id
WHERE c.campaign_id IS NULL
UNION ALL
SELECT 'Spend rows with an unknown campaign', COUNT(*)
FROM stg_spend AS sp LEFT JOIN stg_campaigns AS c ON c.campaign_id = sp.campaign_id
WHERE c.campaign_id IS NULL
UNION ALL
SELECT 'Spend outside the campaign dates', COUNT(*)
FROM stg_spend AS sp JOIN stg_campaigns AS c ON c.campaign_id = sp.campaign_id
WHERE sp.spend_date NOT BETWEEN c.start_date AND c.end_date
UNION ALL
SELECT 'Orders from an unknown user', COUNT(*)
FROM stg_orders AS o LEFT JOIN stg_signups AS s ON s.user_id = o.user_id
WHERE s.user_id IS NULL
UNION ALL
SELECT 'Orders dated before the sign-up', COUNT(*)
FROM stg_orders AS o JOIN stg_signups AS s ON s.user_id = o.user_id
WHERE o.order_date < s.signup_date
UNION ALL
SELECT 'Duplicate user IDs', COUNT(*) - COUNT(DISTINCT user_id) FROM stg_signups
UNION ALL
SELECT 'Duplicate order IDs', COUNT(*) - COUNT(DISTINCT order_id) FROM stg_orders
UNION ALL
SELECT 'Negative spend, revenue or cost',
       (SELECT COUNT(*) FROM stg_spend WHERE spend < 0)
     + (SELECT COUNT(*) FROM stg_orders WHERE revenue < 0 OR cost_of_goods < 0)
UNION ALL
SELECT 'Missing dates or amounts',
       (SELECT COUNT(*) FROM stg_spend WHERE spend_date IS NULL OR spend IS NULL)
     + (SELECT COUNT(*) FROM stg_signups WHERE signup_date IS NULL)
     + (SELECT COUNT(*) FROM stg_orders WHERE order_date IS NULL OR revenue IS NULL);
