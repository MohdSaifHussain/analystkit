"""AI layer invariants: off by default, cleanly absent without a key,
re-performable via the findings digest, output always labeled.

The API is mocked — no network, no key needed to test the invariants.
"""
import sys
import types
from typing import Any

import pytest

from analystkit.ai import ai_available, findings_digest, narrate_findings
from analystkit.core import AnalystKitError

SAMPLE = {
    "command": "validate",
    "rules_evaluated": 2,
    "total_exceptions": 3,
    "results": [{"rule_id": "R01", "failures": 3}],
}


class TestDigest:
    def test_digest_is_reproducible(self) -> None:
        """Same findings, same hash — the AI step is re-performable."""
        assert findings_digest(SAMPLE) == findings_digest(dict(SAMPLE))

    def test_digest_changes_with_findings(self) -> None:
        changed = dict(SAMPLE, total_exceptions=4)
        assert findings_digest(SAMPLE) != findings_digest(changed)

    def test_digest_key_order_independent(self) -> None:
        reordered = {k: SAMPLE[k] for k in reversed(list(SAMPLE))}
        assert findings_digest(SAMPLE) == findings_digest(reordered)


class TestCleanAbsence:
    def test_unavailable_without_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        assert ai_available() is False

    def test_narrate_without_key_clean_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        with pytest.raises(AnalystKitError, match="ANTHROPIC_API_KEY"):
            narrate_findings(SAMPLE)


class TestMockedNarrative:
    def _install_mock_sdk(
        self, monkeypatch: pytest.MonkeyPatch, captured: dict[str, Any]
    ) -> None:
        """A fake 'anthropic' module following the official SDK shape:
        Anthropic().messages.create(...) -> message.content blocks."""

        class _Block:
            type = "text"
            text = "Deterministic engine found three exceptions in R01."

        class _Message:
            def __init__(self) -> None:
                self.content = [_Block()]

        class _Messages:
            def create(self, **kwargs: Any) -> _Message:
                captured.update(kwargs)
                return _Message()

        class _Anthropic:
            def __init__(self, **kwargs: Any) -> None:
                self.messages = _Messages()

        fake = types.ModuleType("anthropic")
        fake.Anthropic = _Anthropic  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "anthropic", fake)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")

    def test_narrative_returned_with_digest(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict[str, Any] = {}
        self._install_mock_sdk(monkeypatch, captured)
        narrative, digest = narrate_findings(SAMPLE)
        assert "three exceptions" in narrative
        assert digest == findings_digest(SAMPLE)

    def test_prompt_forbids_computation(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The system prompt must instruct: numbers from the JSON only."""
        captured: dict[str, Any] = {}
        self._install_mock_sdk(monkeypatch, captured)
        narrate_findings(SAMPLE)
        assert "never compute" in captured["system"]
        assert "never suggest SQL" in captured["system"]

    def test_findings_json_is_the_only_payload(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The AI sees the findings JSON and its hash — nothing else."""
        captured: dict[str, Any] = {}
        self._install_mock_sdk(monkeypatch, captured)
        _, digest = narrate_findings(SAMPLE)
        user_content = captured["messages"][0]["content"]
        assert digest in user_content
        assert '"rules_evaluated": 2' in user_content
