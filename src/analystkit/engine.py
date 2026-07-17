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
        # Explicit read_csv parameters per the DuckDB CSV documentation
        # (docs.duckdb.org/data/csv/overview.html):
        #   header=true        first row is column names (RFC 4180 default)
        #   quote=double-quote RFC 4180 quoting so a field containing a
        #                      comma inside quotes is ONE value, not two cols
        #   strict_mode=false  if a row cannot be parsed, record the error
        #                      and continue — same as Excel and every real
        #                      production CSV tool; read_csv_auto used
        #                      sample-based quoting detection which fails on
        #                      large files where complex rows appear after
        #                      the detection sample window.
        dq = '"'   # double-quote literal — avoids nested quotes in f-string
        sql = (
            f"CREATE VIEW t AS SELECT * FROM read_csv("
            f"{_path_lit(path)}, "
            f"header=true, "
            f"quote={dq!r}, "
            f"strict_mode=false)"
        )
        try:
            con.execute(sql)
        except Exception as exc:
            raise AnalystKitError(
                f"Could not open {path.name!r} as a CSV file. "
                f"Verify it is a valid CSV and is not corrupted. "
                f"DuckDB detail: {exc}"
            ) from exc
        return con
    if suffix == ".parquet":
        # v2.1.0 — Apache Parquet (the warehouse-extract lingua franca;
        # format specification at parquet.apache.org / the parquet-format
        # repository, Thrift IDL authoritative). Loaded via DuckDB's
        # native read_parquet.
        try:
            con.execute(
                f"CREATE VIEW t AS SELECT * FROM read_parquet("
                f"{_path_lit(path)})"
            )
        except Exception as exc:
            raise AnalystKitError(
                f"Could not open {path.name!r} as a Parquet file. Verify "
                f"it is a valid Parquet file (a renamed CSV is not one). "
                f"DuckDB detail: {exc}"
            ) from exc
        # Tabular evidence only: nested / semi-structured columns
        # (LIST, STRUCT, MAP, UNION, and the 2026 Parquet VARIANT type)
        # are a loud refusal naming the columns - never a silent
        # flatten. The engine analyzes tables, and says so.
        nested = [
            (name, dtype)
            for name, dtype in columns_of(con)
            if any(tok in dtype.upper()
                   for tok in ("STRUCT", "MAP", "UNION", "VARIANT"))
            or dtype.endswith("[]")
        ]
        if nested:
            named = ", ".join(f"{n} ({t})" for n, t in nested)
            raise AnalystKitError(
                f"Parquet file contains nested/semi-structured "
                f"column(s): {named}. This toolkit analyzes tabular "
                f"data; flatten or select scalar columns upstream and "
                f"re-export. (Nested and Variant types are a declared "
                f"refusal, not a silent flatten.)"
            )
        return con
    if suffix == ".xls":
        # DuckDB's excel extension documentation is explicit: .xlsx is
        # supported, .xls is not. A clean refusal with the remedy beats
        # a dependency-roulette attempt.
        raise AnalystKitError(
            f"Legacy .xls is not supported ({path.name}). Save the "
            f"workbook as .xlsx and retry (DuckDB excel extension "
            f"supports .xlsx only)."
        )
    if suffix == ".xlsx":
        # v2.1.0 — read via DuckDB's official excel extension instead of
        # pandas: ONE parser across profile, validation, and any engine
        # built on this loader (the single-reader principle; the
        # dual-parser divergence risk retires here). Documented
        # semantics honored as disclosed rules: the first sheet is the
        # default; numeric cells are inferred as DOUBLE.
        try:
            con.execute("INSTALL excel; LOAD excel")
        except Exception as exc:
            raise AnalystKitError(
                f"The DuckDB excel extension could not be loaded "
                f"(needed for .xlsx). Install it once with: INSTALL "
                f"excel; in DuckDB, or check network access to the "
                f"extension repository. Detail: {exc}"
            ) from exc
        try:
            con.execute(
                f"CREATE VIEW t AS SELECT * FROM read_xlsx("
                f"{_path_lit(path)})"
            )
        except Exception as exc:
            raise AnalystKitError(
                f"Could not open {path.name!r} as an .xlsx workbook. "
                f"Verify the file is valid. DuckDB detail: {exc}"
            ) from exc
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
        f"Unsupported source '{suffix}'. Use .csv, .parquet, .xlsx, .sqlite or .db."
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

