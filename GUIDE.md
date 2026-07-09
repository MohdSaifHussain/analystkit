# AnalystKit v2.0 — Design & Learning Guide (Plain English)

Read this twice and you can defend every decision in this toolkit without help.

---

## 1. What problem does this solve?

Junior analysts at top-tier firms are trained into one discipline before
anything else: **profile before you analyse, reconcile before you report,
document everything.** Most self-taught analysts skip all three and get
their work sent back. AnalystKit builds that discipline into a tool: eight
commands that make the professional workflow the default workflow.

## 2. The framework: DAMA six dimensions

The DAMA-DMBOK is the closest thing the data profession has to a standard
reference. Its six data quality dimensions are the industry benchmark:

- **Completeness** — is anything missing? (null counting)
- **Uniqueness** — is anything counted twice? (duplicate detection)
- **Validity** — do values match their expected format? (TRY_CAST ratios,
  email patterns)
- **Consistency** — does the same fact appear the same way everywhere?
  ('Paid' vs 'paid ' vs 'PAID' — the lower(trim()) collision check)
- **Timeliness** — how fresh is the data? (age of the newest timestamp)
- **Accuracy** — does it match the real world? **Deliberately NOT scored.**

## 3. The decision that matters most: accuracy is never faked

Accuracy means agreement with reality, and no tool can measure that from
the dataset alone — it requires an authoritative source to compare against.
Tools that print an "accuracy score" without a reference source are making
it up. AnalystKit prints "requires reconcile against authoritative source"
instead, and provides the `reconcile` command to actually do it. Honesty
about limits is part of the standard, not a weakness in it.

## 4. The tie-out (`reconcile`) — three checks, always in order

Row counts first, key matching second, control totals third. Orphan keys
(records existing on only one side) are findings, never garbage — the
completeness principle, from the case where a bank missed 1.6 million
transactions for four years because a feed silently dropped records.

## 4b. What changed in v2.0 — and the official source behind each decision

**Multi-module src layout.** The single file became a proper package
(`src/analystkit/`), the layout documented by the Python Packaging
Authority. `cli.py` contains dispatch only — zero logic — so every
function stays importable and testable. Install once (`pip install -e .`)
and both `analystkit` and `python -m analystkit` work.

**Database sources, read-only by construction.** `postgres://` and
`mysql://` sources attach through DuckDB's official extensions with
READ_ONLY hardcoded — there is no flag to disable it. An analysis tool
never needs write access; least privilege is enforced by the code, not
by policy. Credentials come from environment variables only (PGHOST,
PGUSER, PGPASSWORD, PGDATABASE), the production pattern in DuckDB's own
documentation. Credentials are never accepted in the URI or CLI — the
DuckDB docs warn that connection errors can print the full connection
string, and CLI arguments leak into shell history. Persistent secrets
are never used: the docs warn they are stored unencrypted on disk.
Every error message is redacted against the credential environment
variables before it is raised — a password can never be echoed, and a
test proves it.

**Three stacked injection defences.** A connected database sits behind:
(1) READ_ONLY attach — even a successful injection cannot write;
(2) parameter binding — values can never become SQL (DuckDB Prepared
Statements docs); (3) validate-then-quote identifiers — names can never
become SQL (DuckDB Keywords and Identifiers docs). Three independent
mechanisms, three independent official sources.

**Optional AI narrative — the governance signature made explicit.**
`validate --ai` adds a narrative, under strict architecture: the
deterministic engine computes ALL findings first; the findings are
serialized to canonical JSON and SHA-256 hashed (the audit boundary);
only that JSON goes to the model; the narrative comes back labeled
"verify against the deterministic findings above" with the input hash
printed. The AI never writes SQL, never touches data, never produces a
number. SDK usage follows the official Anthropic Python SDK docs: key
from ANTHROPIC_API_KEY only, never logged, never in a workpaper. No
key installed → the feature is cleanly absent and the tool is 100%
functional. This is the full pattern in one tool: deterministic
computation → audit boundary → LLM explanation → labeled, hash-verified
output.

## 5. The engineering standards (name them in interviews)

- **DuckDB engine**: SQL directly over CSV/Excel/SQLite; PostgreSQL-
  compatible dialect, so every practiced query transfers to production
  warehouses. Any source becomes view `t` — one mental model.
- **mypy --strict, zero errors**: every type annotation verified.
- **ruff clean**: the 2026-standard linter, configured in pyproject.toml.
- **49 pytest tests on the planted-answer principle**: the demo data
  contains known issues, and the tests verify the tool finds exactly
  those — never trust a test you cannot independently check. Every
  hardening fix landed with its own test proving the old failure.
- **Loophole-hunted, twice**: hostile inputs were thrown at it before
  release, then a second adversarial review (v1.1) found and fixed four
  more. Round one: empty datasets warn instead of scoring a meaningless
  100%; rules naming a nonexistent column fail with a clean message.
  Round two (each fix verified against DuckDB's official documentation,
  each with its own planted-answer test):
    1. **Identifier quoting** — column names containing a double-quote
       crashed every command. Fixed with SQL-standard escaping (internal
       quotes doubled), per the DuckDB "Keywords and Identifiers" doc.
       Even DuckDB's own Python relational API had this bug (issue #15267).
    2. **Parameter binding** — user-supplied VALUES (range bounds,
       allowed sets, regex patterns) are now bound as prepared-statement
       parameters (?), DuckDB's documented SQL-injection defence.
       Identifiers cannot be parameters in SQL, which is why both
       mechanisms exist: validate-then-quote for names, bind for values.
    3. **Clean errors everywhere** — reconcile --key, summarize --by,
       dedupe --key, and range-on-a-text-column all produced raw
       tracebacks; every one now raises a readable AnalystKitError
       listing the real columns.
    4. **The silent-zero trap** — not_future on a column with no
       parseable timestamps reported 0 failures and looked perfectly
       clean while measuring nothing. It now refuses to run and says why.
       A control that cannot fail is not a control.
  Plus: the demo's hardcoded clock meant its planted "future" dates
  decayed into the past within days; it now uses the real clock, and a
  test proves the not_future rule finds exactly the 6 planted violations.
- **Frozen slots dataclasses, StrEnum, timezone-aware IST timestamps,
  atomic Excel writes, no side effects on import, SIGPIPE handled.**

## 6. Self-teaching by design

- `explain <topic>` — built-in lessons on all six dimensions plus
  reconciliation and workpapers, each with its SQL pattern.
- `--show-sql` on every analysis command — every use is a SQL lesson.
- The workpaper's **Learn tab** — the deliverable teaches its reader.
- The demo prints its **answer key** — you always know what the tool
  SHOULD find before it runs, so you can verify it, not trust it.

## 7. The workpaper standard

A workpaper is analysis packaged as evidence: a reviewer must be able to
re-perform the work from the document alone and get the same answer. The
`workpaper` command therefore embeds: who ran it, when (IST), on what
source, with what procedures, what assumptions, and what limitations —
plus the scorecard, the column profile, the findings, and the lessons.

## 8. Honest limitations

- Rules are declarative but simple: no cross-column logic yet (e.g.
  "refund date must be after order date").
- Consistency detection covers case/whitespace variants, not semantic
  duplicates ("St." vs "Street").
- Timeliness decays linearly over 90 days — a reasonable default, not a
  universal truth; different data has different freshness expectations.
  When the newest timestamp is in the FUTURE, timeliness reads 100% but
  the profile prints a warning: future-dated records are a validity
  finding, not freshness.
- Reconcile accepts CSV on both sides (still — databases are for
  single-source analysis commands in v2).
- This is a single-analyst toolkit, not a monitoring platform.

## 9. The one-line story

"I built the discipline of a top-tier data team into a toolkit: profile
before analysing, reconcile before reporting, document everything — with
the tool teaching its user the SQL and the standards as it works."

## 10. Learning path (four weeks, 15 minutes a day)

Week 1: run `demo`, then `profile` and `explain` each dimension. Predict
what profile will find before running it; check against the answer key.
Week 2: `validate` and `dedupe` with --show-sql. Read every query. Modify
rules.json — add a rule, break a rule, understand the failure.
Week 3: `reconcile` and `summarize` with --show-sql; then the SQL
cheat sheet patterns by hand via a `query` command in OpsKit.
Week 4: run `workpaper`, read every tab, and explain the Methodology tab
out loud to someone. If you can do that, you can do it in an interview.
