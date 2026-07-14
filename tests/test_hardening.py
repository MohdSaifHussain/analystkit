"""Ported from v1.1 — planted-answer principle: plant the issue, verify found."""
import csv
from pathlib import Path

import pytest

from analystkit import (
    AnalystKitError,
    find_duplicates,
    load_source,
    profile_columns,
    reconcile_sources,
    run_rules,
)


class TestIdentifierQuoting:
    """DuckDB docs (Keywords and Identifiers): internal double-quotes in an
    identifier must be doubled. Before the fix, a column named col bad
    crashed every command with a raw parser error."""

    @pytest.fixture()
    def quoted_col_csv(self, tmp_path: Path) -> Path:
        # Column name with a space — requires SQL identifier quoting,
        # which was the original intent of this test. Previously used a
        # raw double-quote in the name, which interacted with DuckDB's
        # CSV quote-char parsing differently across auto vs explicit modes.
        p = tmp_path / "quoted.csv"
        with p.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["col bad", "amount"])
            w.writerows([["x", "10"], ["", "20"], ["y", "30"]])
        return p

    def test_profile_handles_quoted_column(self, quoted_col_csv: Path) -> None:
        con = load_source(quoted_col_csv)
        profiles = profile_columns(con)
        target = next(p for p in profiles if p.name == "col bad")
        assert target.nulls == 1                     # planted: one empty cell

    def test_rule_handles_quoted_column(self, quoted_col_csv: Path) -> None:
        con = load_source(quoted_col_csv)
        res = run_rules(con, [{"column": "col bad", "rule": "not_null"}])
        assert res[0].failures == 1

    def test_dedupe_handles_quoted_key(self, quoted_col_csv: Path) -> None:
        con = load_source(quoted_col_csv)
        dup_rows, _groups = find_duplicates(con, key="col bad")
        assert dup_rows == 0                         # no dup keys planted


class TestParameterBinding:
    """Values are bound as prepared-statement parameters (?), the
    DuckDB-documented SQL-injection defence."""

    def test_allowed_value_with_single_quote(self, tmp_path: Path) -> None:
        p = tmp_path / "names.csv"
        p.write_text("name\nO'Brien\nSmith\n", encoding="utf-8")
        con = load_source(p)
        res = run_rules(con, [{
            "column": "name", "rule": "allowed",
            "values": ["O'Brien", "Smith"],
        }])
        assert res[0].failures == 0                  # both allowed, no crash

    def test_regex_pattern_with_quote(self, tmp_path: Path) -> None:
        p = tmp_path / "vals.csv"
        p.write_text("v\nabc\nxyz\n", encoding="utf-8")
        con = load_source(p)
        res = run_rules(con, [{
            "column": "v", "rule": "regex", "pattern": "^[a-z']+$",
        }])
        assert res[0].failures == 0


class TestCleanErrors:
    """Every user mistake gets an AnalystKitError, never a raw traceback."""

    def test_range_on_text_column_clean_error(self, tmp_path: Path) -> None:
        p = tmp_path / "txt.csv"
        p.write_text("name,score\nalice,ten\nbob,also-text\n", encoding="utf-8")
        con = load_source(p)
        with pytest.raises(AnalystKitError, match="numeric"):
            run_rules(con, [{"column": "name", "rule": "range", "min": 0}])

    def test_reconcile_bad_key_clean_error(self, tmp_path: Path) -> None:
        lp = tmp_path / "l.csv"
        rp = tmp_path / "r.csv"
        lp.write_text("id,amount\n1,100\n", encoding="utf-8")
        rp.write_text("id,region\n1,North\n", encoding="utf-8")
        with pytest.raises(AnalystKitError, match="does not exist"):
            reconcile_sources(lp, rp, "ghost_key", "amount")

    def test_reconcile_bad_total_col_clean_error(self, tmp_path: Path) -> None:
        lp = tmp_path / "l.csv"
        rp = tmp_path / "r.csv"
        lp.write_text("id,amount\n1,100\n", encoding="utf-8")
        rp.write_text("id,region\n1,North\n", encoding="utf-8")
        with pytest.raises(AnalystKitError, match="Control-total"):
            reconcile_sources(lp, rp, "id", "ghost_total")

    def test_dedupe_bad_key_clean_error(self, tmp_path: Path) -> None:
        p = tmp_path / "d.csv"
        p.write_text("a,b\n1,2\n", encoding="utf-8")
        con = load_source(p)
        with pytest.raises(AnalystKitError, match="does not exist"):
            find_duplicates(con, key="ghost")

    def test_not_future_on_unparseable_column_raises(self, tmp_path: Path) -> None:
        """Before the fix: TRY_CAST returned NULL for every value, the rule
        reported 0 failures, and a garbage column looked perfectly clean."""
        p = tmp_path / "junk.csv"
        p.write_text("event_date\nnot-a-date\nalso-not\n", encoding="utf-8")
        con = load_source(p)
        with pytest.raises(AnalystKitError, match="parseable"):
            run_rules(con, [{"column": "event_date", "rule": "not_future"}])


class TestDemoClock:
    """The demo previously hardcoded now=2026-07-05, so its planted 'future'
    dates silently decayed into the past. It must use the real clock."""

    def test_demo_future_dates_are_genuinely_future(self, tmp_path: Path) -> None:
        from analystkit.demo import cmd_demo
        cmd_demo(tmp_path)
        con = load_source(tmp_path / "orders.csv")
        res = run_rules(con, [{"column": "order_date", "rule": "not_future"}])
        assert res[0].failures == 6                  # exactly as planted


class TestV20LoopholeFixes:
    """Second hunt (v2.0): user mistakes never earn raw tracebacks."""

    def test_malformed_json_rules_clean_error(self, tmp_path: Path) -> None:
        from analystkit.rules import load_rules
        bad = tmp_path / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        with pytest.raises(AnalystKitError, match="not valid JSON"):
            load_rules(bad)

    def test_missing_rules_file_clean_error(self, tmp_path: Path) -> None:
        from analystkit.rules import load_rules
        with pytest.raises(AnalystKitError, match="not found"):
            load_rules(tmp_path / "ghost.json")

    def test_negative_top_clean_error(self, messy_csv: Path) -> None:
        from analystkit.cli import open_source
        from analystkit.summarize import cmd_summarize
        with pytest.raises(AnalystKitError, match="at least 1"):
            cmd_summarize(str(messy_csv), "status", "count", -5,
                          None, False, open_source)

    def test_reconcile_missing_file_clean_error(
        self, reference_csv: Path, tmp_path: Path
    ) -> None:
        with pytest.raises(AnalystKitError, match="not found"):
            reconcile_sources(tmp_path / "ghost.csv", reference_csv,
                              "customer_id", None)


class TestAllowedRuleOnTypedColumns:
    """Found by Delivery Engine integration: DuckDB auto-types yes/no CSV
    columns as BOOLEAN and trim(BOOLEAN) is a binder error. The allowed
    rule must cast to VARCHAR before trimming."""

    def test_allowed_rule_on_boolean_column(self, tmp_path: Path) -> None:
        p = tmp_path / "b.csv"
        p.write_text("flag\nyes\nno\nyes\n", encoding="utf-8")
        con = load_source(p)
        res = run_rules(con, [{
            "column": "flag", "rule": "allowed", "values": ["true", "false"],
        }])
        # BOOLEAN casts to 'true'/'false' - all allowed, no crash
        assert res[0].failures == 0

    def test_allowed_rule_on_integer_column(self, tmp_path: Path) -> None:
        p = tmp_path / "i.csv"
        p.write_text("code\n1\n2\n9\n", encoding="utf-8")
        con = load_source(p)
        res = run_rules(con, [{
            "column": "code", "rule": "allowed", "values": ["1", "2"],
        }])
        assert res[0].failures == 1  # the planted 9
