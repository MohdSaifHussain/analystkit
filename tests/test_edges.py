"""Ported from v1.1 — planted-answer principle: plant the issue, verify found."""
from pathlib import Path

import pytest

from analystkit import (
    AnalystKitError,
    Dimension,
    dimension_scores,
    load_source,
    profile_columns,
    run_rules,
)


class TestEdges:
    def test_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(AnalystKitError, match="not found"):
            load_source(tmp_path / "ghost.csv")

    def test_single_column_no_time(self, tmp_path: Path) -> None:
        p = tmp_path / "one.csv"
        p.write_text("name\nalice\nbob\nalice\n", encoding="utf-8")
        con = load_source(p)
        scores = dimension_scores(con, profile_columns(con))
        assert scores[Dimension.TIMELINESS] is None   # honest: no time column
        uniq = scores[Dimension.UNIQUENESS]
        assert uniq is not None and uniq < 1.0        # 'alice' twice

    def test_all_null_column(self, tmp_path: Path) -> None:
        p = tmp_path / "nulls.csv"
        p.write_text("a,b\n1,\n2,\n3,\n", encoding="utf-8")
        con = load_source(p)
        b = next(pr for pr in profile_columns(con) if pr.name == "b")
        assert b.completeness == 0.0


class TestLoopholeFixes:
    def test_rule_on_missing_column_gives_clean_error(self, messy_csv: Path) -> None:
        con = load_source(messy_csv)
        with pytest.raises(AnalystKitError, match="does not exist"):
            run_rules(con, [{"column": "ghost", "rule": "not_null"}])

    def test_empty_dataset_profiles_without_crash(self, tmp_path: Path) -> None:
        p = tmp_path / "empty.csv"
        p.write_text("a,b\n", encoding="utf-8")
        con = load_source(p)
        profiles = profile_columns(con)
        assert profiles[0].total == 0
        scores = dimension_scores(con, profiles)
        assert scores[Dimension.COMPLETENESS] == 1.0  # scored, but cmd warns


# ── Hardening fixes (v1.1) — every fix has a planted-answer test ────────────
