"""Valida PBIP/PBIR contra esquemas oficiais e confere suas referências locais."""
import argparse
import json
from pathlib import Path
import urllib.request
from urllib.parse import urlparse

from jsonschema import Draft7Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT7

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PIN = "379b75ac005bec60183cb39f49c176a1c2669493"
PREFIX = "https://developer.microsoft.com/json-schemas/"


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate(project_dir=None, cache=None):
    project_dir = Path(project_dir or ROOT / "powerbi")
    cache = Path(cache or ROOT / ".work/pbi-schemas")
    cache.mkdir(parents=True, exist_ok=True)

    def retrieve(uri):
        if not uri.startswith(PREFIX):
            raise ValueError("Referência de esquema inesperada: " + uri)
        relative = uri[len(PREFIX):]
        if ".." in Path(relative).parts or urlparse(uri).query:
            raise ValueError("Caminho de esquema inválido.")
        target = cache / relative.replace("/", "__")
        if not target.exists():
            url = "https://raw.githubusercontent.com/microsoft/json-schemas/" + SCHEMA_PIN + "/" + relative
            with urllib.request.urlopen(url, timeout=45) as response:
                target.write_bytes(response.read())
        return Resource.from_contents(read_json(target), default_specification=DRAFT7)

    registry = Registry(retrieve=retrieve)
    issues = []
    count = 0
    targets = [project_dir / "OlistLogistics.pbip", project_dir / "OlistLogistics.Report/definition.pbir", project_dir / "OlistLogistics.SemanticModel/definition.pbism"]
    targets.extend((project_dir / "OlistLogistics.Report/definition").rglob("*.json"))
    for path in targets:
        data = read_json(path)
        uri = data.get("$schema")
        if not uri:
            issues.append(str(path) + ": sem $schema")
            continue
        resource = retrieve(uri)
        validator = Draft7Validator(resource.contents, registry=registry)
        for error in validator.iter_errors(data):
            location = ".".join(map(str, error.absolute_path))
            issues.append(f"{path.relative_to(project_dir)}:{location}: {error.message}")
        count += 1

    model = read_json(project_dir / "OlistLogistics.SemanticModel/model.bim")["model"]
    tables = {table["name"]: table for table in model["tables"]}
    names = {name: {c["name"] for c in table["columns"]} for name, table in tables.items()}
    measures = {name: {m["name"] for m in table.get("measures", [])} for name, table in tables.items()}
    report = project_dir / "OlistLogistics.Report"
    pages = read_json(report / "definition/pages/pages.json")
    found_pages = {p.parent.name: read_json(p) for p in (report / "definition/pages").glob("*/page.json")}
    if set(pages["pageOrder"]) != set(found_pages):
        issues.append("A ordem de páginas não corresponde às páginas existentes.")
    roles = {"cardVisual": {"Data"}, "slicer": {"Values", "Tooltips"}, "tableEx": {"Values"}, "lineChart": {"Category", "Y", "Tooltips"}, "clusteredBarChart": {"Category", "Y", "Tooltips"}, "clusteredColumnChart": {"Category", "Y", "Tooltips"}, "textbox": set()}
    visual_count = 0
    for path in (report / "definition/pages").glob("*/visuals/*/visual.json"):
        visual_count += 1
        data = read_json(path)
        page = found_pages[path.parents[2].name]
        pos = data["position"]
        if pos["x"] < 0 or pos["y"] < 0 or pos["x"] + pos["width"] > page["width"] + 0.01 or pos["y"] + pos["height"] > page["height"] + 0.01:
            issues.append(data["name"] + ": visual fora da página")
        visual = data["visual"]
        query = visual.get("query", {}).get("queryState", {})
        if not set(query).issubset(roles[visual["visualType"]]):
            issues.append(data["name"] + ": papel de consulta inválido")
        for role in query.values():
            for projection in role["projections"]:
                kind = next(iter(projection["field"]))
                field = projection["field"][kind]
                table = field["Expression"]["SourceRef"]["Entity"]
                known = measures if kind == "Measure" else names
                if field["Property"] not in known.get(table, set()):
                    issues.append(data["name"] + ": campo inexistente " + table + "." + field["Property"])
    for relation in model["relationships"]:
        if relation["crossFilteringBehavior"] != "oneDirection":
            issues.append(relation["name"] + ": filtro bidirecional inesperado")
        for side in ("from", "to"):
            if relation[side + "Column"] not in names[relation[side + "Table"]]:
                issues.append(relation["name"] + ": relação inválida")
    if issues:
        raise ValueError("\n".join(issues))
    return {"schema_documents_validated": count, "pages": len(found_pages), "visuals": visual_count, "measures": sum(map(len, measures.values())), "desktop_rendering_checked": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", type=Path)
    parser.add_argument("--schema-cache", type=Path)
    args = parser.parse_args()
    print(json.dumps(validate(args.project_dir, args.schema_cache), ensure_ascii=False, indent=2))
