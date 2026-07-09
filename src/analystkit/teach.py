"""analystkit.teach — the built-in lessons behind `explain`."""
from __future__ import annotations

from typing import Final

LESSONS: Final[dict[str, str]] = {
    "completeness": (
        "COMPLETENESS asks: is anything missing?\n"
        "Measured as the share of non-null values per column.\n"
        "SQL pattern:  SELECT COUNT(*) - COUNT(col) AS nulls FROM t\n"
        "COUNT(col) skips nulls; COUNT(*) does not. The difference IS the gap.\n"
        "Why it is first: every other dimension is meaningless if the data\n"
        "is not all there. Profile before you analyse, always."
    ),
    "uniqueness": (
        "UNIQUENESS asks: is anything counted twice?\n"
        "SQL pattern:  SELECT key, COUNT(*) FROM t GROUP BY key HAVING COUNT(*) > 1\n"
        "HAVING filters groups (WHERE filters rows — interviewers love this).\n"
        "Duplicates inflate every downstream total. Find them before summing\n"
        "anything, and keep the evidence — deduplication without evidence is\n"
        "just deletion."
    ),
    "validity": (
        "VALIDITY asks: do values match their expected format?\n"
        "Emails that match an email pattern; dates that parse as dates.\n"
        "SQL pattern:  COUNT(TRY_CAST(col AS TIMESTAMP)) vs COUNT(col)\n"
        "TRY_CAST returns NULL instead of crashing on a bad value, so the\n"
        "ratio of successful casts is the validity score."
    ),
    "consistency": (
        "CONSISTENCY asks: does the same fact appear the same way everywhere?\n"
        "'Paid', 'paid ', and 'PAID' are one business value in three costumes.\n"
        "SQL pattern:  COUNT(DISTINCT col) - COUNT(DISTINCT lower(trim(col)))\n"
        "If those two counts differ, casing/whitespace variants exist, and\n"
        "every GROUP BY on that column is silently splitting one group into many."
    ),
    "timeliness": (
        "TIMELINESS asks: how fresh is this data?\n"
        "SQL pattern:  SELECT max(time_col) FROM t  — then compare to today.\n"
        "A perfect analysis of stale data is a perfectly wrong answer.\n"
        "Always report the data's own date range alongside any conclusion."
    ),
    "accuracy": (
        "ACCURACY asks: does the data match the real world?\n"
        "This is the one dimension NO tool can score from the dataset alone —\n"
        "you need an authoritative source to compare against. That is what\n"
        "`reconcile` does. Any tool that prints an 'accuracy score' without a\n"
        "reference source is making it up. AnalystKit says 'requires reconcile'\n"
        "instead, because honesty about limits is part of the standard."
    ),
    "reconcile": (
        "RECONCILIATION (the tie-out) asks: do two sources agree?\n"
        "Three checks, always in this order:\n"
        "  1. Row counts  — same population size?\n"
        "  2. Key match   — which records exist on only one side (orphans)?\n"
        "  3. Control total — does SUM(amount) tie between the sources?\n"
        "Orphans are findings, never garbage. A bank once missed 1.6 million\n"
        "transactions for four years because a feed silently dropped records\n"
        "nobody tied out. Reconcile BEFORE you report, every time."
    ),
    "workpaper": (
        "A WORKPAPER is analysis packaged as evidence.\n"
        "The standard: a reviewer must be able to RE-PERFORM your work from\n"
        "the document alone and get the same answer. That means it must state\n"
        "who ran it, when, on what source, with what assumptions, using what\n"
        "logic. If your output cannot be re-performed, it is an opinion, not\n"
        "evidence. AnalystKit's workpaper command builds this automatically."
    ),
}


def cmd_explain(topic: str) -> None:
    key = topic.lower().strip()
    if key not in LESSONS:
        print(f"No lesson for '{topic}'. Available: {', '.join(sorted(LESSONS))}")
        return
    print("=" * 62)
    print(LESSONS[key])
    print("=" * 62)

