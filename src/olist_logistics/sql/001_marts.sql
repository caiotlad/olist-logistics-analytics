CREATE SCHEMA IF NOT EXISTS olist_mart;

CREATE OR REPLACE VIEW olist_mart.fact_orders AS
WITH item_totals AS (
    SELECT order_id, COUNT(*)::bigint AS item_count, COUNT(DISTINCT seller_id)::bigint AS seller_count,
           SUM((price::numeric * 100)::bigint)::bigint AS product_total_cents,
           SUM((freight_value::numeric * 100)::bigint)::bigint AS freight_total_cents
    FROM olist_stage.items GROUP BY order_id
), payment_totals AS (
    SELECT order_id, COUNT(*)::bigint AS payment_count,
           SUM((payment_value::numeric * 100)::bigint)::bigint AS payment_total_cents
    FROM olist_stage.payments GROUP BY order_id
), reviews_prepared AS (
    SELECT *, review_score::integer AS score,
           NULLIF(review_answer_timestamp, '')::timestamp AS answered_at,
           NULLIF(review_creation_date, '')::timestamp AS created_at
    FROM olist_stage.reviews
), review_ties AS (
    SELECT order_id, review_id, answered_at, created_at, COUNT(DISTINCT score) > 1 AS review_conflict
    FROM reviews_prepared GROUP BY order_id, review_id, answered_at, created_at
), reviews_ranked AS (
    SELECT r.*, COUNT(*) OVER (PARTITION BY order_id)::bigint AS review_count,
           ROW_NUMBER() OVER (
               PARTITION BY order_id ORDER BY answered_at DESC NULLS LAST, created_at DESC NULLS LAST, review_id DESC
           ) AS row_number
    FROM reviews_prepared r
), last_review AS (
    SELECT r.order_id, CASE WHEN t.review_conflict THEN NULL ELSE r.score END AS review_score,
           r.review_count, t.review_conflict
    FROM reviews_ranked r
    JOIN review_ties t ON t.order_id = r.order_id AND t.review_id = r.review_id
        AND t.answered_at IS NOT DISTINCT FROM r.answered_at
        AND t.created_at IS NOT DISTINCT FROM r.created_at
    WHERE r.row_number = 1
), prepared AS (
    SELECT o.order_id, o.customer_id, o.order_status,
           NULLIF(o.order_purchase_timestamp, '')::timestamp AS order_purchase_timestamp,
           NULLIF(o.order_approved_at, '')::timestamp AS order_approved_at,
           NULLIF(o.order_delivered_carrier_date, '')::timestamp AS order_delivered_carrier_date,
           NULLIF(o.order_delivered_customer_date, '')::timestamp AS order_delivered_customer_date,
           NULLIF(o.order_estimated_delivery_date, '')::timestamp AS order_estimated_delivery_date,
           c.customer_unique_id, c.customer_zip_code_prefix, c.customer_city, c.customer_state,
           COALESCE(i.item_count, 0)::bigint AS item_count,
           COALESCE(i.seller_count, 0)::bigint AS seller_count,
           i.product_total_cents, i.freight_total_cents,
           COALESCE(p.payment_count, 0)::bigint AS payment_count, p.payment_total_cents,
           r.review_score, COALESCE(r.review_count, 0)::bigint AS review_count,
           COALESCE(r.review_conflict, FALSE) AS review_conflict
    FROM olist_stage.orders o
    LEFT JOIN olist_stage.customers c USING (customer_id)
    LEFT JOIN item_totals i USING (order_id)
    LEFT JOIN payment_totals p USING (order_id)
    LEFT JOIN last_review r USING (order_id)
), eligible AS (
    SELECT *, COALESCE(
        order_status = 'delivered'
        AND order_purchase_timestamp IS NOT NULL
        AND order_delivered_customer_date IS NOT NULL
        AND order_estimated_delivery_date IS NOT NULL
        AND order_delivered_customer_date >= order_purchase_timestamp
        AND order_estimated_delivery_date::date >= order_purchase_timestamp::date,
        FALSE
    ) AS delivery_eligible
    FROM prepared
)
SELECT *,
       order_purchase_timestamp::date AS purchase_date,
       TO_CHAR(order_purchase_timestamp, 'YYYY-MM') AS purchase_month,
       CASE WHEN delivery_eligible THEN order_delivered_customer_date::date > order_estimated_delivery_date::date END AS delivered_late,
       CASE WHEN delivery_eligible THEN EXTRACT(EPOCH FROM order_delivered_customer_date - order_purchase_timestamp)::double precision / 86400 END AS delivery_days,
       CASE WHEN delivery_eligible THEN order_delivered_customer_date::date - order_estimated_delivery_date::date END AS delay_calendar_days,
       freight_total_cents::double precision / NULLIF(product_total_cents, 0) AS freight_ratio
FROM eligible;

CREATE OR REPLACE VIEW olist_mart.seller_orders AS
WITH scoped AS (
    SELECT order_id, seller_id, COUNT(*)::bigint AS item_count,
           SUM((price::numeric * 100)::bigint)::bigint AS product_total_cents,
           SUM((freight_value::numeric * 100)::bigint)::bigint AS freight_total_cents
    FROM olist_stage.items GROUP BY order_id, seller_id
)
SELECT s.*, d.seller_state, f.purchase_date, f.purchase_month, f.customer_state,
       f.delivery_eligible, f.delivered_late, f.delivery_days, f.review_score
FROM scoped s
LEFT JOIN olist_stage.sellers d USING (seller_id)
JOIN olist_mart.fact_orders f USING (order_id);

CREATE OR REPLACE VIEW olist_mart.category_orders AS
WITH scoped AS (
    SELECT i.order_id, COALESCE(p.product_category_name, '__unknown__') AS category,
           COUNT(*)::bigint AS item_count,
           SUM((i.price::numeric * 100)::bigint)::bigint AS product_total_cents,
           SUM((i.freight_value::numeric * 100)::bigint)::bigint AS freight_total_cents
    FROM olist_stage.items i
    LEFT JOIN olist_stage.products p USING (product_id)
    GROUP BY i.order_id, COALESCE(p.product_category_name, '__unknown__')
)
SELECT s.*, f.purchase_date, f.purchase_month, f.customer_state,
       f.delivery_eligible, f.delivered_late, f.delivery_days, f.review_score
FROM scoped s JOIN olist_mart.fact_orders f USING (order_id);

CREATE OR REPLACE VIEW olist_mart.calendar AS
SELECT observed.day::date AS date, EXTRACT(YEAR FROM observed.day)::integer AS year,
       EXTRACT(MONTH FROM observed.day)::integer AS month,
       TO_CHAR(observed.day, 'YYYY-MM') AS year_month
FROM generate_series(
    (SELECT MIN(order_purchase_timestamp)::date FROM olist_mart.fact_orders),
    (SELECT MAX(order_purchase_timestamp)::date FROM olist_mart.fact_orders),
    interval '1 day'
) AS observed(day);
