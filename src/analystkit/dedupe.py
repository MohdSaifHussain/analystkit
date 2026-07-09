"""analystkit.dedupe — exact-row and key-based duplicate detection."""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import duckdb

from analystkit.core import AnalystKitError, _ident, _path_lit, show_sql_hint
from analystkit.engine import _print_table, columns_of


def find_duplicates(
    con: duckdb.DuckDBPyConnection, key: str | None
) -> tuple[int, list[tuple[Any, ...]]]:
    """Returns (duplicate_row_count, sample_groups). Full-row when key is None."""
    if key:
        known = {name for name, _ in columns_of(con)}
        if key not in known:
            raise AnalystKitError(
                f"Dedupe key '{key}' does not exist. Available: {sorted(known)}"
            )
        k = _ident(key)
        sql = (f"SELECT {k}, COUNT(*) AS copies FROM t "
               f"WHERE {k} IS NOT NULL "
               f"GROUP BY 1 HAVING COUNT(*) > 1 ORDER BY 2 DESC")
    else:
        cols = ", ".join(_ident(c) for c, _ in columns_of(con))
        sql = (f"SELECT {cols}, COUNT(*) AS copies FROM t "
               f"GROUP BY ALL HAVING COUNT(*) > 1 ORDER BY copies DESC")
    groups = con.execute(sql).fetchall()
    dup_rows = sum(int(g[-1]) - 1 for g in groups)
    return dup_rows, groups


def cmd_dedupe(
    source: str, key: str | None, out: Path | None,
    table: str | None, show_sql: bool,
    opener: Callable[[str, str | None], duckdb.DuckDBPyConnection],
) -> None:
    con = opener(source, table)
    show_sql_hint("GROUP BY " + (f'"{key}"' if key else "ALL") + " HAVING COUNT(*) > 1",
          show_sql)
    dup_rows, groups = find_duplicates(con, key)
    scope = f"key '{key}'" if key else "entire row"
    print(f"Duplicate check on: {scope}")
    print(f"Duplicate groups : {len(groups):,}")
    print(f"Excess rows      : {dup_rows:,} "
          f"(rows beyond the first copy in each group)\n")
    if groups:
        headers = ([key, "copies"] if key
                   else [c for c, _ in columns_of(con)] + ["copies"])
        _print_table(headers, groups, limit=10)
    if out:
        if key:
            con.execute(
                f"COPY (SELECT * FROM (SELECT *, ROW_NUMBER() OVER "
                f"(PARTITION BY {_ident(key)} ORDER BY 1) AS rn FROM t) "
                f"WHERE rn = 1) TO {_path_lit(out)} (HEADER, DELIMITER ',')"
            )
        else:
            con.execute(
                f"COPY (SELECT DISTINCT * FROM t) "
                f"TO {_path_lit(out)} (HEADER, DELIMITER ',')"
            )
        print(f"\nDeduplicated output → {out}  "
              f"(original left untouched — evidence is preserved)")

