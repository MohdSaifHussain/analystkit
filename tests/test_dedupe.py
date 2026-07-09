"""Ported from v1.1 — planted-answer principle: plant the issue, verify found."""
from pathlib import Path

from analystkit import (
    find_duplicates,
    load_source,
)


class TestDedupe:
    def test_full_row_duplicate_found(self, messy_csv: Path) -> None:
        con = load_source(messy_csv)
        dup_rows, groups = find_duplicates(con, key=None)
        assert dup_rows == 1          # the O-6 exact duplicate
        assert len(groups) == 1

    def test_key_duplicates_found(self, messy_csv: Path) -> None:
        con = load_source(messy_csv)
        dup_rows, groups = find_duplicates(con, key="order_id")
        assert len(groups) == 2       # O-1 and O-6 reused
        assert dup_rows == 2


# ── Reconcile ────────────────────────────────────────────────────────────────
