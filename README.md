![AnalystKit Architecture](https://github.com/user-attachments/assets/71373898-6192-4f95-9f8b-790001790275)
![AnalystKit Architecture](https://github.com/user-attachments/assets/71373898-6192-4f95-9f8b-790001790275)

# AnalystKit

**Profile before you analyse. Reconcile before you report. Document everything.**

Most data tools tell you what the data looks like. AnalystKit tells you whether you can trust it — and produces a workpaper a reviewer can re-perform without asking you a single follow-up question.

Built on the DAMA-DMBOK six dimensions — the industry benchmark for professional data quality work. Eight commands. Five source types. One mental model.

One deliberate omission: **accuracy is never scored.** No tool can measure accuracy without an authoritative source to compare against. Scoring it from the dataset alone is fabrication. The `reconcile` command exists specifically for that purpose — it is the honest alternative, not a workaround.

---

## Who this is for

**Data analysts** who receive a vendor file and need to profile it before touching it, produce evidence a reviewer can re-perform, or build SQL skills while getting real work done. Every command has `--show-sql` — every use is a SQL lesson in the PostgreSQL-compatible dialect that transfers directly to Snowflake, BigQuery, and Redshift.

**Operations professionals** who reconcile two reports before presenting to leadership, validate data feeds against declared rules, or need to document their methodology without spending three hours in Excel.

**Controls testers and auditors** who need re-performable evidence, not just findings. The workpaper embeds who ran it, when (IST-timestamped), on what source, with what procedures, what assumptions, and what limitations. A reviewer can re-perform the work from the document alone and get the same answer.

**Data scientists** who spend 80% of their time on data cleaning before a model touches anything. Profile and validate your training data first. The workpaper is the data-side equivalent of MLflow — a timestamped, methodology-documented record of what the data looked like before modelling began.

**Anyone transitioning from Excel** who needs professional data discipline and SQL skills simultaneously, without stopping to take a course. The `explain` command has built-in lessons on all six DAMA dimensions with their SQL patterns. The Learn tab in the workpaper teaches its reader as they review it.

---

## What it does

Eight commands, each mapped to a named professional discipline:

| Command | Discipline | What it does |
|---|---|---|
| `profile` | Profile before you analyse | DAMA six-dimension quality scorecard — accuracy deliberately never scored |
| `validate` | Validate against declared rules | Declarative JSON rules — unique, not_null, range, allowed, regex, not_future |
| `dedupe` | Deduplicate before reporting | Exact-row and key-based duplicate detection with evidence samples |
| `reconcile` | Reconcile before you sign off | Tie-out: row counts, key matching, control totals — orphans are findings, never garbage |
| `summarize` | Summarize for the business | Grouped metrics with validated column names |
| `workpaper` | Document everything | Reviewer-grade Excel: methodology, scorecard, profile, findings, lessons |
| `explain` | Teach as you work | Built-in lessons on all six dimensions with SQL patterns |
| `demo` | Verify before you trust | Messy practice data with a printed answer key — know what the tool should find before it runs |

---

## Data sources supported

One mental model across all sources — any input becomes view `t`:

| Source | Example |
|---|---|
| CSV | `analystkit profile data.csv` |
| Excel (.xlsx) | `analystkit profile data.xlsx` |
| SQLite | `analystkit profile data.sqlite --table orders` |
| PostgreSQL | `analystkit profile postgres:// --table orders` |
| MySQL | `analystkit profile mysql:// --table orders` |

Database sources attach **READ_ONLY by construction.** The tool physically cannot write to a connected database — there is no flag to disable this. Credentials from environment variables only (`PGHOST`, `PGUSER`, `PGPASSWORD`, `PGDATABASE`), never the URI or CLI arguments.

---

## Install

```bash
pip install -e .            # core — CSV, Excel, SQLite, Postgres, MySQL
pip install -e ".[ai]"      # + optional AI narrative layer (needs ANTHROPIC_API_KEY)
pip install -e ".[dev]"     # + pytest, mypy, ruff for development
```

Requires Python 3.12+.

---

## Quick start

```bash
analystkit demo --out demo_data
# Prints the answer key: exactly what issues are planted and how many.
# Then verify the tool finds them:

analystkit profile demo_data/orders.csv
analystkit validate demo_data/orders.csv --rules demo_data/rules.json
analystkit reconcile demo_data/orders.csv demo_data/customers.csv --key customer_id --total amount
analystkit workpaper demo_data/orders.csv --rules demo_data/rules.json --key order_id
```

---

## Security architecture

Every decision below traces to an official primary source — not a blog post.

**Three stacked injection defences:**

1. **READ_ONLY attach** — even a successful injection cannot write to the database. Source: DuckDB PostgreSQL extension documentation.
2. **Prepared-statement parameter binding** — all user-supplied values (range bounds, allowed sets, regex patterns) are bound as `?` parameters. Values can never become SQL. Source: DuckDB Prepared Statements documentation.
3. **Validate-then-quote identifiers** — column names are validated against the schema, then standard-quoted via SQL-standard double-quote doubling. Names can never become SQL. Source: DuckDB Keywords and Identifiers documentation.

Two different surfaces, two different mechanisms — because they are two different problems. Applying one fix to both would leave one surface open.

**Credential safety:**
- Credentials accepted from environment variables only — DuckDB's docs warn that a failed connection string can print credentials to the terminal
- Persistent secrets never used — DuckDB's docs warn they are stored unencrypted on disk
- Every error message is redacted against credential environment variable values before raising
- A planted-answer test proves a password never appears in any error output

**The optional AI layer never touches data.** With `validate --ai`:
- The deterministic engine computes all findings first
- Findings are serialized to canonical JSON and SHA-256 hashed — this is the audit boundary
- Only that hash and the findings JSON reach the model
- The narrative returns labeled: "verify against the deterministic findings above"
- Same findings, same hash — even the AI step is re-performable evidence
- The AI never writes SQL, never queries anything, never produces a number
- API key from `ANTHROPIC_API_KEY` only — never logged, never written to a workpaper
- No key installed: the feature is cleanly absent, the tool is 100% functional

---

## Engineering standards

- `mypy --strict` zero errors across 15 source files, `py.typed` marker included
- `ruff` clean — E, F, W, I, N, UP, B, C4, SIM, RUF rule sets
- **53 pytest tests on the planted-answer principle**: every fixture contains known issues, every test verifies the tool finds exactly those — never trust a test you cannot independently verify
- **Three adversarial loophole hunts** across the project's life — ten bugs found and closed, each with a regression test proving the old failure. Fixes verified against official documentation, not guessed
- Frozen slots dataclasses, StrEnum, timezone-aware IST timestamps, atomic Excel writes via `os.replace` (no partial file on crash), SIGPIPE handled, no side effects on import
- src layout per PyPA packaging guidance; `cli.py` is dispatch-only — every function is independently importable and testable
- GitHub Actions CI runs all three gates (ruff, mypy strict, pytest) on every push — green on first commit

---

## Honest limitations

Single-analyst CLI, not a production monitoring platform. No cross-column validation rules yet (e.g. refund date must be after order date). Consistency detection covers case and whitespace variants, not semantic duplicates ("St." vs "Street"). Timeliness decays linearly over 90 days — a reasonable default, not a universal truth. Reconcile accepts CSV on both sides. Accuracy is never scored from the dataset alone — that is not a gap, it is a principled refusal. A tool that prints an accuracy score without an authoritative reference source is fabricating a number.

---

## Development approach

Designed, specified, and governed by Mohd Saif Hussain. Implementation AI-directed.

Every architectural and security decision was human-made and verified against a primary source before shipping: DuckDB official documentation for identifier quoting, prepared statements, READ_ONLY attach, and credential handling; PyPA packaging guidance for src layout; official Anthropic Python SDK documentation for AI layer integration.

Three adversarial loophole hunts were run against the codebase. Ten bugs were found — raw tracebacks on malformed JSON, on bad column names in reconcile and summarize, on range rules applied to text columns, a silent-zero trap in not_future, a hardcoded clock in the demo that caused planted future dates to decay. Each was fixed, each fix was verified against official documentation, and each has a regression test that proves the old failure.

The planted-answer philosophy runs throughout: the demo prints its answer key before running so you always know what the tool should find. The tests plant known issues and verify they are found. A test you cannot independently check is not a test.

---

## License

MIT
