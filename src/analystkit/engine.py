"""analystkit.engine — one mental model: any source becomes view `t`.

CSV / Excel / SQLite via DuckDB; PostgreSQL and MySQL via analystkit.dbconnect.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb

from analystkit.core import AnalystKitError, _ident, _path_lit


def load_source(
    path: Path, table: str | None = None
) -> duckdb.DuckDBPyConnection:
    """Opens any supported source and exposes it as view `t`.

    Whatever the source (file export or database), every downstream
    query is written identically. One mental model, three source types.
    """
    if not path.exists():
        raise AnalystKitError(f"Source not found: {path}")
    con = duckdb.connect()
    suffix = path.suffix.lower()

    if suffix == ".csv":
        con.execute(
            f"CREATE VIEW t AS SELECT * FROM read_csv_auto({_path_lit(path)})"
        )
        return con
    if suffix in (".xlsx", ".xls"):
        import pandas as pd
        con.register("t", pd.read_excel(path))
        return con
    if suffix in (".sqlite", ".db", ".sqlite3"):
        con.execute(f"ATTACH {_path_lit(path)} AS src (TYPE sqlite)")
        rows = con.execute(
            "SELECT table_name FROM duckdb_tables() WHERE database_name = 'src'"
        ).fetchall()
        tables = [str(r[0]) for r in rows]
        if not tables:
            raise AnalystKitError(f"No tables found in database: {path}")
        if table is None:
            if len(tables) > 1:
                raise AnalystKitError(
                    f"Database has {len(tables)} tables: {tables}. Pick one with --table."
                )
            table = tables[0]
        if table not in tables:
            raise AnalystKitError(f"Table '{table}' not found. Available: {tables}")
        con.execute(f"CREATE VIEW t AS SELECT * FROM src.{_ident(table)}")
        return con
    raise AnalystKitError(
        f"Unsupported source '{suffix}'. Use .csv, .xlsx, .sqlite or .db."
    )


def columns_of(con: duckdb.DuckDBPyConnection) -> list[tuple[str, str]]:
    """Returns [(column_name, duckdb_type), ...] for view t."""
    return [(str(r[0]), str(r[1])) for r in con.execute("DESCRIBE t").fetchall()]


def _show(sql: str, show_sql: bool) -> None:
    if show_sql:
        print("\n-- SQL executed ------------------------------------------")
        print(sql.strip())
        print("----------------------------------------------------------")


def _print_table(
    headers: list[str], rows: list[tuple[Any, ...]], limit: int = 60
) -> None:
    widths = [len(h) for h in headers]
    shown = rows[:limit]
    for row in shown:
        for i, val in enumerate(row):
            widths[i] = max(widths[i], len(str(val)))
    line = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    print(line)
    print("-" * len(line))
    for row in shown:
        print("  ".join(str(v).ljust(widths[i]) for i, v in enumerate(row)))
    if len(rows) > limit:
        print(f"... {len(rows) - limit} more rows")

