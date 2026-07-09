"""Ported from v1.1 — planted-answer principle: plant the issue, verify found."""
from pathlib import Path

from analystkit import (
    Dimension,
    dimension_scores,
    load_source,
    profile_columns,
)


class TestProfile:
    def test_null_count_matches_planted(self, messy_csv: Path) -> None:
        con = load_source(messy_csv)
        email = next(p for p in profile_columns(con) if p.name == "email")
        assert email.nulls == 2

    def test_case_variants_detected(self, messy_csv: Path) -> None:
        con = load_source(messy_csv)
        status = next(p for p in profile_columns(con) if p.name == "status")
        # 'paid', 'PAID', ' paid' collapse to one value when lower(trim())
        assert status.case_variants >= 2

    def test_email_validity_below_one(self, messy_csv: Path) -> None:
        con = load_source(messy_csv)
        email = next(p for p in profile_columns(con) if p.name == "email")
        assert email.valid_ratio < 1.0      # 'not-an-email' planted

    def test_completeness_score_reflects_nulls(self, messy_csv: Path) -> None:
        con = load_source(messy_csv)
        profiles = profile_columns(con)
        scores = dimension_scores(con, profiles)
        completeness = scores[Dimension.COMPLETENESS]
        assert completeness is not None and completeness < 1.0

    def test_accuracy_is_never_scored(self, messy_csv: Path) -> None:
        """Accuracy requires an authoritative source; scoring it from the
        dataset alone would be fabrication. Must always be None."""
        con = load_source(messy_csv)
        scores = dimension_scores(con, profile_columns(con))
        assert scores[Dimension.ACCURACY] is None

    def test_uniqueness_below_one_with_dup_row(self, messy_csv: Path) -> None:
        con = load_source(messy_csv)
        scores = dimension_scores(con, profile_columns(con))
        uniq = scores[Dimension.UNIQUENESS]
        assert uniq is not None and uniq < 1.0


# ── Validation rules ─────────────────────────────────────────────────────────
