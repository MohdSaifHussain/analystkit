"""analystkit.profiling — DAMA six dimensions. Accuracy is never scored."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

import duckdb

from analystkit.core import (
    EMAIL_RE,
    TIME_HINTS,
    Dimension,
    _ident,
    show_sql_hint,
)
from analystkit.engine import _print_table, columns_of


@dataclass(frozen=True, slots=True)
class ColumnProfile:
    """Per-column quality facts, computed once and reused everywhere."""

    name: str
    dtype: str
    total: int
    nulls: int
    distinct: int
    case_variants: int      # values identical except case/whitespace
    valid_ratio: float      # share of non-null values passing the type/format check

    @property
    def completeness(self) -> float:
        return 1.0 if self.total == 0 else 1 - self.nulls / self.total


def profile_columns(con: duckdb.DuckDBPyConnection) -> list[ColumnProfile]:
    """Computes per-column facts: nulls, distincts, case variants, validity."""
    row = con.execute("SELECT COUNT(*) FROM t").fetchone()
    total = int(row[0]) if row else 0
    profiles: list[ColumnProfile] = []

    for name, dtype in columns_of(con):
        c = _ident(name)
        r = con.execute(
            f"SELECT COUNT(*) - COUNT({c}), COUNT(DISTINCT {c}) FROM t"
        ).fetchone()
        nulls = int(r[0]) if r else 0
        distinct = int(r[1]) if r else 0

        # Consistency: values that collide once trimmed and lowercased
        case_variants = 0
        if "VARCHAR" in dtype.upper() and total > 0:
            cv = con.execute(
                f"SELECT COUNT(DISTINCT {c}) - "
                f"COUNT(DISTINCT lower(trim({c}))) FROM t "
                f"WHERE {c} IS NOT NULL"
            ).fetchone()
            case_variants = int(cv[0]) if cv else 0

        # Validity: type/format conformance of non-null values
        valid_ratio = 1.0
        lowered = name.lower()
        if "VARCHAR" in dtype.upper() and total > 0:
            if "email" in lowered:
                vals = con.execute(
                    f"SELECT {c} FROM t WHERE {c} IS NOT NULL"
                ).fetchall()
                non_null = len(vals)
                if non_null:
                    ok = sum(1 for (v,) in vals if EMAIL_RE.match(str(v).strip()))
                    valid_ratio = ok / non_null
            elif any(h in lowered for h in TIME_HINTS):
                v = con.execute(
                    f"SELECT COUNT(*), COUNT(TRY_CAST({c} AS TIMESTAMP)) "
                    f"FROM t WHERE {c} IS NOT NULL"
                ).fetchone()
                if v and int(v[0]) > 0:
                    valid_ratio = int(v[1]) / int(v[0])

        profiles.append(ColumnProfile(
            name=name, dtype=dtype, total=total, nulls=nulls,
            distinct=distinct, case_variants=case_variants,
            valid_ratio=valid_ratio,
        ))
    return profiles


def _detect_time_column(con: duckdb.DuckDBPyConnection) -> str | None:
    for name, dtype in columns_of(con):
        if "TIMESTAMP" in dtype.upper() or "DATE" in dtype.upper():
            return name
        if any(h in name.lower() for h in TIME_HINTS):
            v = con.execute(
                f"SELECT COUNT(*), COUNT(TRY_CAST({_ident(name)} AS TIMESTAMP)) "
                f"FROM t WHERE {_ident(name)} IS NOT NULL"
            ).fetchone()
            if v and int(v[0]) > 0 and int(v[1]) / int(v[0]) >= 0.9:
                return name
    return None


def dimension_scores(
    con: duckdb.DuckDBPyConnection,
    profiles: list[ColumnProfile],
) -> dict[Dimension, float | None]:
    """Rolls per-column facts up into the DAMA six dimension scores (0-1).

    Accuracy returns None on purpose: accuracy means agreement with the
    real world, which no tool can verify from the dataset alone. It
    requires reconciliation against an authoritative source — that is
    what the `reconcile` command exists for. Faking a number here would
    be dishonest, so the scorecard says so instead.
    """
    if not profiles:
        return dict.fromkeys(Dimension)
    total = profiles[0].total

    completeness = sum(p.completeness for p in profiles) / len(profiles)

    all_cols = ", ".join(_ident(p.name) for p in profiles)
    dup = con.execute(
        "SELECT COUNT(*) FROM (SELECT COUNT(*) AS n FROM t "
        f"GROUP BY {all_cols} "
        "HAVING COUNT(*) > 1)"
    ).fetchone() if total else None
    dup_groups = int(dup[0]) if dup else 0
    dup_rows_r = con.execute(
        "SELECT COALESCE(SUM(n - 1), 0) FROM (SELECT COUNT(*) AS n FROM t "
        f"GROUP BY {all_cols} "
        "HAVING COUNT(*) > 1)"
    ).fetchone() if total else None
    dup_rows = int(dup_rows_r[0]) if dup_rows_r else 0
    uniqueness = 1.0 if total == 0 else 1 - dup_rows / total

    validity = sum(p.valid_ratio for p in profiles) / len(profiles)

    text_cols = [p for p in profiles if "VARCHAR" in p.dtype.upper()]
    if text_cols:
        consistency = 1 - sum(
            (p.case_variants / p.distinct if p.distinct else 0) for p in text_cols
        ) / len(text_cols)
    else:
        consistency = 1.0

    timeliness: float | None = None
    tcol = _detect_time_column(con)
    if tcol:
        newest = con.execute(
            f"SELECT max(TRY_CAST({_ident(tcol)} AS TIMESTAMP)) FROM t"
        ).fetchone()
        if newest and newest[0] is not None:
            age_days = (datetime.now() - newest[0]).days
            timeliness = max(0.0, 1 - max(age_days, 0) / 90)  # linear decay, 90d floor

    _ = dup_groups  # groups reported by dedupe; rows drive the score
    return {
        Dimension.COMPLETENESS: completeness,
        Dimension.UNIQUENESS: uniqueness,
        Dimension.VALIDITY: validity,
        Dimension.CONSISTENCY: consistency,
        Dimension.TIMELINESS: timeliness,
        Dimension.ACCURACY: None,
    }


def cmd_profile(source: str, table: str | None, show_sql: bool,
                opener: Callable[[str, str | None], duckdb.DuckDBPyConnection]) -> None:
    con = opener(source, table)
    profiles = profile_columns(con)
    scores = dimension_scores(con, profiles)
    show_sql_hint("Per-column: COUNT(*), COUNT(col), COUNT(DISTINCT col), "
          "lower(trim(col)) collision check, TRY_CAST validity check", show_sql)

    total_rows = profiles[0].total if profiles else 0
    print(f"Source : {source}")
    print(f"Rows   : {total_rows:,}\n")
    if total_rows == 0:
        print("WARNING: dataset contains ZERO rows. Perfect scores on an "
              "empty dataset are meaningless — verify the extract before "
              "trusting anything below.\n")
    _print_table(
        ["column", "type", "nulls", "null %", "distinct", "case variants", "valid %"],
        [(p.name, p.dtype, p.nulls,
          f"{(p.nulls / p.total * 100 if p.total else 0):.1f}%",
          p.distinct, p.case_variants, f"{p.valid_ratio * 100:.1f}%")
         for p in profiles],
    )
    print("\nDAMA DATA QUALITY SCORECARD")
    print("-" * 46)
    for dim, score in scores.items():
        if score is None:
            note = ("requires reconcile vs authoritative source"
                    if dim is Dimension.ACCURACY else "no time column detected")
            print(f"{dim:<14} —      ({note})")
        else:
            bar = "█" * int(score * 20)
            print(f"{dim:<14} {score * 100:5.1f}%  {bar}")
    tcol = _detect_time_column(con)
    if tcol:
        newest_row = con.execute(
            f"SELECT max(TRY_CAST({_ident(tcol)} AS TIMESTAMP)) FROM t"
        ).fetchone()
        if newest_row and newest_row[0] is not None \
                and newest_row[0] > datetime.now():
            print(f"\nWARNING: newest '{tcol}' value ({newest_row[0]}) is in "
                  "the FUTURE. Timeliness scores 100% but future-dated records "
                  "are themselves a validity finding — run the not_future rule.")
    measurable = [s for s in scores.values() if s is not None]
    if measurable:
        print("-" * 46)
        print(f"{'OVERALL':<14} {sum(measurable) / len(measurable) * 100:5.1f}%  "
              f"(mean of measurable dimensions)")

