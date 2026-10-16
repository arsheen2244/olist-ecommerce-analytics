-- Business question: What does the business look like at a glance?
-- Technique: conditional aggregation over a cleaned order-level view.
SELECT
    COUNT(*)                                                        AS orders,
    COUNT(DISTINCT customer_unique_id)                              AS unique_customers,
    ROUND(SUM(items_value), 2)                                      AS gmv,
    ROUND(AVG(items_value), 2)                                      AS avg_order_value,
    ROUND(100.0 * SUM(CASE WHEN order_status = 'delivered'
                           THEN 1 ELSE 0 END) / COUNT(*), 2)        AS delivered_pct,
    ROUND(AVG(review_score), 2)                                     AS avg_review_score,
    ROUND(100.0 * AVG(is_late), 2)                                  AS late_pct
FROM order_facts
WHERE order_status NOT IN ('canceled', 'unavailable')
  AND n_items > 0;
