"""Ported from v1.1 — planted-answer principle: plant the issue, verify found."""
from pathlib import Path

from analystkit import (
    reconcile_sources,
)


class TestReconcile:
    def test_orphans_detected(self, messy_csv: Path, reference_csv: Path) -> None:
        r = reconcile_sources(messy_csv, reference_csv, "customer_id", "amount")
        assert r.left_orphans == 2    # two C-9 rows have no customer record
        assert r.right_orphans == 1   # C-4 has no orders

    def test_control_totals_computed(self, messy_csv: Path,
                                     reference_csv: Path) -> None:
        r = reconcile_sources(messy_csv, reference_csv, "customer_id", "amount")
        assert r.left_total is not None and r.matched_total is not None
        # unreconciled = the two C-9 orders: 600 + 600
        assert abs((r.left_total - r.matched_total) - 1200.0) < 0.01


# ── Edge cases (the loophole hunt) ───────────────────────────────────────────
