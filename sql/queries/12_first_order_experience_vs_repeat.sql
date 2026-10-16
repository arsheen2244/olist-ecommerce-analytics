-- Business question: Does a bad FIRST experience reduce the chance a customer ever returns?
-- Technique: ROW_NUMBER() to isolate each customer's first order, COUNT() OVER for lifetime orders.
--            This ties the delivery -> review -> retention story together.
WITH ranked AS (
    SELECT
        customer_unique_id,
        review_score,
        is_late,
        ROW_NUMBER() OVER (PARTITION BY customer_unique_id ORDER BY purchase_ts) AS order_seq,
        COUNT(*)     OVER (PARTITION BY customer_unique_id)                       AS lifetime_orders
    FROM order_facts
    WHERE order_status = 'delivered'
      AND review_score IS NOT NULL
)
SELECT
    review_score                                                         AS first_order_review,
    COUNT(*)                                                             AS customers,
    ROUND(100.0 * AVG(CASE WHEN lifetime_orders > 1 THEN 1.0 ELSE 0 END), 2) AS repeat_rate_pct
FROM ranked
WHERE order_seq = 1
GROUP BY review_score
ORDER BY review_score;
