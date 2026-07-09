"""analystkit.summarize — grouped metrics with validated columns."""
from __future__ import annotations

from collections.abc import Callable

import duckdb

from analystkit.core import AnalystKitError, _ident, show_sql_hint
from analystkit.engine import _print_table, columns_of


def cmd_summarize(
    source: str, by: str, metric: str, top: int,
    table: str | None, show_sql: bool,
    opener: Callable[[str, str | None], duckdb.DuckDBPyConnection],
) -> None:
    if top < 1:
        raise AnalystKitError(f"--top must be at least 1 (got {top}).")
    con = opener(source, table)
    known = {name for name, _ in columns_of(con)}
    if by not in known:
        raise AnalystKitError(
            f"Group-by column '{by}' does not exist. Available: {sorted(known)}"
        )
    if metric == "count":
        metric_sql, mname = "COUNT(*)", "count"
    elif ":" in metric:
        fn, col = metric.split(":", 1)
        if fn not in ("avg", "sum", "median", "min", "max"):
            raise AnalystKitError(f"Unknown metric function '{fn}'.")
        if col not in known:
            raise AnalystKitError(
                f"Metric column '{col}' does not exist. Available: {sorted(known)}"
            )
        metric_sql, mname = f"ROUND({fn.upper()}({_ident(col)}), 2)", f"{fn}_{col}"
    else:
        raise AnalystKitError("Metric must be 'count' or fn:column.")
    sql = (f"SELECT {_ident(by)}, {metric_sql} AS {_ident(mname)} FROM t "
           f"GROUP BY 1 ORDER BY {_ident(mname)} DESC LIMIT {int(top)}")
    show_sql_hint(sql, show_sql)
    _print_table([by, mname], con.execute(sql).fetchall())

