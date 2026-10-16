-- Business question: How do customers pay, and how much do instalments matter?
-- Technique: join + window share-of-total over an aggregate (SUM(SUM(...)) OVER ()).
SELECT
    p.payment_type,
    COUNT(DISTINCT p.order_id)                                           AS orders,
    ROUND(SUM(p.payment_value), 2)                                       AS payment_value,
    ROUND(100.0 * SUM(p.payment_value) / SUM(SUM(p.payment_value)) OVER (), 2) AS value_share_pct,
    ROUND(AVG(p.payment_installments), 2)                                AS avg_installments,
    ROUND(AVG(p.payment_value), 2)                                       AS avg_payment
FROM order_payments p
JOIN orders o ON o.order_id = p.order_id
WHERE o.order_status NOT IN ('canceled', 'unavailable')
  AND p.payment_type <> 'not_defined'
GROUP BY p.payment_type
ORDER BY payment_value DESC;
