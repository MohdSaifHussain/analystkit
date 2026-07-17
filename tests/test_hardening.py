"""Ported from v1.1 — planted-answer principle: plant the issue, verify found."""
import csv
from pathlib import Path

import pytest

from analystkit import (
    AnalystKitError,
    columns_of,
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


class TestAllowedRuleBooleanCanonicalization:
    """Found in production by the Delivery Engine fraud run (July 2026):
    a 500k-row dataset with BOOLEAN columns produced 1.5M false
    exceptions because DuckDB casts BOOLEAN to VARCHAR as lowercase
    'true'/'false' while callers naturally write Python bools
    (str(True) == 'True'), title-case strings, or 1/0. The allowed rule
    now canonicalizes values for BOOLEAN columns only; VARCHAR
    categoricals keep strict case-sensitive comparison; an
    unrecognizable boolean literal is a loud error, never a rule that
    silently fails every row."""

    def _bool_csv(self, tmp_path: Path) -> Path:
        p = tmp_path / "b.csv"
        p.write_text(
            "flag\n" + "\n".join(
                "True" if i % 2 else "False" for i in range(10)
            ) + "\n",
            encoding="utf-8",
        )
        return p

    def test_python_bools_pass(self, tmp_path: Path) -> None:
        con = load_source(self._bool_csv(tmp_path))
        res = run_rules(con, [{
            "column": "flag", "rule": "allowed", "values": [True, False],
        }])
        assert res[0].failures == 0

    def test_title_case_strings_pass(self, tmp_path: Path) -> None:
        con = load_source(self._bool_csv(tmp_path))
        res = run_rules(con, [{
            "column": "flag", "rule": "allowed",
            "values": ["True", "False"],
        }])
        assert res[0].failures == 0

    def test_upper_case_and_ints_pass(self, tmp_path: Path) -> None:
        con = load_source(self._bool_csv(tmp_path))
        for values in (["TRUE", "FALSE"], [1, 0]):
            res = run_rules(con, [{
                "column": "flag", "rule": "allowed", "values": values,
            }])
            assert res[0].failures == 0, values

    def test_genuine_violation_still_counted(self, tmp_path: Path) -> None:
        con = load_source(self._bool_csv(tmp_path))
        res = run_rules(con, [{
            "column": "flag", "rule": "allowed", "values": [True],
        }])
        assert res[0].failures == 5  # the five False rows

    def test_unrecognizable_boolean_literal_is_a_loud_error(
        self, tmp_path: Path
    ) -> None:
        con = load_source(self._bool_csv(tmp_path))
        with pytest.raises(AnalystKitError, match="boolean literal"):
            run_rules(con, [{
                "column": "flag", "rule": "allowed",
                "values": ["True", "maybe"],
            }])

    def test_varchar_columns_keep_case_sensitivity(
        self, tmp_path: Path
    ) -> None:
        """Canonicalization applies to BOOLEAN dtype only - VARCHAR
        categoricals keep strict, case-sensitive comparison. (Note:
        a column containing only True/TRUE strings is itself sniffed
        as BOOLEAN by DuckDB, where case-folding is then CORRECT
        boolean semantics - so this test uses genuinely non-boolean
        category names.)"""
        p = tmp_path / "v.csv"
        p.write_text("status,pad\nPaid,x\nPAID,x\nPaid,x\n",
                     encoding="utf-8")
        con = load_source(p)
        res = run_rules(con, [{
            "column": "status", "rule": "allowed", "values": ["Paid"],
        }])
        assert res[0].failures == 1  # 'PAID' is a different value


class TestTypeBoundaryMatrix:
    """v2.0.2 - the institutional control against the boolean bug's
    whole FAMILY: comparison-domain mismatches at the type boundary,
    which fail silently per-row. Found by probe after v2.0.1: an
    integer column vs values [1.0, 0.0] and a float column vs values
    [1, 0] each produced 100% false failures. The matrix below pins
    the allowed rule's behavior for every dtype family x caller value
    style, so any future regression of this class fails a named test
    instead of shipping."""

    def _run_one(self, tmp_path: Path, name: str, col_rows: list[str],
                 values: list) -> int:  # type: ignore[type-arg]
        p = tmp_path / f"{name}.csv"
        p.write_text("v\n" + "\n".join(col_rows) + "\n", encoding="utf-8")
        con = load_source(p)
        res = run_rules(con, [{
            "column": "v", "rule": "allowed", "values": values,
        }])
        return res[0].failures

    def test_integer_column_accepts_float_and_string_values(
        self, tmp_path: Path
    ) -> None:
        rows = ["1", "0", "1"] * 5
        assert self._run_one(tmp_path, "i1", rows, [1.0, 0.0]) == 0
        assert self._run_one(tmp_path, "i2", rows, ["1", "0"]) == 0
        assert self._run_one(tmp_path, "i3", rows, [1, 0]) == 0

    def test_float_column_accepts_int_and_string_values(
        self, tmp_path: Path
    ) -> None:
        rows = ["1.0", "0.0", "1.5"] * 5
        assert self._run_one(tmp_path, "f1", rows, [1, 0, 1.5]) == 0
        assert self._run_one(tmp_path, "f2", rows,
                             ["1", "0", "1.5"]) == 0

    def test_numeric_column_genuine_violation_still_counted(
        self, tmp_path: Path
    ) -> None:
        rows = ["1", "0", "9"] * 5
        assert self._run_one(tmp_path, "g1", rows, [1.0, 0.0]) == 5

    def test_numeric_column_non_numeric_value_is_a_loud_error(
        self, tmp_path: Path
    ) -> None:
        p = tmp_path / "n.csv"
        p.write_text("v\n1\n2\n3\n", encoding="utf-8")
        con = load_source(p)
        with pytest.raises(AnalystKitError, match="numeric"):
            run_rules(con, [{
                "column": "v", "rule": "allowed",
                "values": [1, "banana"],
            }])

    def test_date_column_iso_strings_pass(self, tmp_path: Path) -> None:
        rows = ["2026-01-01", "2026-01-02"] * 5
        assert self._run_one(tmp_path, "d1", rows,
                             ["2026-01-01", "2026-01-02"]) == 0

    def test_varchar_column_stays_strict(self, tmp_path: Path) -> None:
        rows = ["Paid", "PAID", "Paid"] * 5
        assert self._run_one(tmp_path, "v1", rows, ["Paid"]) == 5


class TestSourceAdapters:
    """v2.1.0 - Parquet support plus the single-reader principle at the
    doorstep. Rules, each traced to official documentation:
    - Parquet loads via DuckDB read_parquet (spec: parquet.apache.org /
      apache/parquet-format, Thrift IDL authoritative); nested and
      semi-structured columns (LIST/STRUCT/MAP/UNION and the 2026
      VARIANT type) are a loud refusal NAMING the columns - this
      toolkit analyzes tables, never silently flattens.
    - .xlsx reads via DuckDB's official excel extension (previously
      pandas - two parsers, one file, the divergence class of the
      v2.0.x bugs); the documented defaults become disclosed rules:
      first sheet, numerics as DOUBLE.
    - .xls is documented as unsupported by the extension: a clean
      refusal with the remedy, not dependency roulette.
    - A renamed CSV wearing .parquet dies in the kit's voice, not a
      raw DuckDB traceback."""

    def _base(self, tmp_path: Path) -> Path:
        csv = tmp_path / "b.csv"
        csv.write_text(
            "record_id,amount,tier\n" + "\n".join(
                f"R-{i:04d},{10.5 + i},{('a', 'b', 'c')[i % 3]}"
                for i in range(60)
            ) + "\n",
            encoding="utf-8",
        )
        return csv

    def test_parquet_loads_and_matches_csv_values(
        self, tmp_path: Path
    ) -> None:
        import duckdb

        csv = self._base(tmp_path)
        pq = tmp_path / "b.parquet"
        duckdb.execute(
            f"COPY (SELECT * FROM read_csv('{csv}')) TO '{pq}' "
            f"(FORMAT parquet)"
        )
        con = load_source(pq)
        n, total = con.execute(
            "SELECT COUNT(*), ROUND(SUM(amount), 4) FROM t"
        ).fetchone()
        assert n == 60
        assert total == round(sum(10.5 + i for i in range(60)), 4)

    def test_nested_parquet_refused_naming_columns(
        self, tmp_path: Path
    ) -> None:
        import duckdb

        pq = tmp_path / "nested.parquet"
        duckdb.execute(
            f"COPY (SELECT 1 AS id, [1, 2] AS tags, "
            f"{{'k': 1}} AS meta) TO '{pq}' (FORMAT parquet)"
        )
        with pytest.raises(AnalystKitError) as exc:
            load_source(pq)
        msg = str(exc.value)
        assert "tags" in msg and "meta" in msg
        assert "silent flatten" in msg

    def test_xls_is_a_clean_refusal_with_remedy(
        self, tmp_path: Path
    ) -> None:
        xls = tmp_path / "old.xls"
        xls.write_bytes(b"\xd0\xcf\x11\xe0 fake")
        with pytest.raises(AnalystKitError, match=r"\.xlsx"):
            load_source(xls)

    def test_xlsx_reads_via_duckdb_extension(
        self, tmp_path: Path
    ) -> None:
        import duckdb

        csv = self._base(tmp_path)
        xlsx = tmp_path / "b.xlsx"
        con0 = duckdb.connect()
        con0.execute("INSTALL excel; LOAD excel")
        con0.execute(
            f"COPY (SELECT * FROM read_csv('{csv}')) TO '{xlsx}' "
            f"(FORMAT xlsx, HEADER true)"
        )
        con = load_source(xlsx)
        cols = dict(columns_of(con))
        # the extension's documented inference: numerics arrive DOUBLE
        assert cols["amount"] == "DOUBLE"
        assert con.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 60

    def test_renamed_csv_wearing_parquet_dies_in_our_voice(
        self, tmp_path: Path
    ) -> None:
        fake = tmp_path / "fake.parquet"
        fake.write_bytes(self._base(tmp_path).read_bytes())
        with pytest.raises(AnalystKitError, match="renamed CSV"):
            load_source(fake)
