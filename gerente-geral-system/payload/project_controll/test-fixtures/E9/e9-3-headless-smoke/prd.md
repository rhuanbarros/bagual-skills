---
title: Expense CSV Summary CLI
status: final
created: 2026-07-11
updated: 2026-07-11
---

# PRD: Expense CSV Summary CLI
*Working title — confirm.*

## 0. Document Purpose
This PRD captures the intent and requirements for a small personal CLI tool. It is written for a single developer (the builder, who is also the sole user) and is scoped to hobby-tier rigor: enough to guide implementation, not enough to imply a team, a roadmap, or compliance obligations. No prior inputs (brief, research, design docs) existed for this project; everything below derives from the brief provided at kickoff. [ASSUMPTION: no additional context beyond the brief exists or is expected for this run.]

## 1. Vision
A single-developer, personal-use command-line tool that takes a CSV export of expenses and produces a monthly summary report — total spend per category, per month. The goal is simply to stop manually totaling receipts in a spreadsheet; feed it a CSV, get a readable summary back. It matters only insofar as it saves the builder a few minutes each month — no broader ambition implied.

## 2. Target User

### 2.1 Jobs To Be Done
- As the builder, I want to convert a raw expenses CSV into a per-category monthly total so I don't have to tally it by hand.
- As the builder, I want a fast, no-fuss CLI I can run locally without setting up infrastructure.

### 2.3 Key User Journeys
- **UJ-1.** The builder, at month's end, exports their expenses to CSV from wherever they track spending, runs the script against that file from a terminal, and gets back a monthly summary (total per category) printed or written to a report file. [ASSUMPTION: "lighter" scope dial used per template — a single-sentence UJ is sufficient for a solo hobby CLI.]

## 3. Glossary
- **Expense CSV** — the input file: a CSV export where each row is a single expense transaction, minimally containing a date, an amount, and a category.
- **Category** — a user- or source-defined label on each expense row (e.g. "Groceries", "Transport") used as the grouping key for totals.
- **Monthly Summary Report** — the tool's output: for each month present in the input, the total amount spent per category.

## 4. Features

### 4.1 CSV Ingestion
**Description:** The script reads a single expenses CSV file supplied by the user (e.g. as a command-line argument) and parses each row into a date, amount, and category. Realizes UJ-1. [ASSUMPTION: input CSV has a header row identifying date/amount/category columns; exact column names are configurable or auto-detected at implementation time — not specified in the brief.]

**Functional Requirements:**

#### FR-1: Load and parse expenses CSV
The user can run the script with a path to a CSV file and have it parsed into individual expense records (date, amount, category). Realizes UJ-1.

**Consequences (testable):**
- Given a well-formed CSV with date, amount, and category columns, the script parses every data row into an in-memory expense record without error.
- Given a CSV missing a required column or with an unparseable row, the script reports a clear error identifying the problem row/column rather than failing silently or crashing uninformatively.

**Out of Scope:**
- Reading from any source other than a local CSV file (no database, no API, no multiple-file merge).

### 4.2 Monthly Category Summary
**Description:** The script groups parsed expenses by month and category, sums the amounts within each group, and outputs the result as a summary report. Realizes UJ-1.

**Functional Requirements:**

#### FR-2: Compute per-category monthly totals
The system can group all parsed expenses by calendar month and category, and compute the sum of amounts for each (month, category) pair. Realizes UJ-1.

**Consequences (testable):**
- For a given month, the sum of all category totals equals the sum of all expense amounts in that month (no expenses dropped or double-counted).
- Months with zero expenses in a category simply do not appear for that category (no fabricated zero rows required).

#### FR-3: Output the summary report
The user can view the computed summary in a readable form after running the script — printed to the terminal and/or written to an output file. Realizes UJ-1.

**Consequences (testable):**
- Running the script against a valid input CSV produces a summary output (stdout and/or file) showing, per month, each category and its total.
- The output is legible as plain text/console output without requiring a separate viewer application. [ASSUMPTION: exact output format — plain text table vs. CSV vs. Markdown — left to implementation; brief only specifies "monthly summary report (total per category)".]

**Notes:** *(open question)* Exact output format and destination (stdout vs. file, and file format) are unspecified in the brief — see Open Questions.

## 5. Non-Goals (Explicit)
- Not a multi-user or shared tool — single developer, personal use only.
- Not building any budget tracking, forecasting, or alerting on top of the totals.
- Not building a GUI or web interface — CLI only.
- Not addressing compliance, data residency, or audit requirements — explicitly out of scope per the brief ("no compliance concerns").
- Not building CSV ingestion from multiple/varying source formats — one expected input shape.

## 6. MVP Scope

### 6.1 In Scope
- Parse a single expenses CSV file (date, amount, category columns).
- Compute total spend per category per month.
- Output the summary (console and/or a simple output file).
- Basic error handling for malformed input.

### 6.2 Out of Scope for MVP
- Multiple input files / merging across sources.
- Configurable category taxonomies or category re-mapping.
- Any persistence, database, or historical trend tracking across runs.
- Packaging/distribution beyond a runnable local script.

## 7. Success Metrics
Success: the builder actually runs this monthly instead of tallying expenses by hand, and does not abandon it after the first use. No quantitative targets — hobby-tier, single user. [ASSUMPTION: no formal metrics tracking implied; this is a qualitative bar appropriate to a solo hobby tool.]

## 8. Open Questions
1. What are the exact expected CSV column names/order for date, amount, and category — fixed schema or auto-detected/configurable?
2. What output format is preferred — plain console table, CSV, or Markdown — and should it write to a file by default or only print to stdout?
3. How should the script handle multi-currency or non-numeric amount fields, if they ever occur (brief implies single-currency, not stated explicitly)?

## 9. Assumptions Index
- §0 — No additional context/inputs beyond the brief exist for this run.
- §2.3 — UJ-1 uses the "lighter" scope dial (single-sentence journey) appropriate for a solo hobby CLI.
- §4.1 — Input CSV has a header row identifying date/amount/category columns; exact column handling left to implementation.
- §4.2 (FR-3) — Output format (plain text vs. CSV vs. Markdown) is left to implementation, not specified by the brief.
- §7 — No formal/quantitative success metrics; qualitative bar only, consistent with hobby-tier stakes.
