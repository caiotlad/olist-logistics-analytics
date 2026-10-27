"""Prepara uma cópia local do PBIP com a pasta de dados deste checkout."""
import argparse
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = ("fact_orders.csv", "seller_orders.csv", "category_orders.csv", "calendar.csv")


def prepare(output, data_folder):
    output = Path(output).resolve()
    data_folder = Path(data_folder).resolve()
    if output == ROOT or ROOT in output.parents and ".work" not in output.relative_to(ROOT).parts:
        raise ValueError("Use uma pasta fora do checkout ou dentro de .work.")
    missing = [name for name in REQUIRED if not (data_folder / name).is_file()]
    if missing:
        raise ValueError("Execute o pipeline antes de preparar o Power BI: " + ", ".join(missing))
    if output.exists() and any(output.iterdir()):
        raise ValueError("Escolha uma pasta de saída vazia para preservar trabalhos já salvos.")
    output.mkdir(parents=True, exist_ok=True)
    for name in ("OlistLogistics.Report", "OlistLogistics.SemanticModel"):
        shutil.copytree(ROOT / "powerbi" / name, output / name, ignore=shutil.ignore_patterns(".pbi"), dirs_exist_ok=True)
    shutil.copyfile(ROOT / "powerbi/OlistLogistics.pbip", output / "OlistLogistics.pbip")
    model_file = output / "OlistLogistics.SemanticModel/model.bim"
    model = json.loads(model_file.read_text(encoding="utf-8"))
    parameter = next(e for e in model["model"]["expressions"] if e["name"] == "DataFolder")
    parameter["expression"] = '"' + data_folder.as_posix().replace('"', '""') + '" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]'
    model_file.write_text(json.dumps(model, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output / "OlistLogistics.pbip"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / ".work/powerbi-local")
    parser.add_argument("--data-folder", type=Path, default=ROOT / "reports/generated")
    args = parser.parse_args()
    print(prepare(args.output, args.data_folder))
