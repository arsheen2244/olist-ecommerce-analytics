-- Business question: How is revenue trending, and which months are spikes vs. real growth?
-- Technique: CTE + LAG() for month-over-month growth + 3-month moving average window.
WITH monthly AS (
    SELECT purchase_month,
           COUNT(*)                           AS orders,
           SUM(items_value)                   AS revenue,
           COUNT(DISTINCT customer_unique_id) AS customers
    FROM order_facts
    WHERE order_status NOT IN ('canceled', 'unavailable')
      AND n_items > 0
    GROUP BY purchase_month
)
SELECT
    purchase_month,
    orders,
    ROUND(revenue, 2)                                              AS revenue,
    customers,
    ROUND(revenue / orders, 2)                                     AS aov,
    ROUND(100.0 * (revenue - LAG(revenue) OVER (ORDER BY purchase_month))
          / LAG(revenue) OVER (ORDER BY purchase_month), 1)        AS mom_growth_pct,
    ROUND(AVG(revenue) OVER (ORDER BY purchase_month
                             ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 2) AS revenue_3m_avg
FROM monthly
ORDER BY purchase_month;
