from dataclasses import dataclass


SOURCE_URL = "https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce"
DATA_LICENSE = "CC-BY-NC-SA-4.0"


@dataclass(frozen=True)
class Source:
    filename: str
    columns: tuple[str, ...]
    key: tuple[str, ...] = ()


SOURCES = {
    "orders": Source("olist_orders_dataset.csv", (
        "order_id", "customer_id", "order_status", "order_purchase_timestamp",
        "order_approved_at", "order_delivered_carrier_date",
        "order_delivered_customer_date", "order_estimated_delivery_date",
    ), ("order_id",)),
    "customers": Source("olist_customers_dataset.csv", (
        "customer_id", "customer_unique_id", "customer_zip_code_prefix",
        "customer_city", "customer_state",
    ), ("customer_id",)),
    "items": Source("olist_order_items_dataset.csv", (
        "order_id", "order_item_id", "product_id", "seller_id",
        "shipping_limit_date", "price", "freight_value",
    ), ("order_id", "order_item_id")),
    "payments": Source("olist_order_payments_dataset.csv", (
        "order_id", "payment_sequential", "payment_type",
        "payment_installments", "payment_value",
    ), ("order_id", "payment_sequential")),
    "reviews": Source("olist_order_reviews_dataset.csv", (
        "review_id", "order_id", "review_score",
        "review_creation_date", "review_answer_timestamp",
    )),
    "products": Source("olist_products_dataset.csv", (
        "product_id", "product_category_name",
    ), ("product_id",)),
    "sellers": Source("olist_sellers_dataset.csv", (
        "seller_id", "seller_zip_code_prefix", "seller_city", "seller_state",
    ), ("seller_id",)),
    "categories": Source("product_category_name_translation.csv", (
        "product_category_name", "product_category_name_english",
    ), ("product_category_name",)),
}

DATE_COLUMNS = {
    "orders": (
        "order_purchase_timestamp", "order_approved_at",
        "order_delivered_carrier_date", "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ),
    "items": ("shipping_limit_date",),
    "reviews": ("review_creation_date", "review_answer_timestamp"),
}
MONEY_COLUMNS = {"items": ("price", "freight_value"), "payments": ("payment_value",)}
INTEGER_COLUMNS = {
    "items": {"order_item_id": (1, None)},
    "payments": {"payment_sequential": (1, None), "payment_installments": (0, None)},
    "reviews": {"review_score": (1, 5)},
}
