"""analystkit.rules — declarative validation with parameter-bound values."""
from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb

from analystkit.core import NUMERIC_TYPE_HINTS, AnalystKitError, _ident, show_sql_hint
from analystkit.engine import _print_table, columns_of


@dataclass(frozen=True, slots=True)
class RuleResult:
    """Outcome of one validation rule."""

    rule_id: str
    column: str
    rule: str
    detail: str
    failures: int
    sample: list[str]


def run_rules(
    con: duckdb.DuckDBPyConnection, rules: list[dict[str, Any]], show_sql: bool = False
) -> list[RuleResult]:
    """Evaluates each rule and returns failure counts with sample evidence.

    Supported rules: not_null, unique, range (min/max), allowed (values),
    regex (pattern), not_future (timestamps).

    Engineering note: user-supplied VALUES (range bounds, allowed sets,
    regex patterns) are bound as prepared-statement parameters (?), the
    DuckDB-documented defence against SQL injection. Identifiers cannot
    be parameters in SQL, so column names are validated against the
    schema first and then standard-quoted via _ident().
    """
    results: list[RuleResult] = []
    schema = dict(columns_of(con))
    for i, r in enumerate(rules, 1):
        col = str(r.get("column", ""))
        kind = str(r.get("rule", ""))
        rid = f"R{i:02d}"
        if not col or not kind:
            raise AnalystKitError(f"Rule {i} needs 'column' and 'rule' keys: {r}")
        if col not in schema:
            raise AnalystKitError(
                f"Rule {rid}: column '{col}' does not exist in the source. "
                f"Available columns: {sorted(schema)}"
            )
        c = _ident(col)
        dtype = schema[col].upper()
        params: list[Any] = []

        if kind == "not_null":
            cond, detail = f"{c} IS NULL", "value must not be null"
        elif kind == "unique":
            dup = con.execute(
                f"SELECT {c}, COUNT(*) FROM t WHERE {c} IS NOT NULL "
                f"GROUP BY 1 HAVING COUNT(*) > 1 ORDER BY 2 DESC"
            ).fetchall()
            failures = sum(int(n) - 1 for _, n in dup)
            results.append(RuleResult(
                rid, col, kind, "value must be unique", failures,
                [f"{v} (x{n})" for v, n in dup[:3]],
            ))
            continue
        elif kind == "range":
            if not any(h in dtype for h in NUMERIC_TYPE_HINTS):
                raise AnalystKitError(
                    f"Rule {rid}: range requires a numeric column; "
                    f"'{col}' is {schema[col]}. Cast or clean the column first."
                )
            parts: list[str] = []
            if "min" in r:
                parts.append(f"{c} < ?")
                params.append(float(r["min"]))
            if "max" in r:
                parts.append(f"{c} > ?")
                params.append(float(r["max"]))
            if not parts:
                raise AnalystKitError(f"Rule {rid}: range needs 'min' and/or 'max'.")
            cond = f"{c} IS NOT NULL AND ({' OR '.join(parts)})"
            detail = f"value outside [{r.get('min', '-inf')}, {r.get('max', 'inf')}]"
        elif kind == "allowed":
            vals = r.get("values")
            if not isinstance(vals, list) or not vals:
                raise AnalystKitError(f"Rule {rid}: allowed needs a 'values' list.")
            placeholders = ", ".join("?" for _ in vals)
            params.extend(str(v) for v in vals)
            cond = f"{c} IS NOT NULL AND trim({c}) NOT IN ({placeholders})"
            detail = f"value not in the allowed set ({len(vals)} values)"
        elif kind == "regex":
            pattern = str(r.get("pattern", ""))
            if not pattern:
                raise AnalystKitError(f"Rule {rid}: regex needs a 'pattern'.")
            cond = f"{c} IS NOT NULL AND NOT regexp_matches(trim({c}), ?)"
            params.append(pattern)
            detail = "value does not match the required pattern"
        elif kind == "not_future":
            parse = con.execute(
                f"SELECT COUNT(*), COUNT(TRY_CAST({c} AS TIMESTAMP)) "
                f"FROM t WHERE {c} IS NOT NULL"
            ).fetchone()
            non_null = int(parse[0]) if parse else 0
            parsed = int(parse[1]) if parse else 0
            if non_null > 0 and parsed == 0:
                raise AnalystKitError(
                    f"Rule {rid}: not_future found NO parseable timestamps in "
                    f"'{col}' — the rule would silently measure nothing. "
                    f"Verify the column really holds dates/timestamps."
                )
            cond = f"TRY_CAST({c} AS TIMESTAMP) > now()"
            detail = "timestamp is in the future"
        else:
            raise AnalystKitError(f"Rule {rid}: unknown rule kind '{kind}'.")

        sql = f"SELECT COUNT(*) FROM t WHERE {cond}"
        show_sql_hint(sql, show_sql)
        row = con.execute(sql, params or None).fetchone()
        failures = int(row[0]) if row else 0
        sample_rows = con.execute(
            f"SELECT {c} FROM t WHERE {cond} LIMIT 3", params or None
        ).fetchall()
        results.append(RuleResult(
            rid, col, kind, detail, failures,
            [str(s[0]) for s in sample_rows],
        ))
    return results


def load_rules(rules_path: Path) -> list[dict[str, Any]]:
    """Loads and shape-checks a JSON rules file. Every failure mode is a
    clean AnalystKitError — a user mistake never earns a raw traceback."""
    if not rules_path.exists():
        raise AnalystKitError(f"Rules file not found: {rules_path}")
    try:
        with rules_path.open(encoding="utf-8") as fh:
            raw: Any = json.load(fh)
    except json.JSONDecodeError as exc:
        raise AnalystKitError(
            f"Rules file is not valid JSON ({rules_path.name}, "
            f"line {exc.lineno}): {exc.msg}"
        ) from None
    if not isinstance(raw, list):
        raise AnalystKitError("Rules file must be a JSON list of rule objects.")
    return [dict(item) for item in raw]


def cmd_validate(
    source: str, rules_path: Path, table: str | None, show_sql: bool,
    opener: Callable[[str, str | None], duckdb.DuckDBPyConnection],
    ai: bool = False,
) -> None:
    con = opener(source, table)
    results = run_rules(con, load_rules(rules_path), show_sql)

    total_fail = sum(r.failures for r in results)
    _print_table(
        ["rule", "column", "check", "failures", "sample evidence"],
        [(r.rule_id, r.column, r.detail, r.failures,
          "; ".join(r.sample) if r.failures else "")
         for r in results],
    )
    print(f"\n{len(results)} rules evaluated | {total_fail:,} total exceptions")
    print("Exceptions are REPORTED, never dropped — every failure above is "
          "evidence, not garbage.")

    if ai:
        from analystkit.ai import narrate_findings, print_narrative
        findings = {
            "command": "validate",
            "rules_evaluated": len(results),
            "total_exceptions": total_fail,
            "results": [
                {"rule_id": r.rule_id, "column": r.column, "rule": r.rule,
                 "detail": r.detail, "failures": r.failures,
                 "sample": list(r.sample)}
                for r in results
            ],
        }
        narrative, digest = narrate_findings(findings)
        print_narrative(narrative, digest)

