import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prepare_powerbi = script("prepare_powerbi")


class PowerBIContracts(unittest.TestCase):
    def test_official_schemas_and_visual_field_bindings_are_valid(self):
        try:
            validator = script("validate_powerbi")
        except ModuleNotFoundError:
            self.skipTest("Instale o extra validation para validar os esquemas Power BI.")
        result = validator.validate()
        self.assertEqual(result["pages"], 5)
        self.assertGreater(result["visuals"], 0)

    def test_filter_paths_have_one_direction_and_no_ambiguous_calendar_links(self):
        model = json.loads((ROOT / "powerbi/OlistLogistics.SemanticModel/model.bim").read_text(encoding="utf-8"))["model"]
        relations = model["relationships"]
        self.assertEqual({(r["fromTable"], r["toTable"]) for r in relations}, {
            ("fact_orders", "calendar"), ("seller_orders", "fact_orders"), ("category_orders", "fact_orders")
        })
        self.assertTrue(all(r["crossFilteringBehavior"] == "oneDirection" for r in relations))
        self.assertTrue(all(r["fromCardinality"] == "many" and r["toCardinality"] == "one" for r in relations))

    def test_group_tables_keep_the_minimum_sample_visible_in_the_filter(self):
        base = ROOT / "powerbi/OlistLogistics.Report/definition/pages"
        for page in ("categorias", "vendedores"):
            path = base / page / "visuals" / (page + "_detail") / "visual.json"
            visual = json.loads(path.read_text(encoding="utf-8"))
            condition = visual["filterConfig"]["filters"][0]["filter"]["Where"][0]["Condition"]["Comparison"]
            self.assertEqual(condition["ComparisonKind"], 2)
            self.assertEqual(condition["Right"]["Literal"]["Value"], "30L")
            self.assertFalse(visual["filterConfig"]["filters"][0]["isHiddenInViewMode"])

    def test_local_preparation_sets_the_checkout_data_path_without_editing_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            data = base / "data com espaço"
            data.mkdir()
            for name in prepare_powerbi.REQUIRED:
                (data / name).write_text("header\n", encoding="utf-8")
            original = (ROOT / "powerbi/OlistLogistics.SemanticModel/model.bim").read_bytes()
            project = prepare_powerbi.prepare(base / "prepared", data)
            self.assertTrue(project.exists())
            model = json.loads((project.parent / "OlistLogistics.SemanticModel/model.bim").read_text(encoding="utf-8"))
            parameter = next(e for e in model["model"]["expressions"] if e["name"] == "DataFolder")
            self.assertIn(data.resolve().as_posix(), parameter["expression"])
            self.assertEqual((ROOT / "powerbi/OlistLogistics.SemanticModel/model.bim").read_bytes(), original)

    def test_preparation_refuses_to_overwrite_an_existing_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            data = base / "data"
            data.mkdir()
            for name in prepare_powerbi.REQUIRED:
                (data / name).write_text("header\n", encoding="utf-8")
            target = base / "existing"
            target.mkdir()
            saved = target / "my-work.txt"
            saved.write_text("preserve", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "vazia"):
                prepare_powerbi.prepare(target, data)
            self.assertEqual(saved.read_text(encoding="utf-8"), "preserve")

    def test_preparation_requires_all_four_generated_marts(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "Execute o pipeline"):
                prepare_powerbi.prepare(Path(tmp) / "output", Path(tmp))

    def test_preparation_refuses_the_versioned_project_directory(self):
        with self.assertRaisesRegex(ValueError, "fora do checkout"):
            prepare_powerbi.prepare(ROOT / "powerbi", ROOT / "reports/generated")


if __name__ == "__main__":
    unittest.main()
