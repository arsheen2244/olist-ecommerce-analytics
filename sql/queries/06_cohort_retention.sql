-- Business question: Do customers come back? How does retention differ by acquisition month?
-- Technique: first-purchase cohorts, month-offset arithmetic, retention % per cohort.
WITH valid AS (
    SELECT customer_unique_id, purchase_month
    FROM order_facts
    WHERE order_status NOT IN ('canceled', 'unavailable')
      AND n_items > 0
),
first_purchase AS (
    SELECT customer_unique_id, MIN(purchase_month) AS cohort_month
    FROM valid
    GROUP BY customer_unique_id
),
activity AS (
    SELECT DISTINCT
        v.customer_unique_id,
        fp.cohort_month,
        (CAST(substr(v.purchase_month, 1, 4) AS INTEGER)
         - CAST(substr(fp.cohort_month, 1, 4) AS INTEGER)) * 12
        + CAST(substr(v.purchase_month, 6, 2) AS INTEGER)
        - CAST(substr(fp.cohort_month, 6, 2) AS INTEGER)  AS month_number
    FROM valid v
    JOIN first_purchase fp ON fp.customer_unique_id = v.customer_unique_id
),
cohort_size AS (
    SELECT cohort_month, COUNT(*) AS cohort_customers
    FROM first_purchase
    GROUP BY cohort_month
)
SELECT
    a.cohort_month,
    cs.cohort_customers,
    a.month_number,
    COUNT(*)                                             AS active_customers,
    ROUND(100.0 * COUNT(*) / cs.cohort_customers, 2)     AS retention_pct
FROM activity a
JOIN cohort_size cs ON cs.cohort_month = a.cohort_month
GROUP BY a.cohort_month, cs.cohort_customers, a.month_number
ORDER BY a.cohort_month, a.month_number;
