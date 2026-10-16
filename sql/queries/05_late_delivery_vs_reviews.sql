-- Business question: How much does a late delivery hurt customer satisfaction?
-- Technique: CASE bucketing of a continuous variable, then compare outcomes per bucket.
SELECT
    CASE
        WHEN days_vs_estimate <= -7 THEN '1. 7+ days early'
        WHEN days_vs_estimate <=  0 THEN '2. On time (0-7 days early)'
        WHEN days_vs_estimate <=  3 THEN '3. 1-3 days late'
        WHEN days_vs_estimate <=  7 THEN '4. 4-7 days late'
        ELSE                             '5. 8+ days late'
    END                                                   AS delivery_bucket,
    COUNT(*)                                              AS orders,
    ROUND(AVG(review_score), 2)                           AS avg_review,
    ROUND(100.0 * AVG(CASE WHEN review_score <= 2
                           THEN 1.0 ELSE 0 END), 1)       AS pct_negative_reviews
FROM order_facts
WHERE order_status = 'delivered'
  AND delivered_ts IS NOT NULL
  AND review_score IS NOT NULL
GROUP BY delivery_bucket
ORDER BY delivery_bucket;
