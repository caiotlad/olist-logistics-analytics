from datetime import datetime, timezone
import json
from pathlib import Path

from .contracts import DATA_LICENSE, SOURCE_URL
from .marts import build_marts
from .metrics import summarize
from .quality import QualityError, issue_records, normalize_sources, read_sources
from .report import write_report


def run(raw_dir, output_dir, min_orders=30, dsn=None):
    if min_orders < 1:
        raise ValueError("A amostra mínima precisa ser positiva.")
    raw_dir, output_dir = Path(raw_dir), Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    frames, manifest = read_sources(raw_dir)
    source_file = raw_dir / "SOURCE.json"
    source = json.loads(source_file.read_text(encoding="utf-8")) if source_file.exists() else {
        "kind": "provided", "source_url": SOURCE_URL,
        "note": "Arquivos fornecidos sem manifesto de importação.",
    }
    expected_hashes = source.get("files", {})
    for entry in manifest.values():
        if entry["file"] in expected_hashes and expected_hashes[entry["file"]] != entry["sha256"]:
            raise ValueError("Arquivo alterado depois da importação: " + entry["file"])
    audit = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": source, "dataset_license": DATA_LICENSE, "files": manifest,
        "minimum_group_orders": min_orders, "status": "failed",
    }
    try:
        sources, issues = normalize_sources(frames)
    except QualityError as error:
        audit["issues"] = issue_records(error.issues)
        (output_dir / "quality.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
        raise
    marts = build_marts(sources)
    summary = summarize(marts, min_orders)
    if dsn is not None:
        from .warehouse import connect_and_load
        audit["warehouse"] = connect_and_load(sources, dsn, summary["overview"])
    audit["status"] = "passed"
    audit["issues"] = issue_records(issues)
    audit["delivery_exclusions"] = summary["overview"]["excluded_delivered_orders"]
    audit["review_conflicts"] = summary["overview"]["review_conflicts"]
    for name, frame in marts.items():
        frame.to_csv(output_dir / (name + ".csv"), index=False, encoding="utf-8-sig")
    (output_dir / "quality.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    report = write_report(output_dir, summary, audit, source)
    return {"overview": summary["overview"], "report": str(report), "source_kind": source["kind"]}
