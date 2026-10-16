-- =====================================================================
-- Olist e-commerce analytics: reusable views (SQLite dialect)
--
-- Metric definitions used everywhere downstream
--   valid order  = order_status NOT IN ('canceled', 'unavailable') AND has >= 1 item
--   revenue/GMV  = SUM(item price), freight excluded
--   late order   = delivered on a later calendar DATE than the estimate. Comparing raw
--                  timestamps would wrongly flag same-day deliveries as late, because
--                  the estimate is stored as midnight of the promised day.
--   review score = the LATEST review per order (some orders have duplicates)
-- =====================================================================

DROP VIEW IF EXISTS item_facts;
DROP VIEW IF EXISTS order_facts;

-- One row per order, enriched with value, delivery performance and review.
CREATE VIEW order_facts AS
WITH items AS (
    SELECT order_id,
           COUNT(*)           AS n_items,
           SUM(price)         AS items_value,
           SUM(freight_value) AS freight_value
    FROM order_items
    GROUP BY order_id
),
latest_review AS (
    SELECT order_id, review_score
    FROM (
        SELECT order_id,
               review_score,
               ROW_NUMBER() OVER (PARTITION BY order_id
                                  ORDER BY review_answer_timestamp DESC) AS rn
        FROM order_reviews
    )
    WHERE rn = 1
)
SELECT
    o.order_id,
    c.customer_unique_id,
    c.customer_state,
    o.order_status,
    o.order_purchase_timestamp                             AS purchase_ts,
    substr(o.order_purchase_timestamp, 1, 7)               AS purchase_month,
    o.order_delivered_customer_date                        AS delivered_ts,
    o.order_estimated_delivery_date                        AS estimated_ts,
    COALESCE(i.n_items, 0)                                 AS n_items,
    COALESCE(i.items_value, 0)                             AS items_value,
    COALESCE(i.freight_value, 0)                           AS freight_value,
    COALESCE(i.items_value, 0) + COALESCE(i.freight_value, 0) AS order_value,
    r.review_score,
    CASE WHEN o.order_delivered_customer_date IS NOT NULL
         THEN julianday(o.order_delivered_customer_date)
              - julianday(o.order_purchase_timestamp) END   AS delivery_days,
    CASE WHEN o.order_delivered_customer_date IS NOT NULL
         THEN julianday(date(o.order_delivered_customer_date))
              - julianday(date(o.order_estimated_delivery_date)) END AS days_vs_estimate,
    CASE WHEN o.order_delivered_customer_date IS NOT NULL
         THEN (date(o.order_delivered_customer_date)
               > date(o.order_estimated_delivery_date)) END  AS is_late
FROM orders o
JOIN customers c        ON c.customer_id = o.customer_id
LEFT JOIN items i       ON i.order_id = o.order_id
LEFT JOIN latest_review r ON r.order_id = o.order_id;

-- One row per order line, with category (English) and seller attributes.
CREATE VIEW item_facts AS
SELECT
    oi.order_id,
    oi.order_item_id,
    oi.product_id,
    oi.seller_id,
    oi.price,
    oi.freight_value,
    COALESCE(t.product_category_name_english,
             p.product_category_name, 'unknown') AS category,
    s.seller_state,
    f.customer_state,
    f.purchase_month,
    f.order_status,
    f.review_score,
    f.is_late,
    f.delivery_days
FROM order_items oi
JOIN order_facts f              ON f.order_id = oi.order_id
LEFT JOIN products p            ON p.product_id = oi.product_id
LEFT JOIN category_translation t ON t.product_category_name = p.product_category_name
LEFT JOIN sellers s             ON s.seller_id = oi.seller_id;
