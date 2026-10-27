import copy
import os
import unittest

from olist_logistics.demo import demo_frames
from olist_logistics.marts import build_marts
from olist_logistics.metrics import overview
from olist_logistics.quality import normalize_sources
from olist_logistics.warehouse import connect_and_load


@unittest.skipUnless(os.getenv("DATABASE_URL"), "Defina DATABASE_URL para os testes com PostgreSQL.")
class WarehouseTests(unittest.TestCase):
    def setUp(self):
        import psycopg
        self.psycopg = psycopg
        self.dsn = os.environ["DATABASE_URL"]
        self.source, _ = normalize_sources(demo_frames())
        self.expected = overview(build_marts(self.source)["fact_orders"])

    def test_sql_metrics_match_pandas_and_reloads_do_not_duplicate_orders(self):
        result = connect_and_load(self.source, self.dsn, self.expected)
        self.assertTrue(result["overview_matches_pandas"])
        connect_and_load(self.source, self.dsn, self.expected)
        with self.psycopg.connect(self.dsn) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM olist_mart.fact_orders").fetchone()[0], 8)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM olist_mart.seller_orders").fetchone()[0], 9)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM olist_mart.category_orders").fetchone()[0], 10)
            self.assertEqual(connection.execute("SELECT product_total_cents FROM olist_mart.fact_orders WHERE order_id = 'o1'").fetchone()[0], 3000)

    def test_metric_divergence_rolls_back_the_entire_snapshot(self):
        connect_and_load(self.source, self.dsn, self.expected)
        changed = demo_frames()
        changed["items"].loc[0, "price"] = "99.00"
        normalized, _ = normalize_sources(changed)
        incorrect = overview(build_marts(normalized)["fact_orders"])
        incorrect["late_orders"] += 1
        with self.assertRaisesRegex(RuntimeError, "diverge"):
            connect_and_load(normalized, self.dsn, incorrect)
        with self.psycopg.connect(self.dsn) as connection:
            value = connection.execute("SELECT product_total_cents FROM olist_mart.fact_orders WHERE order_id = 'o1'").fetchone()[0]
            self.assertEqual(value, 3000)


if __name__ == "__main__":
    unittest.main()
