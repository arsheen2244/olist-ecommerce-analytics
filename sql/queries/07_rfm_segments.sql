-- Business question: Which customer segments are worth the most, and who is slipping away?
-- Technique: RFM with NTILE() scoring. Frequency is mostly 1 in this dataset, so it is
--            banded (1 / 2 / 3+) instead of quintiled, which would give meaningless cut-offs.
WITH base AS (
    SELECT
        customer_unique_id,
        CAST(julianday((SELECT date(MAX(purchase_ts), '+1 day') FROM order_facts))
             - julianday(MAX(purchase_ts)) AS INTEGER) AS recency_days,
        COUNT(*)                                       AS frequency,
        SUM(items_value)                               AS monetary
    FROM order_facts
    WHERE order_status NOT IN ('canceled', 'unavailable')
      AND n_items > 0
    GROUP BY customer_unique_id
),
scored AS (
    SELECT *,
           NTILE(5) OVER (ORDER BY recency_days DESC) AS r_score,   -- 5 = most recent
           NTILE(5) OVER (ORDER BY monetary ASC)      AS m_score,   -- 5 = highest spend
           CASE WHEN frequency >= 3 THEN 3
                WHEN frequency = 2  THEN 2
                ELSE 1 END                            AS f_score
    FROM base
),
segmented AS (
    SELECT *,
           CASE
               WHEN f_score >= 2 AND r_score >= 4 THEN 'Champions (repeat + recent)'
               WHEN f_score >= 2                  THEN 'Repeat, cooling off'
               WHEN r_score >= 4 AND m_score >= 4 THEN 'Recent big spenders'
               WHEN r_score >= 4                  THEN 'New customers'
               WHEN m_score >= 4                  THEN 'Lapsed big spenders'
               ELSE                                    'Lapsed low-value'
           END AS segment
    FROM scored
)
SELECT
    segment,
    COUNT(*)                                                      AS customers,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)            AS pct_customers,
    ROUND(SUM(monetary), 2)                                       AS revenue,
    ROUND(100.0 * SUM(monetary) / SUM(SUM(monetary)) OVER (), 1)  AS pct_revenue,
    ROUND(AVG(monetary), 2)                                       AS avg_spend,
    ROUND(AVG(recency_days), 0)                                   AS avg_recency_days,
    ROUND(AVG(frequency), 2)                                      AS avg_orders
FROM segmented
GROUP BY segment
ORDER BY revenue DESC;
