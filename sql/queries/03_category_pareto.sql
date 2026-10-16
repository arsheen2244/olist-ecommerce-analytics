-- Business question: Which categories drive revenue, and how concentrated is it (80/20)?
-- Technique: window share-of-total, running cumulative share (Pareto), RANK().
WITH cat AS (
    SELECT category,
           COUNT(DISTINCT order_id) AS orders,
           SUM(price)               AS revenue,
           AVG(review_score)        AS avg_review
    FROM item_facts
    WHERE order_status NOT IN ('canceled', 'unavailable')
    GROUP BY category
)
SELECT
    category,
    orders,
    ROUND(revenue, 2)                                              AS revenue,
    ROUND(100.0 * revenue / SUM(revenue) OVER (), 2)               AS revenue_share_pct,
    ROUND(100.0 * SUM(revenue) OVER (ORDER BY revenue DESC
                                     ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
          / SUM(revenue) OVER (), 2)                               AS cumulative_share_pct,
    ROUND(avg_review, 2)                                           AS avg_review,
    RANK() OVER (ORDER BY revenue DESC)                            AS revenue_rank
FROM cat
ORDER BY revenue DESC;
