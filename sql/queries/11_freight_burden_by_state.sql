-- Business question: Is shipping cost a barrier in remote states?
-- Technique: ratio of sums (not average of ratios) so large orders are weighted correctly.
SELECT
    customer_state,
    COUNT(*)                                                   AS orders,
    ROUND(AVG(items_value), 2)                                 AS avg_item_value,
    ROUND(AVG(freight_value), 2)                               AS avg_freight,
    ROUND(100.0 * SUM(freight_value) / SUM(items_value), 1)    AS freight_pct_of_item_value
FROM order_facts
WHERE order_status NOT IN ('canceled', 'unavailable')
  AND n_items > 0
GROUP BY customer_state
HAVING COUNT(*) >= 30
ORDER BY freight_pct_of_item_value DESC;
