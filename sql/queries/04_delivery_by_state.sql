-- Business question: Where is delivery performance worst?
-- Technique: grouped aggregation with a minimum-volume filter (HAVING) to avoid tiny-sample noise.
SELECT
    customer_state,
    COUNT(*)                              AS delivered_orders,
    ROUND(AVG(delivery_days), 1)          AS avg_delivery_days,
    ROUND(AVG(days_vs_estimate), 1)       AS avg_days_vs_estimate,
    ROUND(100.0 * AVG(is_late), 1)        AS late_pct,
    ROUND(AVG(review_score), 2)           AS avg_review
FROM order_facts
WHERE order_status = 'delivered'
  AND delivered_ts IS NOT NULL
GROUP BY customer_state
HAVING COUNT(*) >= 30
ORDER BY late_pct DESC;
