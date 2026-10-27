"""Confere a base identificada no relatório usando pandas e PostgreSQL."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import urllib.request

from olist_logistics.ingest import import_zip
from olist_logistics.pipeline import run

ROOT = Path(__file__).resolve().parents[1]
DOWNLOAD_URL = "https://www.kaggle.com/api/v1/datasets/download/olistbr/brazilian-ecommerce?datasetVersionNumber=2"


def validate(raw_dir, output_dir, with_postgres):
    published = json.loads((ROOT / "reports/source_manifest.json").read_text(encoding="utf-8"))
    raw_dir, output_dir = Path(raw_dir), Path(output_dir)
    expected_files = published["source"]["files"]
    for name, expected in expected_files.items():
        path = raw_dir / name
        digest = hashlib.file_digest(path.open("rb"), "sha256").hexdigest()
        if digest != expected:
            raise ValueError("O arquivo não corresponde ao snapshot publicado: " + name)
    dsn = os.environ.get("DATABASE_URL") if with_postgres else None
    if with_postgres and not dsn:
        raise ValueError("Defina DATABASE_URL para conferir o PostgreSQL.")
    result = run(raw_dir, output_dir, 30, dsn)
    wanted = json.loads((ROOT / "reports/summary.json").read_text(encoding="utf-8"))
    for key, expected in wanted.items():
        observed = result["overview"][key]
        equal = math.isclose(observed, expected, rel_tol=1e-10, abs_tol=1e-10) if isinstance(expected, float) else observed == expected
        if not equal:
            raise ValueError("O resultado difere do snapshot publicado: " + key)
    audit = json.loads((output_dir / "quality.json").read_text(encoding="utf-8"))
    evidence = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "commit_sha": os.getenv("GITHUB_SHA"),
        "run_url": ("https://github.com/" + os.environ["GITHUB_REPOSITORY"] + "/actions/runs/" + os.environ["GITHUB_RUN_ID"]) if os.getenv("GITHUB_RUN_ID") else None,
        "source_csv_sha256_match": True,
        "published_metrics_match": True,
        "warehouse": audit.get("warehouse"),
        "overview": result["overview"],
        "desktop_validated": False,
        "note": "Esta execução valida a base e o SQL; a renderização e as medidas do Power BI são verificações separadas."
    }
    (output_dir / "validation.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--with-postgres", action="store_true")
    parser.add_argument("--raw-dir", type=Path, default=ROOT / "data/raw")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "reports/real-validation")
    args = parser.parse_args()
    if args.download:
        cache = ROOT / ".work/olist-real.zip"
        cache.parent.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(DOWNLOAD_URL, headers={"User-Agent": "olist-logistics-analytics/0.1"})
        with urllib.request.urlopen(request, timeout=180) as response, cache.open("wb") as destination:
            shutil.copyfileobj(response, destination)
        import_zip(cache, args.raw_dir)
    print(json.dumps(validate(args.raw_dir, args.output_dir, args.with_postgres), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
