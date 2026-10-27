from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import tempfile
import zipfile

from .contracts import DATA_LICENSE, SOURCES, SOURCE_URL
from .quality import file_hash


def import_zip(archive, raw_dir):
    archive, raw_dir = Path(archive), Path(raw_dir)
    required = {spec.filename for spec in SOURCES.values()}
    with zipfile.ZipFile(archive) as source:
        candidates = {}
        for entry in source.infolist():
            filename = Path(entry.filename.replace("\\\\", "/")).name
            if filename in required:
                if filename in candidates:
                    raise ValueError(f"ZIP contém mais de um arquivo chamado {filename}.")
                if entry.file_size > 250 * 1024 * 1024:
                    raise ValueError("Um arquivo do ZIP ultrapassa o limite de tamanho.")
                candidates[filename] = entry
        missing = required - candidates.keys()
        if missing:
            raise ValueError("ZIP incompleto: " + ", ".join(sorted(missing)))
        raw_dir.mkdir(parents=True, exist_ok=True)
        # Extraio apenas os oito nomes esperados, sem usar os caminhos do ZIP.
        with tempfile.TemporaryDirectory(prefix="olist-import-") as temporary:
            staging = Path(temporary)
            for filename, entry in candidates.items():
                with source.open(entry) as reader, (staging / filename).open("wb") as writer:
                    shutil.copyfileobj(reader, writer)
            for filename in required:
                shutil.copyfile(staging / filename, raw_dir / filename)
    manifest = {
        "kind": "olist", "source_url": SOURCE_URL, "license": DATA_LICENSE,
        "archive_sha256": file_hash(archive),
        "imported_at_utc": datetime.now(timezone.utc).isoformat(),
        "files": {name: file_hash(raw_dir / name) for name in sorted(required)},
        "note": "Arquivo fornecido para importação; hashes permitem identificar os bytes usados.",
    }
    (raw_dir / "SOURCE.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest
