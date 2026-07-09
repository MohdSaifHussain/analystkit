![AnalystKit Architecture](https://github.com/user-attachments/assets/71373898-6192-4f95-9f8b-790001790275)

# AnalystKit

Data quality & analysis toolkit — DAMA six dimensions, workpaper discipline, self-teaching by design.

Built for the discipline top-tier data teams enforce: **profile before you analyse, reconcile before you report, document everything.**

## What it does

Eight commands over one mental model — any source becomes view `t`:

| Command | What it does |
|---|---|
| `profile` | DAMA six-dimension quality scorecard (accuracy deliberately never scored) |
| `validate` | Declarative rules from JSON — unique, not_null, range, allowed, regex, not_future |
| `dedupe` | Exact-row and key-based duplicate detection with evidence |
| `reconcile` | The tie-out: row counts, key matching, control totals — orphans are findings, never garbage |
| `summarize` | Grouped metrics with validated columns |
| `workpaper` | Reviewer-grade Excel deliverable: methodology, scorecard, profile, findings, lessons |
| `explain` | Built-in lesson on any dimension or concept |
| `demo` | Messy practice data with a printed answer key |

Sources: CSV, Excel, SQLite files — or `postgres://` / `mysql://` (read-only, credentials from environment variables only).

## Install

```bash
pip install -e .            # core
pip install -e ".[ai]"      # + optional AI narrative layer
pip install -e ".[dev]"     # + pytest, mypy, ruff
```

## Quick start

```bash
analystkit demo --out demo_data          # planted issues + printed answer key
analystkit profile demo_data/orders.csv
analystkit validate demo_data/orders.csv --rules demo_data/rules.json
analystkit workpaper demo_data/orders.csv --rules demo_data/rules.json --key order_id
```

## Security architecture (every decision traced to official documentation)

**Database sources are read-only by construction.** `ATTACH ... READ_ONLY` is hardcoded — there is no flag to disable it (DuckDB PostgreSQL extension docs). Credentials come from environment variables only (`PGHOST`, `PGUSER`, `PGPASSWORD`, `PGDATABASE`), never the URI or CLI — DuckDB's docs warn a failed connection string can print credentials to the terminal. Persistent secrets are never used — DuckDB's docs warn they are stored unencrypted on disk. Every error message is redacted against credential environment variables before raising, and a test proves a planted password never appears in output.

**Three stacked injection defences:**
1. READ_ONLY attach — even a successful injection cannot write
2. Prepared-statement parameter binding — values can never become SQL (DuckDB Prepared Statements docs)
3. Validate-then-quote identifiers — names can never become SQL (DuckDB Keywords and Identifiers docs)

**The optional AI layer never touches data.** With `validate --ai`: the deterministic engine computes all findings first; findings are serialized to canonical JSON and SHA-256 hashed (the audit boundary); only that JSON reaches the model; the narrative returns labeled for verification against the deterministic findings, with the input hash printed. The AI never writes SQL, never queries anything, never produces a number. Key from `ANTHROPIC_API_KEY` only (official Anthropic SDK default), never logged, never in a workpaper. Without a key the feature is cleanly absent and the tool is 100% functional.

## Engineering standards

- `mypy --strict`, zero errors, `py.typed` marker
- `ruff` clean (E, F, W, I, N, UP, B, C4, SIM, RUF)
- 53 pytest tests on the **planted-answer principle**: fixtures contain known issues, tests verify the tool finds exactly those — never trust a test you cannot independently check
- Loophole-hunted three times; every fix landed with a test proving the old failure
- Frozen slots dataclasses, StrEnum, timezone-aware IST timestamps, atomic Excel writes (`os.replace`), SIGPIPE handled, no side effects on import
- src layout per PyPA packaging guidance; `cli.py` is dispatch-only

## Honest limitations

Single-analyst toolkit, not a monitoring platform. Rules have no cross-column logic yet. Consistency detection covers case/whitespace variants, not semantic duplicates. Timeliness decays linearly over 90 days — a reasonable default, not a universal truth. Reconcile accepts CSV on both sides. Accuracy is never scored from the dataset alone, because that would be fabrication — that's what `reconcile` is for.

## Development approach

Designed, specified, and governed by Mohd Saif Hussain; implementation AI-directed with every architectural and security decision human-made, verified against primary sources (DuckDB official documentation, PyPA packaging guidance, official Anthropic SDK documentation), and gated through adversarial review — three loophole hunts, ten bugs found and closed, each with a regression test.

## License

MIT
