from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
import hashlib
from pathlib import Path

import pandas as pd

from .contracts import DATE_COLUMNS, INTEGER_COLUMNS, MONEY_COLUMNS, SOURCES


@dataclass(frozen=True)
class Issue:
    table: str
    rule: str
    severity: str
    affected_rows: int


class QualityError(ValueError):
    def __init__(self, issues):
        self.issues = list(issues)
        super().__init__("A base não passou nas verificações de qualidade.")


def to_cents(value):
    if pd.isna(value) or str(value).strip() == "":
        raise ValueError("Valor monetário ausente")
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount < 0 or amount > Decimal("90000000000000"):
            raise ValueError("Valor monetário inválido")
        cents = amount * 100
        if cents != cents.to_integral_value():
            raise ValueError("Valor monetário inválido")
        result = int(cents)
        if result > 9_000_000_000_000_000:
            raise ValueError("Valor monetário fora do limite")
        return result
    except (InvalidOperation, OverflowError) as error:
        raise ValueError("Valor monetário inválido") from error


def file_hash(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def read_sources(raw_dir):
    frames, manifest, missing = {}, {}, []
    raw_dir = Path(raw_dir)
    for name, spec in SOURCES.items():
        path = raw_dir / spec.filename
        if not path.is_file():
            missing.append(spec.filename)
            continue
        frame = pd.read_csv(path, dtype="string", keep_default_na=False, encoding="utf-8-sig")
        absent = sorted(set(spec.columns) - set(frame.columns))
        if absent:
            raise ValueError(f"{spec.filename}: colunas ausentes: {', '.join(absent)}")
        frames[name] = frame
        manifest[name] = {
            "file": spec.filename, "sha256": file_hash(path),
            "bytes": path.stat().st_size, "rows": len(frame),
            "columns": list(frame.columns),
            "blank_by_column": {column: int(frame[column].eq("").sum()) for column in frame},
        }
    if missing:
        raise FileNotFoundError("Arquivos necessários: " + ", ".join(missing))
    if frames["orders"].empty:
        raise ValueError("A tabela de pedidos está vazia.")
    return frames, manifest


def normalize_sources(frames):
    result, issues = {}, []
    for name, original in frames.items():
        frame = original.copy()
        for column in frame:
            frame[column] = frame[column].astype("string").str.strip().replace("", pd.NA)
        duplicated = frame.duplicated(keep="first")
        if duplicated.any():
            issues.append(Issue(name, "exact_duplicates_removed", "warning", int(duplicated.sum())))
            frame = frame.loc[~duplicated].copy()
        key = SOURCES[name].key
        if key:
            null_key = frame[list(key)].isna().any(axis=1)
            if null_key.any():
                issues.append(Issue(name, "missing_key", "error", int(null_key.sum())))
            conflicts = frame.duplicated(subset=list(key), keep=False)
            if conflicts.any():
                issues.append(Issue(name, "conflicting_key", "error", int(conflicts.sum())))
        for column in DATE_COLUMNS.get(name, ()):
            parsed = pd.to_datetime(frame[column], format="%Y-%m-%d %H:%M:%S", errors="coerce")
            invalid = frame[column].notna() & parsed.isna()
            if invalid.any():
                issues.append(Issue(name, "invalid_date:" + column, "error", int(invalid.sum())))
            frame[column] = parsed
        for column in MONEY_COLUMNS.get(name, ()):
            values, invalid = [], 0
            for value in frame[column]:
                try:
                    values.append(to_cents(value))
                except ValueError:
                    values.append(pd.NA)
                    invalid += 1
            if invalid:
                issues.append(Issue(name, "invalid_money:" + column, "error", invalid))
            frame[column + "_cents"] = pd.array(values, dtype="Int64")
        for column, (minimum, maximum) in INTEGER_COLUMNS.get(name, {}).items():
            numeric = pd.to_numeric(frame[column], errors="coerce")
            invalid = numeric.isna() | numeric.lt(minimum) | numeric.mod(1).ne(0)
            if maximum is not None:
                invalid |= numeric.gt(maximum)
            if invalid.any():
                issues.append(Issue(name, "invalid_integer:" + column, "error", int(invalid.sum())))
            frame[column] = numeric.where(~invalid).astype("Int64")
        result[name] = frame

    references = (
        ("orders", "customer_id", "customers", "customer_id"),
        ("items", "order_id", "orders", "order_id"),
        ("payments", "order_id", "orders", "order_id"),
        ("reviews", "order_id", "orders", "order_id"),
        ("items", "product_id", "products", "product_id"),
        ("items", "seller_id", "sellers", "seller_id"),
    )
    for table, column, parent, parent_key in references:
        invalid = ~result[table][column].isin(result[parent][parent_key])
        if invalid.any():
            issues.append(Issue(table, "orphan:" + column, "error", int(invalid.sum())))

    missing_review_id = result["reviews"]["review_id"].isna()
    if missing_review_id.any():
        issues.append(Issue("reviews", "missing_review_id", "error", int(missing_review_id.sum())))
    if any(issue.severity == "error" for issue in issues):
        raise QualityError(issues)
    for name, column in (("customers", "customer_state"), ("sellers", "seller_state")):
        result[name][column] = result[name][column].str.upper().fillna("UNKNOWN")
    result["orders"]["order_status"] = result["orders"]["order_status"].str.lower()
    if result["orders"]["order_status"].isna().any():
        raise QualityError([Issue("orders", "missing_status", "error", int(result["orders"]["order_status"].isna().sum()))])
    return result, issues


def issue_records(issues):
    return [asdict(issue) for issue in issues]
