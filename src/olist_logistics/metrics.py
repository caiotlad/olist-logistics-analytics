import math

import pandas as pd


def number(value):
    if pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        return value if math.isfinite(float(value)) else None
    return float(value)


def overview(facts):
    eligible = facts.loc[facts["delivery_eligible"]]
    late = eligible.loc[eligible["delivered_late"].fillna(False)]
    products = facts["product_total_cents"].sum(min_count=1)
    freight = facts["freight_total_cents"].sum(min_count=1)
    delivered = int(facts["order_status"].eq("delivered").sum())
    return {
        "orders": len(facts),
        "delivered_orders": delivered,
        "eligible_orders": len(eligible),
        "excluded_delivered_orders": delivered - len(eligible),
        "late_orders": len(late),
        "late_rate": len(late) / len(eligible) if len(eligible) else None,
        "mean_delivery_days": number(eligible["delivery_days"].mean()),
        "median_delivery_days": number(eligible["delivery_days"].median()),
        "p90_delivery_days": number(eligible["delivery_days"].quantile(0.9)),
        "mean_late_calendar_days": number(late["delay_calendar_days"].mean()),
        "product_total_cents": None if pd.isna(products) else int(products),
        "freight_total_cents": None if pd.isna(freight) else int(freight),
        "freight_to_products_ratio": number(freight / products) if not pd.isna(products) and products > 0 else None,
        "canceled_orders": int(facts["order_status"].eq("canceled").sum()),
        "orders_without_items": int(facts["item_count"].eq(0).sum()),
        "orders_without_payments": int(facts["payment_count"].eq(0).sum()),
        "review_conflicts": int(facts["review_conflict"].sum()),
        "purchase_start": facts["order_purchase_timestamp"].min().isoformat() if facts["order_purchase_timestamp"].notna().any() else None,
        "purchase_end": facts["order_purchase_timestamp"].max().isoformat() if facts["order_purchase_timestamp"].notna().any() else None,
    }


def group_summary(frame, column, min_orders=30):
    rows = []
    for group, subset in frame.groupby(column, dropna=False, sort=True):
        eligible = subset.loc[subset["delivery_eligible"]]
        late_count = int(eligible["delivered_late"].fillna(False).sum())
        rows.append({
            column: "UNKNOWN" if pd.isna(group) else str(group),
            "orders": int(subset["order_id"].nunique()),
            "eligible_orders": len(eligible),
            "late_orders": late_count,
            "late_rate": late_count / len(eligible) if len(eligible) else None,
            "mean_delivery_days": number(eligible["delivery_days"].mean()),
            "p90_delivery_days": number(eligible["delivery_days"].quantile(0.9)),
            "product_total_cents": number(subset["product_total_cents"].sum(min_count=1)),
            "freight_total_cents": number(subset["freight_total_cents"].sum(min_count=1)),
            "reviewed_eligible_orders": int(eligible["review_score"].notna().sum()),
            "mean_review_score": number(eligible["review_score"].mean()),
            "meets_minimum": len(eligible) >= min_orders,
        })
    return pd.DataFrame(rows, columns=[
        column, "orders", "eligible_orders", "late_orders", "late_rate", "mean_delivery_days",
        "p90_delivery_days", "product_total_cents", "freight_total_cents",
        "reviewed_eligible_orders", "mean_review_score", "meets_minimum",
    ])


def review_summary(facts):
    eligible = facts.loc[facts["delivery_eligible"]]
    rows = []
    for late, label in ((False, "No prazo"), (True, "Com atraso")):
        subset = eligible.loc[eligible["delivered_late"].eq(late).fillna(False)]
        reviewed = subset.loc[subset["review_score"].notna()]
        rows.append({
            "delivery_group": label, "eligible_orders": len(subset),
            "reviewed_orders": len(reviewed), "mean_review_score": number(reviewed["review_score"].mean()),
            "low_score_rate": float(reviewed["review_score"].le(2).mean()) if len(reviewed) else None,
        })
    return pd.DataFrame(rows)


def summarize(marts, min_orders=30):
    facts = marts["fact_orders"]
    return {
        "overview": overview(facts),
        "by_state": group_summary(facts, "customer_state", min_orders),
        "by_month": group_summary(facts, "purchase_month", min_orders),
        "by_seller": group_summary(marts["seller_orders"], "seller_id", min_orders),
        "by_category": group_summary(marts["category_orders"], "category", min_orders),
        "by_review": review_summary(facts),
        "by_status": facts.groupby("order_status").size().rename("orders").reset_index(),
    }
