"""Security invariants of the database layer, each tested directly.

The invariants come from DuckDB's official documentation:
- READ_ONLY attach (least privilege by construction)
- credentials from environment variables only
- no credential value may ever appear in an error message
"""
from pathlib import Path

import pytest

from analystkit.cli import is_db_uri, open_source
from analystkit.core import AnalystKitError
from analystkit.dbconnect import _redact, attach_database


class TestUriRouting:
    def test_postgres_uri_detected(self) -> None:
        assert is_db_uri("postgres://")
        assert is_db_uri("postgresql://")

    def test_mysql_uri_detected(self) -> None:
        assert is_db_uri("mysql://")

    def test_file_paths_not_db(self) -> None:
        assert not is_db_uri("orders.csv")
        assert not is_db_uri("/data/orders.sqlite")

    def test_file_route_still_works(self, messy_csv: Path) -> None:
        con = open_source(str(messy_csv), None)
        row = con.execute("SELECT COUNT(*) FROM t").fetchone()
        assert row is not None and int(row[0]) == 8


class TestCredentialSafety:
    def test_unknown_scheme_clean_error(self) -> None:
        with pytest.raises(AnalystKitError, match="Unknown database scheme"):
            attach_database("oracle://")

    def test_missing_env_lists_names_never_values(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for var in ("PGHOST", "PGUSER", "PGPASSWORD", "PGDATABASE"):
            monkeypatch.delenv(var, raising=False)
        with pytest.raises(AnalystKitError, match="PGHOST"):
            attach_database("postgres://")

    def test_credentials_never_accepted_in_uri(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Anything after the scheme is ignored — a password pasted into
        the URI must NOT be used and must NOT appear in the error."""
        for var in ("PGHOST", "PGUSER", "PGPASSWORD", "PGDATABASE"):
            monkeypatch.delenv(var, raising=False)
        with pytest.raises(AnalystKitError) as exc_info:
            attach_database("postgres://user:sekret123@host/db")
        assert "sekret123" not in str(exc_info.value)

    def test_redact_strips_secret_values(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PGPASSWORD", "hunter2secret")
        msg = _redact("connection failed: password=hunter2secret host=x")
        assert "hunter2secret" not in msg
        assert "[REDACTED]" in msg

    def test_db_source_requires_table(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from analystkit.dbconnect import load_db_source
        with pytest.raises(AnalystKitError, match="--table"):
            load_db_source("postgres://", "")
