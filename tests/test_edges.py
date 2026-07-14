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


class TestCsvRobustness:
    """Regression tests for the read_csv fix (loophole hunt v2.1).

    read_csv_auto used sample-based quoting detection which failed on
    large files where fields containing commas inside quotes appeared
    after the detection window. The planted answer: a 3-row CSV with
    one field that contains a comma inside double-quotes must load as
    3 rows with the field value intact, not crash or split the column.
    Official source: DuckDB CSV documentation, read_csv parameters.
    """

    def test_quoted_comma_field_loads_correctly(self, tmp_path: Path) -> None:
        """The exact failure mode from the 13M-row Kaggle transaction dataset:
        the errors column contained values like "Insufficient Balance,
        Technical Glitch" which read_csv_auto parsed as an extra column.
        Planted: exactly 3 rows, the multi-value field must survive intact."""
        import csv
        p = tmp_path / "messy_bank.csv"
        with p.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["txn_id", "amount", "errors"])
            w.writerow(["T001", "100.00", ""])
            w.writerow(["T002", "-50.00", "Insufficient Balance,Technical Glitch"])
            w.writerow(["T003", "200.00", ""])
        con = load_source(p)
        rows = con.execute("SELECT COUNT(*) FROM t").fetchone()[0]
        assert rows == 3                                       # planted: 3
        errors = con.execute(
            "SELECT errors FROM t WHERE txn_id = 'T002'"
        ).fetchone()[0]
        assert errors == "Insufficient Balance,Technical Glitch"  # intact

    def test_malformed_file_gives_clean_error(self, tmp_path: Path) -> None:
        """A genuinely corrupted file must raise AnalystKitError with a
        clear message — not a raw DuckDB traceback."""
        p = tmp_path / "corrupt.csv"
        p.write_bytes(b"\xff\xfe not utf-8 at all \x00\x00")
        with pytest.raises(AnalystKitError, match="valid CSV"):
            load_source(p)

    def test_quoted_comma_does_not_add_phantom_column(
        self, tmp_path: Path
    ) -> None:
        """Planted: a file with exactly 3 declared columns must profile
        as 3 columns, not 4 (the phantom column from misparse)."""
        import csv
        p = tmp_path / "three_cols.csv"
        with p.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["id", "value", "note"])
            w.writerow(["1", "100", "simple"])
            w.writerow(["2", "200", "has,comma,inside"])
            w.writerow(["3", "300", "normal"])
        con = load_source(p)
        col_count = len(con.execute("DESCRIBE t").fetchall())
        assert col_count == 3                                  # planted: 3
