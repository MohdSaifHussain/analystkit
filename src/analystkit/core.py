"""analystkit.core — shared constants, identifier safety, errors.

Security foundations (each traced to an official source):
- _ident():  SQL-standard identifier quoting, internal double-quotes doubled.
             Source: DuckDB docs, "Keywords and Identifiers".
- _path_lit: single-quotes doubled in path string literals.
- Values are NEVER interpolated into SQL anywhere in this package —
  they are bound as prepared-statement parameters (?).
             Source: DuckDB docs, "Prepared Statements" (the documented
             defence against SQL injection).
"""
from __future__ import annotations

import re
import sys
from enum import StrEnum
from pathlib import Path
from typing import Final
from zoneinfo import ZoneInfo

IST: Final[ZoneInfo] = ZoneInfo("Asia/Kolkata")

PAL: Final[dict[str, str]] = {
    "navy": "1B3A6B", "red": "C00000", "amber": "F4B942",
    "green": "70AD47", "grey": "9AA3AF", "alt": "EEF2F7",
    "white": "FFFFFF", "ink": "1A1A2E", "muted": "666666",
}

TIME_HINTS: Final[tuple[str, ...]] = (
    "_at", "date", "time", "created", "updated", "opened", "closed", "timestamp",
)

EMAIL_RE: Final[re.Pattern[str]] = re.compile(r"^[\w.+-]+@[\w-]+\.[\w.]+$")

NUMERIC_TYPE_HINTS: Final[tuple[str, ...]] = (
    "INT", "DECIMAL", "FLOAT", "DOUBLE", "HUGEINT", "NUMERIC", "REAL",
)


def _ident(name: str) -> str:
    """Quote a SQL identifier, doubling internal double-quotes.

    SQL-standard escaping per the DuckDB documentation (Keywords and
    Identifiers): to reference a column literally named col"bad, the SQL
    must read "col""bad". Without this, any identifier containing a
    double-quote breaks out of its quoting and produces a raw parser
    error — the identifier-injection loophole.
    """
    return '"' + name.replace('"', '""') + '"'


def _path_lit(path: Path) -> str:
    """A path as a SQL string literal, single-quotes doubled."""
    return "'" + path.as_posix().replace("'", "''") + "'"


class Dimension(StrEnum):
    """The DAMA-DMBOK six data quality dimensions."""

    COMPLETENESS = "Completeness"
    UNIQUENESS = "Uniqueness"
    VALIDITY = "Validity"
    CONSISTENCY = "Consistency"
    TIMELINESS = "Timeliness"
    ACCURACY = "Accuracy"


class AnalystKitError(ValueError):
    """User-facing error with a readable message, never a raw traceback."""


def show_sql_hint(sql: str, show_sql: bool) -> None:
    """Prints the SQL being run when --show-sql is on (the teaching hook)."""
    if show_sql:
        print(f"  [SQL] {sql}", file=sys.stderr)
