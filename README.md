[![CI](https://github.com/MohdSaifHussain/analystkit/actions/workflows/ci.yml/badge.svg)](https://github.com/MohdSaifHussain/analystkit/actions/workflows/ci.yml)

![AnalystKit Architecture](https://github.com/user-attachments/assets/71373898-6192-4f95-9f8b-790001790275)

# AnalystKit

**Profile before you analyse. Reconcile before you report. Document everything.**

Most data tools tell you what the data looks like. AnalystKit tells you whether
you can trust it — and produces a workpaper a reviewer can re-perform without
asking you a single follow-up question.

Built on the DAMA-DMBOK six dimensions — the industry benchmark for professional
data quality work. Eight commands. Five source types. One mental model.

One deliberate omission: **accuracy is never scored.** No tool can measure
accuracy without an authoritative source to compare against. Scoring it from the
dataset alone is fabrication. The `reconcile` command exists specifically for that
purpose — it is the honest alternative, not a workaround.

---

## Install

```bash
git clone https://github.com/MohdSaifHussain/analystkit.git
cd analystkit
pip install -e .
```

No extra steps. CSV, Excel, SQLite, PostgreSQL, and MySQL sources work out of the
box. Optional extras:

```bash
pip install -e ".[ai]"   # AI narrative layer — needs ANTHROPIC_API_KEY
pip install -e ".[dev]"  # pytest, mypy, ruff for development
```

Requires **Python 3.12+**.

---

## 60-second start

```bash
# Create messy practice data with a printed answer key
analystkit demo --out demo_data
# Prints exactly what issues are planted before you run anything.
# That is the planted-answer philosophy: verify, do not trust.

# DAMA six-dimension quality scorecard
analystkit profile demo_data/orders.csv

# Validate against declared rules
analystkit validate demo_data/orders.csv --rules demo_data/rules.json

# Reconcile two sources — tie-out row counts, keys, control totals
analystkit reconcile demo_data/orders.csv demo_data/customers.csv \
    --key customer_id --total amount

# Produce the workpaper — the re-performable evidence package
analystkit workpaper demo_data/orders.csv \
    --rules demo_data/rules.json --key order_id
```

---

## Real-world example — a transaction monitoring feed

A bank CSV export arrives. It is large (13 million rows), contains quoted
multi-value fields in the errors column, and someone needs to know whether the
feed is complete before any analysis runs. AnalystKit handles it with one command,
no preprocessing:

```bash
analystkit profile transactions.csv
```

```
Dimension       Score   Detail
Completeness    0.887   merchant_state: 11.9% null  zip: 12.6% null
Uniqueness      1.000   no duplicate transaction ids found
Validity        0.943   errors column: 98.5% null — confirm field population logic
Consistency     0.977   2 case variants in use_chip
Timeliness      0.000   newest record: 2019-10-30 (2,447 days) — confirm feed age
Accuracy               requires reconcile against authoritative source
```

Every figure is deterministic SQL. Re-run the same command on the same file: the
numbers are identical. That is re-performable evidence — the property regulators
now require from AML and data quality programmes.

```bash
# Validate completeness rules and document findings
analystkit validate transactions.csv --rules txn_rules.json

# Produce the workpaper — methodology, scorecard, findings, lessons
analystkit workpaper transactions.csv --rules txn_rules.json --key id
```

---

## All eight commands

| Command | Professional discipline | What it does |
|---|---|---|
| `profile` | Profile before you analyse | DAMA six-dimension scorecard — accuracy never scored |
| `validate` | Validate against declared rules | Declarative JSON rules: unique, not_null, range, allowed, regex, not_future |
| `dedupe` | Deduplicate before reporting | Exact-row and key-based duplicate detection with evidence samples |
| `reconcile` | Reconcile before you sign off | Row counts, key matching, control totals — orphans are findings, not garbage |
| `summarize` | Summarize for the business | Grouped metrics with validated column names |
| `workpaper` | Document everything | Reviewer-grade Excel: methodology, scorecard, profile, findings, lessons |
| `explain` | Teach as you work | Built-in lessons on all six DAMA dimensions with SQL patterns |
| `demo` | Verify before you trust | Messy practice data with a printed answer key |

Every analysis command accepts `--show-sql` — every run is a SQL lesson in the
PostgreSQL-compatible dialect that transfers to Snowflake, BigQuery, and Redshift.

---

## Data sources

One mental model across all sources — any input becomes view `t`:

| Source | Example |
|---|---|
| CSV (including large files with quoted multi-value fields) | `analystkit profile data.csv` |
| Excel (.xlsx / .xls) | `analystkit profile data.xlsx` |
| SQLite | `analystkit profile data.sqlite --table orders` |
| PostgreSQL | `analystkit profile postgres:// --table orders` |
| MySQL | `analystkit profile mysql:// --table orders` |

Database sources attach **READ_ONLY by construction.** The tool physically cannot
write to a connected database — there is no flag to disable this. Credentials from
environment variables only (`PGHOST`, `PGUSER`, `PGPASSWORD`, `PGDATABASE`),
never the URI or CLI arguments.

---

## Validation rules — quick reference

Rules live in a JSON file. Every rule needs `column` and `rule`:

```json
[
  { "column": "order_id",    "rule": "unique" },
  { "column": "customer_id", "rule": "not_null" },
  { "column": "amount",      "rule": "range",   "min": 0, "max": 100000 },
  { "column": "status",      "rule": "allowed", "values": ["paid", "shipped", "returned"] },
  { "column": "email",       "rule": "regex",   "pattern": "^[^@]+@[^@]+\\.[^@]+$" },
  { "column": "order_date",  "rule": "not_future" }
]
```

Available rules: `unique`, `not_null`, `range`, `allowed`, `regex`, `not_future`.
Values are parameter-bound — they can never become SQL.

---

## Who this is for

**Data analysts** who receive a vendor file and need to profile it before
touching it, produce evidence a reviewer can re-perform, or build SQL skills while
doing real work. Every command has `--show-sql`.

**Operations professionals** who reconcile two reports before presenting to
leadership, validate data feeds against declared rules, or need to document
methodology without three hours in Excel.

**Controls testers and auditors** (3rd Line of Defence) who need re-performable
evidence. The workpaper embeds who ran it, when (IST-timestamped), on what source,
with what procedures, what assumptions, and what limitations. A reviewer re-performs
the work from the document alone and gets the same answer. This is the software
embodiment of workpaper discipline.

**Data scientists** who spend 80% of their time on data cleaning. Profile and
validate training data first. The workpaper is the data-side equivalent of MLflow.

**Anyone transitioning from Excel** who needs professional data discipline and SQL
skills simultaneously. The `explain` command has built-in lessons on all six DAMA
dimensions with their SQL patterns.

---

## Security architecture

Every decision traces to an official primary source — not a blog post.

**Three stacked injection defences:**

1. **READ_ONLY attach** — even a successful injection cannot write. Source: DuckDB
   PostgreSQL extension documentation.
2. **Prepared-statement parameter binding** — values are bound as `?` parameters
   and can never become SQL. Source: DuckDB Prepared Statements documentation.
3. **Validate-then-quote identifiers** — column names are validated against the
   schema, then standard-quoted via SQL-standard double-quote doubling. Names can
   never become SQL. Source: DuckDB Keywords and Identifiers documentation.

**Credential safety:** environment variables only; persistent secrets never used;
every error message redacted against credential values; a test proves a password
never appears in any error output.

**The optional AI layer never touches data.** With `validate --ai`: deterministic
engine first → findings hashed to SHA-256 (audit boundary) → only the hash and
findings JSON reach the model → narrative labeled "verify against the deterministic
findings above." Same findings, same hash. AI never writes SQL, queries data, or
produces a number.

---

## Engineering standards

- `mypy --strict` zero errors across 15 source files, `py.typed` marker included
- `ruff` clean — E, F, W, I, N, UP, B, C4, SIM, RUF
- **58 tests on the planted-answer principle** — every fixture contains known
  issues; every test verifies the tool finds exactly those
- **Four adversarial loophole hunts** — fourteen bugs found and closed, each with
  a regression test proving the old failure, each fix verified against official
  documentation
- **Robust CSV loading** — `read_csv` with explicit parameters per DuckDB's CSV
  documentation: RFC 4180 quoting, `strict_mode=false`. Real bank exports with
  quoted multi-value fields (e.g. `"Insufficient Balance,Technical Glitch"`) load
  without a preprocessing step.
- Frozen slots dataclasses, StrEnum, timezone-aware IST timestamps, atomic Excel
  writes (`os.replace`), SIGPIPE handled, no side effects on import
- src layout per PyPA packaging guidance; `cli.py` is dispatch-only
- GitHub Actions CI on every push — green on first commit

---

## Honest limitations

Single-analyst CLI, not a production monitoring platform. No cross-column
validation rules yet. Consistency detection covers case and whitespace variants,
not semantic duplicates. Timeliness decays linearly over 90 days. Reconcile
accepts CSV on both sides. Accuracy is never scored from the dataset alone — a
principled refusal, not a gap.

---

## Development approach

Designed, specified, and governed by **Mohd Saif Hussain**. Implementation
AI-directed.

Every architectural and security decision was human-made and verified against a
primary source: DuckDB official documentation for CSV loading, identifier quoting,
prepared statements, READ_ONLY attach, and credential handling; PyPA packaging
guidance for src layout; official Anthropic Python SDK documentation for the AI
layer.

Four adversarial loophole hunts, fourteen bugs found and closed. The
planted-answer philosophy runs throughout: the demo prints its answer key before
running. A test you cannot independently verify is not a test.

---

## License

MIT — see [LICENSE](LICENSE).

## v2.0.2 — per-dtype comparison domains in the `allowed` rule

The v2.0.1 boolean bug turned out to be one member of a FAMILY:
comparison-domain mismatches at the type boundary, failing silently
per-row. Probing after the fix found two live siblings — an integer
column vs `values: [1.0, 0.0]` and a float column vs `values: [1, 0]`
each produced 100% false failures (`'1'` vs `'1.0'` after VARCHAR
casting). v2.0.2 closes the class: numeric columns are now compared
NUMERICALLY (no string round-trip at all; non-numeric allowed values
are a loud error), booleans keep the v2.0.1 canonicalization, and
everything else keeps strict string comparison. A type-boundary test
matrix pins the behavior for every dtype family × caller value style,
so any regression of this class fails a named test instead of
shipping.

## v2.0.1 — boolean canonicalization in the `allowed` rule

Found in production by a Delivery Engine run on a 500k-row transaction
dataset: DuckDB casts BOOLEAN to VARCHAR as lowercase `true`/`false`,
while callers naturally write Python bools (`str(True) == 'True'`),
title-case strings, or `1`/`0` — so every row "failed" the allowed
check on perfectly valid data (1.5M false exceptions). The `allowed`
rule now canonicalizes values for BOOLEAN columns only. VARCHAR
categoricals keep strict, case-sensitive comparison, and an
unrecognizable boolean literal for a BOOLEAN column is a loud
`AnalystKitError`, never a rule that silently fails every row.
