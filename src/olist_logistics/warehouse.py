from importlib.resources import files
import math

import pandas as pd

from .contracts import SOURCES


def connect_and_load(sources, dsn, expected):
    try:
        import psycopg
        from psycopg import sql
        from psycopg.rows import dict_row
    except ImportError as error:
        raise RuntimeError("Instale o extra postgres: pip install -e '.[postgres]'") from error

    with psycopg.connect(dsn, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(846120261)")
            cursor.execute("CREATE SCHEMA IF NOT EXISTS olist_stage")
            cursor.execute("CREATE SCHEMA IF NOT EXISTS olist_meta")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS olist_meta.loads (
                    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    loaded_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    orders bigint NOT NULL
                )
            """)
            for name, spec in SOURCES.items():
                table = sql.Identifier("olist_stage", name)
                definitions = sql.SQL(", ").join(sql.SQL("{} text").format(sql.Identifier(column)) for column in spec.columns)
                cursor.execute(sql.SQL("CREATE TABLE IF NOT EXISTS {} ({})").format(table, definitions))
                cursor.execute(sql.SQL("TRUNCATE {}").format(table))
                columns = sql.SQL(", ").join(map(sql.Identifier, spec.columns))
                with cursor.copy(sql.SQL("COPY {} ({}) FROM STDIN").format(table, columns)) as copier:
                    for row in sources[name][list(spec.columns)].itertuples(index=False, name=None):
                        copier.write_row(tuple(None if pd.isna(value) else str(value) for value in row))
            cursor.execute(files("olist_logistics").joinpath("sql/001_marts.sql").read_text(encoding="utf-8"))
            cursor.execute(files("olist_logistics").joinpath("sql/002_overview.sql").read_text(encoding="utf-8"))
            actual = dict(cursor.fetchone())
            for key, wanted in expected.items():
                observed = actual[key]
                if key in ("purchase_start", "purchase_end"):
                    observed = observed.isoformat() if observed is not None else None
                if wanted is None:
                    equal = observed is None
                elif isinstance(wanted, float):
                    equal = observed is not None and math.isclose(float(observed), wanted, rel_tol=1e-10, abs_tol=1e-10)
                else:
                    equal = observed == wanted
                if not equal:
                    raise RuntimeError(f"Métrica SQL diverge do pandas: {key}. Carga revertida.")
            cursor.execute("INSERT INTO olist_meta.loads (orders) VALUES (%s)", (expected["orders"],))
            return {"overview_matches_pandas": True, "metrics_compared": len(expected)}
