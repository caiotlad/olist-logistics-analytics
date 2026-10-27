import copy
from pathlib import Path
import tempfile
import unittest
import zipfile

import pandas as pd

from olist_logistics.contracts import SOURCES
from olist_logistics.demo import demo_frames, write_demo
from olist_logistics.ingest import import_zip
from olist_logistics.marts import build_marts
from olist_logistics.metrics import overview, summarize
from olist_logistics.pipeline import run
from olist_logistics.quality import QualityError, normalize_sources, read_sources, to_cents


class QualityTests(unittest.TestCase):
    def setUp(self):
        self.frames = demo_frames()

    def test_money_is_exact_in_cents(self):
        self.assertEqual(to_cents("0.10"), 10)
        self.assertEqual(to_cents("123.45"), 12345)
        self.assertEqual(to_cents("0.00"), 0)

    def test_invalid_money_is_rejected(self):
        for value in ("", "-1", "1.001", "NaN", "Infinity", "1e1000000"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                to_cents(value)

    def test_exact_duplicate_is_removed_with_a_warning(self):
        self.frames["orders"] = pd.concat([self.frames["orders"], self.frames["orders"].iloc[[0]]])
        normalized, issues = normalize_sources(self.frames)
        self.assertEqual(len(normalized["orders"]), 8)
        self.assertTrue(any(issue.rule == "exact_duplicates_removed" for issue in issues))

    def test_conflicting_order_key_stops_the_load(self):
        extra = self.frames["orders"].iloc[[0]].copy()
        extra["order_status"] = "canceled"
        self.frames["orders"] = pd.concat([self.frames["orders"], extra])
        with self.assertRaises(QualityError):
            normalize_sources(self.frames)

    def test_foreign_key_is_validated(self):
        self.frames["orders"].loc[0, "customer_id"] = "unknown-customer"
        with self.assertRaises(QualityError) as caught:
            normalize_sources(self.frames)
        self.assertTrue(any(issue.rule == "orphan:customer_id" for issue in caught.exception.issues))

    def test_invalid_date_is_not_silently_discarded(self):
        self.frames["orders"].loc[0, "order_purchase_timestamp"] = "2018-99-01"
        with self.assertRaises(QualityError):
            normalize_sources(self.frames)

    def test_invalid_review_score_is_rejected(self):
        self.frames["reviews"].loc[0, "review_score"] = "7"
        with self.assertRaises(QualityError):
            normalize_sources(self.frames)

    def test_missing_review_identifier_is_rejected(self):
        self.frames["reviews"].loc[0, "review_id"] = ""
        with self.assertRaises(QualityError):
            normalize_sources(self.frames)

    def test_zero_installments_and_zero_freight_are_preserved(self):
        self.frames["payments"].loc[0, "payment_installments"] = "0"
        normalized, _ = normalize_sources(self.frames)
        self.assertEqual(normalized["payments"].loc[0, "payment_installments"], 0)
        self.assertEqual(normalized["items"].loc[normalized["items"]["order_id"].eq("o7"), "freight_value_cents"].iloc[0], 0)

    def test_zip_prefix_remains_text(self):
        normalized, _ = normalize_sources(self.frames)
        self.assertEqual(normalized["customers"].loc[0, "customer_zip_code_prefix"], "01234")


class MartTests(unittest.TestCase):
    def setUp(self):
        self.frames = demo_frames()
        normalized, _ = normalize_sources(self.frames)
        self.marts = build_marts(normalized)
        self.facts = self.marts["fact_orders"].set_index("order_id")

    def test_join_keeps_one_row_per_order(self):
        self.assertEqual(len(self.facts), 8)
        self.assertTrue(self.facts.index.is_unique)

    def test_items_and_payments_are_aggregated_before_join(self):
        row = self.facts.loc["o1"]
        self.assertEqual(row["item_count"], 2)
        self.assertEqual(row["payment_count"], 2)
        self.assertEqual(row["product_total_cents"], 3000)
        self.assertEqual(row["freight_total_cents"], 500)
        self.assertEqual(row["payment_total_cents"], 3500)

    def test_customer_unique_id_does_not_collapse_orders(self):
        self.assertEqual(self.facts["customer_unique_id"].eq("repeat-customer").sum(), 2)

    def test_delivery_on_the_promised_day_is_on_time(self):
        self.assertFalse(self.facts.loc["o1", "delivered_late"])
        self.assertEqual(self.facts.loc["o1", "delay_calendar_days"], 0)

    def test_late_days_use_calendar_dates(self):
        self.assertTrue(self.facts.loc["o2", "delivered_late"])
        self.assertEqual(self.facts.loc["o2", "delay_calendar_days"], 3)

    def test_missing_and_inconsistent_dates_are_excluded(self):
        for order in ("o4", "o5"):
            self.assertFalse(self.facts.loc[order, "delivery_eligible"])
            self.assertTrue(pd.isna(self.facts.loc[order, "delivered_late"]))
        self.assertEqual(overview(self.facts)["excluded_delivered_orders"], 2)

    def test_missing_payment_is_not_filled_with_zero(self):
        self.assertEqual(self.facts.loc["o7", "payment_count"], 0)
        self.assertTrue(pd.isna(self.facts.loc["o7", "payment_total_cents"]))

    def test_latest_review_is_used_once(self):
        self.assertEqual(self.facts.loc["o1", "review_score"], 5)
        self.assertEqual(self.facts.loc["o1", "review_count"], 2)

    def test_ambiguous_latest_review_has_no_arbitrary_score(self):
        extra = self.frames["reviews"].iloc[[1]].copy()
        extra["review_score"] = "1"
        self.frames["reviews"] = pd.concat([self.frames["reviews"], extra])
        source, _ = normalize_sources(self.frames)
        facts = build_marts(source)["fact_orders"].set_index("order_id")
        self.assertTrue(facts.loc["o1", "review_conflict"])
        self.assertTrue(pd.isna(facts.loc["o1", "review_score"]))

    def test_missing_category_is_kept_as_unknown(self):
        category = self.marts["category_orders"].set_index("order_id").loc["o4", "category"]
        self.assertEqual(category, "__unknown__")

    def test_seller_groups_are_overlapping_participation_groups(self):
        bridge = self.marts["seller_orders"]
        self.assertFalse(bridge.duplicated(["order_id", "seller_id"]).any())
        self.assertEqual(len(bridge), 9)
        self.assertEqual(len(bridge.loc[bridge["order_id"].eq("o2")]), 2)

    def test_category_bridge_preserves_its_grain(self):
        bridge = self.marts["category_orders"]
        self.assertFalse(bridge.duplicated(["order_id", "category"]).any())
        self.assertEqual(len(bridge), 10)

    def test_overview_has_explicit_denominators(self):
        result = overview(self.facts)
        self.assertEqual(result["orders"], 8)
        self.assertEqual(result["eligible_orders"], 4)
        self.assertEqual(result["late_orders"], 1)
        self.assertEqual(result["late_rate"], 0.25)
        self.assertEqual(result["product_total_cents"], 16000)
        self.assertEqual(result["freight_total_cents"], 2500)
        self.assertEqual(result["freight_to_products_ratio"], 0.15625)

    def test_empty_denominator_is_unavailable_not_zero(self):
        self.frames["orders"]["order_status"] = "shipped"
        normalized, _ = normalize_sources(self.frames)
        result = overview(build_marts(normalized)["fact_orders"])
        self.assertIsNone(result["late_rate"])
        self.assertIsNone(result["mean_delivery_days"])
        self.assertIsNone(result["p90_delivery_days"])

    def test_empty_reviews_remain_missing(self):
        self.frames["reviews"] = self.frames["reviews"].iloc[:0]
        normalized, _ = normalize_sources(self.frames)
        summary = summarize(build_marts(normalized), 1)
        self.assertEqual(summary["by_review"]["reviewed_orders"].sum(), 0)
        self.assertTrue(summary["by_review"]["mean_review_score"].isna().all())


class FileFlowTests(unittest.TestCase):
    def _archive(self, root):
        original = root / "original"
        write_demo(original)
        archive = root / "source.zip"
        with zipfile.ZipFile(archive, "w") as zipped:
            for spec in SOURCES.values():
                zipped.write(original / spec.filename, arcname="nested/" + spec.filename)
            zipped.writestr("../outside.txt", "must not be extracted")
        return archive

    def test_zip_import_is_scoped_and_fingerprinted(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = import_zip(self._archive(root), root / "raw")
            self.assertEqual(len(manifest["files"]), 8)
            self.assertFalse((root / "outside.txt").exists())
            frames, _ = read_sources(root / "raw")
            self.assertEqual(len(frames["orders"]), 8)

    def test_incomplete_zip_does_not_replace_an_existing_snapshot(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "bad.zip"
            with zipfile.ZipFile(archive, "w") as zipped:
                zipped.writestr("unknown.csv", "x")
            with self.assertRaises(ValueError):
                import_zip(archive, root / "raw")
            self.assertFalse((root / "raw").exists())

    def test_demo_produces_a_self_contained_report(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_demo(root / "raw")
            result = run(root / "raw", root / "report", 1)
            text = Path(result["report"]).read_text(encoding="utf-8")
            self.assertIn("DADOS SINTÉTICOS", text)
            self.assertIn("data:image/png;base64,", text)
            self.assertTrue((root / "report" / "fact_orders.csv").exists())
            self.assertTrue((root / "report" / "quality.json").exists())

    def test_changed_imported_file_is_detected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            import_zip(self._archive(root), root / "raw")
            with (root / "raw" / SOURCES["items"].filename).open("a", encoding="utf-8") as writer:
                writer.write("\n")
            with self.assertRaisesRegex(ValueError, "alterado"):
                run(root / "raw", root / "report", 1)


if __name__ == "__main__":
    unittest.main()
