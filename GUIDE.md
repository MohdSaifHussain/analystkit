# AnalystKit v2.0 — Design & Learning Guide

Read this once and you can defend every decision in this toolkit without help.

---

## 1. What problem does this solve?

Junior analysts at top-tier firms are trained into one discipline before anything
else: **profile before you analyse, reconcile before you report, document
everything.** Most self-taught analysts skip all three and get their work sent
back. AnalystKit builds that discipline into a tool — eight commands that make the
professional workflow the default workflow.

---

## 2. The framework: DAMA-DMBOK six dimensions

The DAMA-DMBOK (Data Management Body of Knowledge) is the closest thing the data
profession has to an official reference standard. Its six data quality dimensions
are the industry benchmark, used by regulators, auditors, and data teams globally:

| Dimension | What it measures | How AnalystKit scores it |
|---|---|---|
| **Completeness** | Is anything missing? | Null counts and ratios per column |
| **Uniqueness** | Is anything counted twice? | Exact-row and key-based duplicate detection |
| **Validity** | Do values match expected formats? | TRY_CAST ratios, regex patterns, range checks |
| **Consistency** | Does the same fact appear the same way everywhere? | Case and whitespace variant detection (`lower(trim())`) |
| **Timeliness** | How fresh is the data? | Age of the newest timestamp, linear decay over 90 days |
| **Accuracy** | Does it match the real world? | **Deliberately not scored — see below.** |

---

## 3. The decision that matters most: accuracy is never faked

Accuracy means agreement with reality. No tool can measure that from the dataset
alone — it requires an authoritative source to compare against. Tools that print an
"accuracy score" without a reference source are making it up.

AnalystKit prints "requires reconcile against authoritative source" instead, and
provides the `reconcile` command to actually do it. Honesty about limits is part
of the standard, not a weakness in it.

---

## 4. The tie-out (`reconcile`) — three checks, always in order

1. **Row counts** — the simplest check. A feed that arrives with 10,000 rows when
   12,000 are expected has lost records.
2. **Key matching** — which records exist on one side only? Orphan keys are
   findings, never garbage. A bank missed 1.6 million transactions for four years
   because a feed silently dropped records; row counts looked fine because the
   totals were close enough that nobody checked the keys.
3. **Control totals** — do the sums agree? A feed can have matching row counts and
   matching keys and still have corrupted amounts.

Always in this order. Finding a key mismatch before checking totals saves you from
explaining a total discrepancy that is actually a completeness problem.

---

## 5. What changed in v2.0 and why

### Multi-module src layout
The single file became a proper package (`src/analystkit/`), the layout documented
by the Python Packaging Authority (PyPA). `cli.py` contains dispatch only — zero
logic — so every function stays importable and testable independently of the CLI.

### Database sources, read-only by construction
`postgres://` and `mysql://` sources attach through DuckDB's official extensions
with `READ_ONLY` hardcoded — there is no flag to disable it. Credentials come from
environment variables only (`PGHOST`, `PGUSER`, `PGPASSWORD`, `PGDATABASE`), the
production pattern in DuckDB's own documentation. Credentials are never accepted
in the URI or CLI — DuckDB warns that connection errors can print the full
connection string, and CLI arguments leak into shell history.

### Three stacked injection defences
1. `READ_ONLY` attach — even a successful injection cannot write
2. Parameter binding — values can never become SQL (DuckDB Prepared Statements
   documentation)
3. Validate-then-quote identifiers — names can never become SQL (DuckDB Keywords
   and Identifiers documentation)

Three independent mechanisms, three independent official sources. Applying one fix
to both surfaces would leave one surface open.

### Robust CSV loading
The previous `read_csv_auto` used sample-based auto-detection for the quoting
character. On large files (13+ million rows), complex fields appear after the
detection sample window and the auto-detection gets it wrong — producing a
`_duckdb.InvalidInputException` instead of loading the data.

The fix uses `read_csv` with explicit parameters per DuckDB's official CSV
documentation:
- `header=true` — first row is column names (RFC 4180 default)
- `quote='"'` — RFC 4180 quoting, so a field like `"Insufficient Balance,Technical
  Glitch"` is ONE value, not two columns
- `strict_mode=false` — if a row cannot be parsed, record the parse error and
  continue rather than aborting the load (the same behaviour as Excel and every
  production CSV tool)

A regression test plants exactly this pattern (a quoted comma field) and verifies
the tool loads 3 rows with the field value intact, not 4 columns with a crash.

### Optional AI narrative
`validate --ai` adds a narrative under strict architecture:
- Deterministic engine computes ALL findings first
- Findings serialized to canonical JSON and SHA-256 hashed — this is the audit
  boundary
- Only that JSON reaches the model; the narrative returns labeled "verify against
  the deterministic findings above" with the input hash printed
- The AI never writes SQL, never queries data, never produces a number
- Same findings, same hash — the AI step is re-performable evidence

---

## 6. Engineering standards — name them in interviews

- **DuckDB engine**: SQL directly over CSV, Excel, SQLite, Postgres, MySQL. The
  PostgreSQL-compatible dialect means every practiced query transfers to production
  warehouses (Snowflake, BigQuery, Redshift). Any source becomes view `t` — one
  mental model.
- **`mypy --strict` zero errors**: every type annotation verified across 15 source
  files, `py.typed` marker included.
- **`ruff` clean**: the 2026-standard Python linter, configured in `pyproject.toml`.
- **58 tests on the planted-answer principle**: every fixture contains known issues
  and every test verifies the tool finds exactly those — never trust a test you
  cannot independently verify.
- **Four adversarial loophole hunts** — fourteen bugs found and closed:
  - Raw tracebacks on malformed JSON, bad column names, range rules on text columns
  - A silent-zero trap in `not_future` (a control that cannot fail is not a control)
  - A hardcoded clock in the demo that caused planted future dates to decay
  - CSV parser failure on real-world bank exports with quoted multi-value fields
  - The `ai.py` type narrowing not forward-compatible with SDK type changes
  Each fix verified against official documentation, each with a regression test
  proving the old failure.
- **Frozen slots dataclasses, StrEnum, timezone-aware IST timestamps, atomic Excel
  writes** (`os.replace` — no partial file on crash), SIGPIPE handled, no side
  effects on import.
- **GitHub Actions CI** runs all three gates (ruff, mypy strict, pytest) on every
  push — green on first commit.

---

## 7. Self-teaching by design

- `explain <topic>` — built-in lessons on all six DAMA dimensions, reconciliation,
  and workpapers, each with its SQL pattern.
- `--show-sql` on every analysis command — every run is a SQL lesson.
- The **Learn tab** in the workpaper — the deliverable teaches its reader.
- The **demo answer key** — printed before the tool runs so you always know what
  it should find before it does. Verify, do not trust.

---

## 8. The workpaper standard

A workpaper is analysis packaged as evidence: a reviewer must be able to re-perform
the work from the document alone and get the same answer. The `workpaper` command
embeds: who ran it, when (IST), on what source, with what procedures, what
assumptions, what limitations — plus the scorecard, the column profile, the
findings, and the SQL lessons.

This is the professional standard used by audit teams, compliance functions, and
data governance teams. The document is the evidence; the tool produces it.

---

## 9. Honest limitations

- Rules are declarative but simple: no cross-column logic yet (e.g. "refund date
  must be after order date").
- Consistency detection covers case/whitespace variants, not semantic duplicates
  ("St." vs "Street").
- Timeliness decays linearly over 90 days — a reasonable default, not a universal
  truth. When the newest timestamp is in the future, timeliness reads 100% but the
  profile prints a warning: future-dated records are a validity finding, not a
  freshness one.
- Reconcile accepts CSV on both sides.
- This is a single-analyst CLI, not a production monitoring platform.

---

## 10. The one-line story for interviews

"I built the discipline of a professional data team into a CLI: profile before
analysing, reconcile before reporting, document everything — with the tool teaching
its user the SQL and the standards as it works. Security-first, DAMA-grounded,
loophole-hunted."

---

## 11. Learning path (four weeks, 15 minutes a day)

**Week 1:** Run `demo`, then `profile` and `explain` each dimension. Predict what
profile will find before running it; check against the answer key.

**Week 2:** `validate` and `dedupe` with `--show-sql`. Read every query. Edit
`rules.json` — add a rule, break a rule, understand the failure.

**Week 3:** `reconcile` and `summarize` with `--show-sql`. Then write the SQL
patterns by hand in a separate DuckDB connection.

**Week 4:** Run `workpaper`, open every tab, and explain the Methodology tab out
loud to someone. If you can do that, you can do it in an interview.
