-- Business question: Which sellers should the marketplace fix first?
-- Technique: seller-level aggregation, RANK() + NTILE() over revenue, rule-based action flag.
--            "Fix first" = top revenue quartile but poor reviews or frequent late deliveries,
--            i.e. where a CX problem puts the most revenue at risk.
WITH seller AS (
    SELECT
        seller_id,
        seller_state,
        COUNT(DISTINCT order_id) AS orders,
        SUM(price)               AS revenue,
        AVG(review_score)        AS avg_review,
        100.0 * AVG(is_late)     AS late_pct,
        AVG(delivery_days)       AS avg_delivery_days
    FROM item_facts
    WHERE order_status = 'delivered'
    GROUP BY seller_id, seller_state
    HAVING COUNT(DISTINCT order_id) >= 20
),
ranked AS (
    SELECT *,
           RANK()   OVER (ORDER BY revenue DESC) AS revenue_rank,
           NTILE(4) OVER (ORDER BY revenue DESC) AS revenue_quartile   -- 1 = top 25%
    FROM seller
)
SELECT
    seller_id,
    seller_state,
    orders,
    ROUND(revenue, 2)            AS revenue,
    ROUND(avg_review, 2)         AS avg_review,
    ROUND(late_pct, 1)           AS late_pct,
    ROUND(avg_delivery_days, 1)  AS avg_delivery_days,
    revenue_rank,
    revenue_quartile,
    CASE
        WHEN revenue_quartile = 1 AND (avg_review < 3.8 OR late_pct > 15)
            THEN 'Fix first: big seller, poor experience'
        WHEN avg_review >= 4.3 AND late_pct <= 8
            THEN 'Healthy'
        ELSE 'Monitor'
    END                          AS action_flag
FROM ranked
ORDER BY revenue_rank;
