"""analystkit.reconcile — the tie-out: rows, keys, control totals."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import duckdb

from analystkit.core import AnalystKitError, _ident, _path_lit, show_sql_hint


@dataclass(frozen=True, slots=True)
class ReconcileResult:
    """The three tie-outs every reviewer asks for."""

    left_rows: int
    right_rows: int
    matched_keys: int
    left_orphans: int
    right_orphans: int
    left_total: float | None
    matched_total: float | None


def reconcile_sources(
    left: Path, right: Path, key: str, total_col: str | None
) -> ReconcileResult:
    """Ties two sources together on a shared key.

    The Santander principle: a control can test perfectly on visible
    records and still fail completely if records never entered the
    system. Orphan keys are findings, never garbage.
    """
    con = duckdb.connect()
    for alias, path in (("l", left), ("r", right)):
        if not path.exists():
            raise AnalystKitError(f"Reconcile source not found: {path}")
        if path.suffix.lower() != ".csv":
            raise AnalystKitError("reconcile currently accepts CSV on both sides.")
        con.execute(
            f"CREATE VIEW {alias} AS SELECT * FROM read_csv_auto({_path_lit(path)})"
        )
    for alias, path in (("l", left), ("r", right)):
        cols = {str(row[0]) for row in
                con.execute(f"DESCRIBE {alias}").fetchall()}
        if key not in cols:
            raise AnalystKitError(
                f"Reconcile key '{key}' does not exist in {path.name}. "
                f"Available columns: {sorted(cols)}"
            )
        if alias == "l" and total_col and total_col not in cols:
            raise AnalystKitError(
                f"Control-total column '{total_col}' does not exist in "
                f"{path.name}. Available columns: {sorted(cols)}"
            )
    k = _ident(key)
    counts = con.execute(f"""
        SELECT
          (SELECT COUNT(*) FROM l),
          (SELECT COUNT(*) FROM r),
          (SELECT COUNT(*) FROM (SELECT DISTINCT l.{k} FROM l
             INNER JOIN r USING ({k}))),
          (SELECT COUNT(*) FROM l LEFT JOIN r USING ({k})
             WHERE r.{k} IS NULL),
          (SELECT COUNT(*) FROM r LEFT JOIN l USING ({k})
             WHERE l.{k} IS NULL)
    """).fetchone()
    if counts is None:
        raise AnalystKitError("Reconciliation query returned nothing.")

    left_total = matched_total = None
    if total_col:
        tc = _ident(total_col)
        totals = con.execute(f"""
            SELECT
              (SELECT SUM({tc}) FROM l),
              (SELECT SUM(l.{tc}) FROM l INNER JOIN r USING ({k}))
        """).fetchone()
        if totals:
            left_total = None if totals[0] is None else float(totals[0])
            matched_total = None if totals[1] is None else float(totals[1])

    return ReconcileResult(
        left_rows=int(counts[0]), right_rows=int(counts[1]),
        matched_keys=int(counts[2]), left_orphans=int(counts[3]),
        right_orphans=int(counts[4]),
        left_total=left_total, matched_total=matched_total,
    )


def cmd_reconcile(
    left: Path, right: Path, key: str, total_col: str | None, show_sql: bool
) -> None:
    show_sql_hint(f'LEFT/INNER JOIN USING ("{key}") + SUM("{total_col}") control totals'
          if total_col else f'LEFT/INNER JOIN USING ("{key}")', show_sql)
    r = reconcile_sources(left, right, key, total_col)
    print(f"TIE-OUT: {left.name}  ↔  {right.name}  on '{key}'")
    print("-" * 56)
    print(f"Left rows            : {r.left_rows:,}")
    print(f"Right rows           : {r.right_rows:,}")
    print(f"Matched keys         : {r.matched_keys:,}")
    print(f"Left orphans         : {r.left_orphans:,}  "
          f"(left rows whose key is absent on the right)")
    print(f"Right orphans        : {r.right_orphans:,}")
    if r.left_total is not None:
        print(f"Left control total   : {r.left_total:,.2f}")
        print(f"Matched control total: {r.matched_total or 0:,.2f}")
        gap = r.left_total - (r.matched_total or 0)
        print(f"Unreconciled amount  : {gap:,.2f}")
    if r.left_orphans or r.right_orphans:
        print("\nFINDING: orphan keys exist. These are records outside the "
              "reconciled population — they must be investigated and reported, "
              "never silently excluded (the completeness principle).")
    else:
        print("\nTied out clean: every key matches, nothing outside the population.")

