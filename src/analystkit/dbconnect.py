"""analystkit.dbconnect — PostgreSQL / MySQL sources, read-only by construction.

Every security decision here traces to DuckDB's official documentation:

1. READ_ONLY is hardcoded on every ATTACH and there is no flag to disable
   it. An analysis tool never needs write access; least privilege is
   enforced by construction, not by policy. (DuckDB docs: the ATTACH
   READ_ONLY option, PostgreSQL extension.)

2. Credentials come from environment variables ONLY (PGHOST, PGUSER,
   PGPASSWORD, PGDATABASE / MYSQL_* equivalents). The DuckDB docs describe
   environment-variable configuration as the production pattern where
   connection information is managed externally.

3. Credentials are NEVER accepted in the connection string or CLI
   arguments. The DuckDB docs warn explicitly: if a connection error
   occurs, the full connection string (including credentials) may be
   printed to terminal output. CLI arguments additionally leak into
   shell history and process listings.

4. Persistent secrets are NEVER used. The DuckDB docs warn that
   persistent secrets are stored in unencrypted binary format on disk.
   This module creates nothing persistent; the connection lives only
   in memory for the lifespan of the DuckDB instance.

5. Error messages are sanitized before re-raising: any value currently
   held in a credential environment variable is redacted from the
   message, so a failure can never echo a password.

Combined with core._ident (validated identifier quoting) and
rules.run_rules (parameter-bound values), a connected database sits
behind three independent defences: it cannot be written to, values
cannot become SQL, and names cannot become SQL.
"""
from __future__ import annotations

import os
from typing import Final

import duckdb

from analystkit.core import AnalystKitError, _ident

__all__ = ["DB_SCHEMES", "attach_database", "load_db_source"]

DB_SCHEMES: Final[dict[str, str]] = {
    "postgres": "postgres",
    "postgresql": "postgres",
    "mysql": "mysql",
}

_PG_ENV: Final[tuple[str, ...]] = ("PGHOST", "PGPORT", "PGUSER", "PGPASSWORD", "PGDATABASE")
_MYSQL_ENV: Final[tuple[str, ...]] = (
    "MYSQL_HOST", "MYSQL_TCP_PORT", "MYSQL_USER", "MYSQL_PWD", "MYSQL_DATABASE",
)
_SECRET_ENV: Final[tuple[str, ...]] = ("PGPASSWORD", "MYSQL_PWD")


def _redact(message: str) -> str:
    """Removes any credential env-var VALUE that leaked into an error string.

    DuckDB warns that connection errors may print the full connection
    string. We never build one with credentials, but defence in depth:
    no secret value present in the environment may appear in anything
    this module raises.
    """
    for var in _SECRET_ENV:
        value = os.environ.get(var)
        if value:
            message = message.replace(value, "[REDACTED]")
    return message


def _require_env(names: tuple[str, ...], engine: str) -> None:
    """Fails fast, listing missing variables by NAME only, never by value."""
    required = tuple(n for n in names if not n.endswith(("PORT", "TCP_PORT")))
    missing = [n for n in required if not os.environ.get(n)]
    if missing:
        raise AnalystKitError(
            f"{engine} connection needs environment variables: "
            f"{', '.join(missing)}. Credentials are read from the "
            f"environment only — never pass them on the command line "
            f"(shell history and process listings are readable)."
        )


def attach_database(uri: str) -> tuple[duckdb.DuckDBPyConnection, str]:
    """Attaches a database READ_ONLY and returns (connection, engine name).

    The uri selects the engine only — 'postgres://' or 'mysql://'.
    Anything after the scheme is deliberately ignored: connection
    details live in the environment, not in the argument.
    """
    scheme = uri.split("://", 1)[0].lower()
    engine = DB_SCHEMES.get(scheme)
    if engine is None:
        raise AnalystKitError(
            f"Unknown database scheme '{scheme}'. "
            f"Supported: {sorted(set(DB_SCHEMES))}"
        )

    con = duckdb.connect()
    try:
        if engine == "postgres":
            _require_env(_PG_ENV, "PostgreSQL")
            con.execute("ATTACH '' AS db (TYPE postgres, READ_ONLY)")
        else:
            _require_env(_MYSQL_ENV, "MySQL")
            con.execute("ATTACH '' AS db (TYPE mysql, READ_ONLY)")
    except AnalystKitError:
        raise
    except Exception as exc:
        raise AnalystKitError(
            f"Could not attach {engine} database: {_redact(str(exc))}"
        ) from None
    return con, engine


def load_db_source(uri: str, table: str) -> duckdb.DuckDBPyConnection:
    """Attaches READ_ONLY and exposes one table as view `t`.

    Same mental model as files: whatever the source, analysis code
    sees view `t`. The table name is validated against the attached
    schema before quoting — identifiers are never trusted raw.
    """
    if not table:
        raise AnalystKitError(
            "Database sources need --table (which table to analyse)."
        )
    con, engine = attach_database(uri)
    rows = con.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_catalog = 'db'"
    ).fetchall()
    known = {str(r[0]) for r in rows}
    if table not in known:
        raise AnalystKitError(
            f"Table '{table}' not found in the attached {engine} "
            f"database. Available: {sorted(known)}"
        )
    con.execute(f"CREATE VIEW t AS SELECT * FROM db.{_ident(table)}")
    return con
