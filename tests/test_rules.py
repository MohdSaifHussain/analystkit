"""Ported from v1.1 — planted-answer principle: plant the issue, verify found."""
from pathlib import Path

import pytest

from analystkit import (
    AnalystKitError,
    load_source,
    run_rules,
)


class TestRules:
    def _run(self, con, rules):  # type: ignore[no-untyped-def]
        return {r.rule_id: r for r in run_rules(con, rules)}

    def test_unique_rule_finds_reused_ids(self, messy_csv: Path) -> None:
        con = load_source(messy_csv)
        res = self._run(con, [{"column": "order_id", "rule": "unique"}])
        # O-1 twice and O-6 twice → 2 excess rows
        assert res["R01"].failures == 2

    def test_range_rule_finds_negative_amount(self, messy_csv: Path) -> None:
        con = load_source(messy_csv)
        res = self._run(con, [{"column": "amount", "rule": "range", "min": 0}])
        assert res["R01"].failures == 1

    def test_not_future_finds_planted_date(self, messy_csv: Path) -> None:
        con = load_source(messy_csv)
        res = self._run(con, [{"column": "order_date", "rule": "not_future"}])
        assert res["R01"].failures == 1

    def test_allowed_rule_catches_case_variants(self, messy_csv: Path) -> None:
        con = load_source(messy_csv)
        res = self._run(con, [{
            "column": "status", "rule": "allowed",
            "values": ["paid", "shipped", "delivered", "refunded"],
        }])
        # 'PAID' and 'PAID'→ actually: 'PAID', ' paid' trims to 'paid' (allowed)
        # trim(' paid') = 'paid' passes; 'PAID' fails → 1 failure
        assert res["R01"].failures == 1

    def test_unknown_rule_raises(self, messy_csv: Path) -> None:
        con = load_source(messy_csv)
        with pytest.raises(AnalystKitError, match="unknown rule"):
            run_rules(con, [{"column": "amount", "rule": "sparkle"}])

    def test_rule_missing_keys_raises(self, messy_csv: Path) -> None:
        con = load_source(messy_csv)
        with pytest.raises(AnalystKitError, match="needs"):
            run_rules(con, [{"rule": "not_null"}])


# ── Dedupe ───────────────────────────────────────────────────────────────────
