"""analystkit.ai — OPTIONAL narrative layer. The AI never touches data.

Architecture (the governance signature):

    deterministic engine  →  findings JSON  →  LLM narrative  →  labeled output
         (computes)           (audit boundary)    (explains)       (verifiable)

Non-negotiable design rules, enforced by construction:

1. The AI never writes SQL, never queries anything, never produces a
   number. Every figure in the narrative must already exist in the
   findings JSON computed by the deterministic engine. The prompt says
   so explicitly, and the output is labeled so a reviewer checks the
   narrative AGAINST the findings, never instead of them.

2. Off by default. Activated only by the --ai flag.

3. The API key is read from the ANTHROPIC_API_KEY environment variable
   only — the default documented by the official Anthropic Python SDK
   (platform.claude.com/docs, anthropic-sdk-python README). It is never
   accepted as an argument, never logged, never written to a workpaper.

4. The findings JSON is hashed (SHA-256) before the call. The hash is
   printed with the narrative, so even the AI step is re-performable:
   same findings JSON, same hash, and the narrative can be regenerated
   and compared.

5. If the SDK is not installed or the key is absent, the feature is
   cleanly absent: the tool is 100% functional without it and says in
   one line how to enable it. No nagging, no degradation.
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Final

from analystkit.core import AnalystKitError

__all__ = ["AI_MODEL", "ai_available", "findings_digest", "narrate_findings"]

AI_MODEL: Final[str] = "claude-sonnet-4-6"
_MAX_TOKENS: Final[int] = 1000

_SYSTEM_PROMPT: Final[str] = (
    "You are a data-quality reviewer writing a short narrative for a "
    "findings report. You are given a JSON document of findings computed "
    "by a deterministic engine. STRICT RULES: use ONLY facts and numbers "
    "present in the JSON; never compute, estimate, or extrapolate a "
    "number; never suggest SQL; if the JSON is empty, say the run found "
    "nothing. Write 3 short paragraphs maximum: what was tested, what "
    "was found (most severe first), and what a reviewer should verify "
    "first. Plain professional English, no bullet points, no headers."
)


def ai_available() -> bool:
    """True only when both the SDK and the key are present."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return True


def findings_digest(findings: dict[str, Any]) -> str:
    """SHA-256 of the canonical findings JSON — the audit boundary.

    sort_keys makes the serialization canonical, so the same findings
    always hash the same. This hash is what makes the AI step
    re-performable evidence rather than an unverifiable black box.
    """
    canonical = json.dumps(findings, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def narrate_findings(findings: dict[str, Any]) -> tuple[str, str]:
    """Returns (narrative, findings_sha256). Raises cleanly if unavailable.

    SDK usage follows the official Anthropic Python SDK documentation:
    client reads ANTHROPIC_API_KEY from the environment by default;
    messages.create(model=..., max_tokens=..., system=..., messages=[...]);
    response content blocks are iterated and only type == "text" is read.
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise AnalystKitError(
            "AI narrative needs the ANTHROPIC_API_KEY environment "
            "variable. The key is never accepted on the command line."
        )
    try:
        from anthropic import Anthropic
    except ImportError:
        raise AnalystKitError(
            "AI narrative needs the official SDK: "
            "pip install analystkit[ai]  (installs 'anthropic')."
        ) from None

    digest = findings_digest(findings)
    payload = json.dumps(findings, sort_keys=True, default=str, indent=2)

    client = Anthropic()  # key from ANTHROPIC_API_KEY per official SDK default
    message = client.messages.create(
        model=AI_MODEL,
        max_tokens=_MAX_TOKENS,
        system=_SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": (
                f"Findings JSON (sha256={digest}):\n\n{payload}"
            ),
        }],
    )
    narrative = "".join(
        block.text for block in message.content
        if getattr(block, "type", "") == "text"
    ).strip()
    if not narrative:
        raise AnalystKitError("AI narrative came back empty; nothing to show.")
    return narrative, digest


def print_narrative(narrative: str, digest: str) -> None:
    """Prints with the mandatory label. A reviewer verifies AGAINST the
    deterministic findings above, never instead of them."""
    print("\n" + "=" * 72)
    print("AI-GENERATED NARRATIVE — verify against the deterministic")
    print("findings above. The AI saw only the findings JSON; it ran no")
    print(f"queries and computed no numbers.  input sha256: {digest[:16]}…")
    print("=" * 72)
    print(narrative)
