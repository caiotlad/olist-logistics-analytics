import pandas as pd


def _reviews_by_order(reviews):
    if reviews.empty:
        return pd.DataFrame(columns=["order_id", "review_score", "review_count", "review_conflict"])
    ordered = reviews.sort_values(
        ["order_id", "review_answer_timestamp", "review_creation_date", "review_id"],
        na_position="first", kind="stable",
    )
    latest = ordered.drop_duplicates("order_id", keep="last").copy()
    # Notas divergentes no mesmo instante e identificador não recebem um desempate arbitrário.
    tie_keys = ["order_id", "review_answer_timestamp", "review_creation_date", "review_id"]
    ambiguity = ordered.groupby(tie_keys, dropna=False)["review_score"].nunique().gt(1).rename("review_conflict").reset_index()
    latest = latest.merge(ambiguity, on=tie_keys, how="left", validate="one_to_one")
    latest.loc[latest["review_conflict"], "review_score"] = pd.NA
    counts = ordered.groupby("order_id").size().rename("review_count")
    return latest[["order_id", "review_score", "review_conflict"]].merge(
        counts, on="order_id", validate="one_to_one",
    )


def build_marts(sources):
    orders, items, payments = sources["orders"], sources["items"], sources["payments"]
    customers = sources["customers"]
    item_totals = items.groupby("order_id", as_index=False).agg(
        item_count=("order_item_id", "size"),
        seller_count=("seller_id", "nunique"),
        product_total_cents=("price_cents", "sum"),
        freight_total_cents=("freight_value_cents", "sum"),
    )
    payment_totals = payments.groupby("order_id", as_index=False).agg(
        payment_count=("payment_sequential", "size"),
        payment_total_cents=("payment_value_cents", "sum"),
    )
    facts = orders.merge(customers, on="customer_id", how="left", validate="many_to_one")
    facts = facts.merge(item_totals, on="order_id", how="left", validate="one_to_one")
    facts = facts.merge(payment_totals, on="order_id", how="left", validate="one_to_one")
    facts = facts.merge(_reviews_by_order(sources["reviews"]), on="order_id", how="left", validate="one_to_one")
    for column in ("item_count", "seller_count", "payment_count", "review_count"):
        facts[column] = pd.to_numeric(facts[column], errors="coerce").fillna(0).astype("Int64")
    for column in ("product_total_cents", "freight_total_cents", "payment_total_cents", "review_score"):
        facts[column] = pd.to_numeric(facts[column], errors="coerce").astype("Int64")
    facts["review_conflict"] = facts["review_conflict"].astype("boolean").fillna(False).astype(bool)
    purchase = facts["order_purchase_timestamp"]
    delivered = facts["order_delivered_customer_date"]
    estimated = facts["order_estimated_delivery_date"]
    facts["purchase_date"] = purchase.dt.normalize()
    facts["purchase_month"] = purchase.dt.strftime("%Y-%m").astype("string")
    facts["delivery_eligible"] = (
        facts["order_status"].eq("delivered")
        & purchase.notna() & delivered.notna() & estimated.notna()
        & delivered.ge(purchase) & estimated.dt.normalize().ge(purchase.dt.normalize())
    )
    facts["delivered_late"] = pd.Series(pd.NA, index=facts.index, dtype="boolean")
    eligible = facts["delivery_eligible"]
    facts.loc[eligible, "delivered_late"] = delivered.loc[eligible].dt.normalize().gt(estimated.loc[eligible].dt.normalize())
    facts["delivery_days"] = (delivered - purchase).dt.total_seconds().div(86400).where(eligible)
    facts["delay_calendar_days"] = (delivered.dt.normalize() - estimated.dt.normalize()).dt.days.where(eligible).astype("Int64")
    facts["freight_ratio"] = (facts["freight_total_cents"] / facts["product_total_cents"].where(facts["product_total_cents"].gt(0))).astype("Float64")

    category_items = items.merge(
        sources["products"][["product_id", "product_category_name"]],
        on="product_id", how="left", validate="many_to_one",
    )
    category_items["category"] = category_items["product_category_name"].fillna("__unknown__")
    category_bridge = category_items.groupby(["order_id", "category"], as_index=False).agg(
        item_count=("order_item_id", "size"),
        product_total_cents=("price_cents", "sum"),
        freight_total_cents=("freight_value_cents", "sum"),
    )
    seller_bridge = items.groupby(["order_id", "seller_id"], as_index=False).agg(
        item_count=("order_item_id", "size"),
        product_total_cents=("price_cents", "sum"),
        freight_total_cents=("freight_value_cents", "sum"),
    ).merge(sources["sellers"][["seller_id", "seller_state"]], on="seller_id", how="left", validate="many_to_one")
    context = facts[["order_id", "purchase_date", "purchase_month", "customer_state",
                     "delivery_eligible", "delivered_late", "delivery_days", "review_score"]]
    seller_bridge = seller_bridge.merge(context, on="order_id", how="left", validate="many_to_one")
    category_bridge = category_bridge.merge(context, on="order_id", how="left", validate="many_to_one")

    observed = purchase.dropna()
    calendar = pd.DataFrame({"date": pd.date_range(observed.min().normalize(), observed.max().normalize())}) if len(observed) else pd.DataFrame({"date": pd.Series(dtype="datetime64[ns]")})
    calendar["year"] = calendar["date"].dt.year
    calendar["month"] = calendar["date"].dt.month
    calendar["year_month"] = calendar["date"].dt.strftime("%Y-%m")
    return {"fact_orders": facts, "seller_orders": seller_bridge, "category_orders": category_bridge, "calendar": calendar}
