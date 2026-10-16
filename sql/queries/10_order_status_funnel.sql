-- Business question: How many orders fall out of the fulfilment funnel, and where?
-- Technique: share-of-total window over a grouped count.
SELECT
    order_status,
    COUNT(*)                                              AS orders,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2)    AS pct_of_orders
FROM orders
GROUP BY order_status
ORDER BY orders DESC;
