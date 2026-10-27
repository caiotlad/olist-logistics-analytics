import argparse
import json
import os
from pathlib import Path
import sys

from .demo import write_demo
from .ingest import import_zip
from .pipeline import run


def main(argv=None):
    parser = argparse.ArgumentParser(description="Olist Logistics: carga, qualidade e análise de entregas.")
    commands = parser.add_subparsers(dest="command", required=True)
    importer = commands.add_parser("import-zip", help="Importar os oito CSVs necessários de um ZIP.")
    importer.add_argument("archive", type=Path)
    importer.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    for name, help_text in (("run", "Analisar os CSVs importados."), ("demo", "Executar com dados sintéticos.")):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--raw-dir", type=Path, default=Path("data/demo" if name == "demo" else "data/raw"))
        command.add_argument("--output-dir", type=Path, default=Path("reports/demo" if name == "demo" else "reports/generated"))
        command.add_argument("--min-orders", type=int, default=1 if name == "demo" else 30)
        command.add_argument("--with-postgres", action="store_true", help="Carregar PostgreSQL e conferir as métricas SQL.")
    args = parser.parse_args(argv)
    try:
        if args.command == "import-zip":
            result = import_zip(args.archive, args.raw_dir)
            print(json.dumps({"raw_dir": str(args.raw_dir), "archive_sha256": result["archive_sha256"]}, ensure_ascii=False))
            return 0
        dsn = os.getenv("DATABASE_URL") if args.with_postgres else None
        if args.with_postgres and not dsn:
            raise ValueError("Defina DATABASE_URL para usar PostgreSQL.")
        if args.command == "demo":
            if (args.raw_dir / "SOURCE.json").exists():
                previous = json.loads((args.raw_dir / "SOURCE.json").read_text(encoding="utf-8"))
                if previous.get("kind") != "synthetic":
                    raise ValueError("O diretório de demonstração contém uma base não sintética.")
            elif args.raw_dir.exists() and any(args.raw_dir.iterdir()):
                raise ValueError("Escolha um diretório vazio para os dados sintéticos.")
            write_demo(args.raw_dir)
        result = run(args.raw_dir, args.output_dir, args.min_orders, dsn)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (ValueError, OSError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
