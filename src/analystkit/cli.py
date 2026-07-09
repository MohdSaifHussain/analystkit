"""analystkit.cli — argument parsing and dispatch ONLY. No logic lives here.

Every command's logic is an importable, testable function in its own
module. This file maps arguments to those functions and handles the two
process-level concerns: clean error exit and SIGPIPE.

Database sources: a source argument beginning with postgres:// or
mysql:// routes through analystkit.dbconnect (read-only by construction,
credentials from environment variables only). Everything else is a file
path handled by analystkit.engine. Either way, analysis code sees view `t`.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

from analystkit.core import AnalystKitError
from analystkit.dbconnect import DB_SCHEMES, load_db_source
from analystkit.dedupe import cmd_dedupe
from analystkit.demo import cmd_demo
from analystkit.engine import load_source
from analystkit.profiling import cmd_profile
from analystkit.reconcile import cmd_reconcile
from analystkit.rules import cmd_validate
from analystkit.summarize import cmd_summarize
from analystkit.teach import cmd_explain
from analystkit.workpaper import cmd_workpaper

__all__ = ["main", "open_source"]


def is_db_uri(source: str) -> bool:
    """True when the source names a database engine, not a file."""
    scheme = source.split("://", 1)[0].lower() if "://" in source else ""
    return scheme in DB_SCHEMES


def open_source(source: str, table: str | None) -> duckdb.DuckDBPyConnection:
    """One entry point, one mental model: file or database, you get view `t`."""
    if is_db_uri(source):
        return load_db_source(source, table or "")
    return load_source(Path(source), table)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="analystkit",
        description="Data quality & analysis toolkit — DAMA six dimensions, "
                    "workpaper discipline, self-teaching. Sources: CSV, "
                    "Excel, SQLite files, or postgres:// / mysql:// "
                    "(read-only, credentials via environment variables).",
    )
    sub = p.add_subparsers(dest="command", required=True)

    d = sub.add_parser("demo", help="Create messy practice data with a printed answer key")
    d.add_argument("--out", type=Path, default=Path("demo_data"))

    e = sub.add_parser("explain", help="Built-in lesson on any concept")
    e.add_argument("topic")

    pr = sub.add_parser("profile", help="DAMA six-dimension quality scorecard")
    pr.add_argument("source")
    pr.add_argument("--table", default=None)
    pr.add_argument("--show-sql", action="store_true")

    v = sub.add_parser("validate", help="Rule-based checks from a JSON rules file")
    v.add_argument("source")
    v.add_argument("--rules", type=Path, required=True)
    v.add_argument("--table", default=None)
    v.add_argument("--show-sql", action="store_true")
    v.add_argument("--ai", action="store_true",
                   help="Add an AI-written narrative of the findings "
                        "(needs ANTHROPIC_API_KEY; the AI sees only the "
                        "computed findings JSON, never the data)")

    dd = sub.add_parser("dedupe", help="Duplicate detection with evidence")
    dd.add_argument("source")
    dd.add_argument("--key", default=None)
    dd.add_argument("--out", type=Path, default=None)
    dd.add_argument("--table", default=None)
    dd.add_argument("--show-sql", action="store_true")

    rc = sub.add_parser("reconcile", help="Tie-out two sources on a key")
    rc.add_argument("left", type=Path)
    rc.add_argument("right", type=Path)
    rc.add_argument("--key", required=True)
    rc.add_argument("--total", dest="total_col", default=None)
    rc.add_argument("--show-sql", action="store_true")

    s = sub.add_parser("summarize", help="Group and aggregate")
    s.add_argument("source")
    s.add_argument("--by", required=True)
    s.add_argument("--metric", default="count")
    s.add_argument("--top", type=int, default=20)
    s.add_argument("--table", default=None)
    s.add_argument("--show-sql", action="store_true")

    w = sub.add_parser("workpaper", help="Full DQ workpaper: Excel deliverable")
    w.add_argument("source")
    w.add_argument("--rules", type=Path, default=None)
    w.add_argument("--key", default=None)
    w.add_argument("--out", type=Path, default=None)
    w.add_argument("--table", default=None)

    return p


def main() -> None:
    args = _build_parser().parse_args()
    try:
        if args.command == "demo":
            cmd_demo(args.out)
        elif args.command == "explain":
            cmd_explain(args.topic)
        elif args.command == "profile":
            cmd_profile(args.source, args.table, args.show_sql, open_source)
        elif args.command == "validate":
            cmd_validate(args.source, args.rules, args.table, args.show_sql,
                         open_source, ai=getattr(args, "ai", False))
        elif args.command == "dedupe":
            cmd_dedupe(args.source, args.key, args.out, args.table,
                       args.show_sql, open_source)
        elif args.command == "reconcile":
            cmd_reconcile(args.left, args.right, args.key, args.total_col,
                          args.show_sql)
        elif args.command == "summarize":
            cmd_summarize(args.source, args.by, args.metric, args.top,
                          args.table, args.show_sql, open_source)
        elif args.command == "workpaper":
            cmd_workpaper(args.source, args.rules, args.key, args.out,
                          args.table, open_source)
    except AnalystKitError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
    except BrokenPipeError:
        # Output piped to a closed reader (e.g. `| head`) — exit quietly.
        sys.stderr.close()
        sys.exit(0)
