from pathlib import Path
import json

import pandas as pd

from .contracts import SOURCES


def demo_frames():
    orders = []
    definitions = [
        ("o1", "c1", "delivered", "2018-01-05 21:00:00", "2018-01-05 00:00:00"),
        ("o2", "c2", "delivered", "2018-01-10 16:00:00", "2018-01-07 00:00:00"),
        ("o3", "c3", "canceled", "", "2018-01-15 00:00:00"),
        ("o4", "c4", "delivered", "", "2018-01-15 00:00:00"),
        ("o5", "c5", "delivered", "2017-12-31 12:00:00", "2018-01-15 00:00:00"),
        ("o6", "c6", "shipped", "", "2018-01-15 00:00:00"),
        ("o7", "c7", "delivered", "2018-01-03 12:00:00", "2018-01-08 00:00:00"),
        ("o8", "c8", "delivered", "2018-01-04 12:00:00", "2018-01-08 00:00:00"),
    ]
    for order_id, customer_id, status, delivered, estimate in definitions:
        orders.append([order_id, customer_id, status, "2018-01-01 12:00:00",
                       "2018-01-01 13:00:00", "2018-01-02 12:00:00", delivered, estimate])
    customers = [
        [f"c{i}", "repeat-customer" if i in (1, 2) else f"unique-{i}",
         "01234", "cidade de teste", "RJ" if i == 2 else "SP"]
        for i in range(1, 9)
    ]
    items = [
        ["o1", "1", "p1", "s1", "2018-01-02 00:00:00", "10.00", "2.00"],
        ["o1", "2", "p2", "s1", "2018-01-02 00:00:00", "20.00", "3.00"],
        ["o2", "1", "p1", "s1", "2018-01-02 00:00:00", "30.00", "4.00"],
        ["o2", "2", "p2", "s2", "2018-01-02 00:00:00", "40.00", "6.00"],
    ]
    for i in range(3, 9):
        items.append([f"o{i}", "1", "p3" if i == 4 else "p1", "s2",
                      "2018-01-02 00:00:00", "10.00", "0.00" if i == 7 else "2.00"])
    payments = [
        ["o1", "1", "credit_card", "1", "15.00"],
        ["o1", "2", "voucher", "1", "20.00"],
        ["o2", "1", "credit_card", "2", "80.00"],
    ]
    payments += [[f"o{i}", "1", "boleto", "1", "12.00"] for i in (3, 4, 5, 6, 8)]
    reviews = [
        ["r-old", "o1", "2", "2018-01-04 00:00:00", "2018-01-04 18:00:00"],
        ["r-new", "o1", "5", "2018-01-05 00:00:00", "2018-01-06 18:00:00"],
        ["r-two", "o2", "1", "2018-01-07 00:00:00", "2018-01-11 18:00:00"],
        ["r-seven", "o7", "4", "2018-01-03 00:00:00", "2018-01-04 18:00:00"],
    ]
    rows = {
        "orders": orders, "customers": customers, "items": items, "payments": payments,
        "reviews": reviews,
        "products": [["p1", "cafe"], ["p2", "alimentos"], ["p3", ""]],
        "sellers": [["s1", "01234", "cidade um", "SP"], ["s2", "30000", "cidade dois", "MG"]],
        "categories": [["cafe", "coffee"], ["alimentos", "food"]],
    }
    return {name: pd.DataFrame(values, columns=SOURCES[name].columns, dtype="string")
            for name, values in rows.items()}


def write_demo(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for name, frame in demo_frames().items():
        frame.to_csv(directory / SOURCES[name].filename, index=False, encoding="utf-8")
    (directory / "SOURCE.json").write_text(json.dumps({
        "kind": "synthetic", "description": "Dados artificiais de demonstração. Não são resultados da Olist."
    }, ensure_ascii=False, indent=2), encoding="utf-8")
