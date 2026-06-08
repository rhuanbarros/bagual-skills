---
alwaysApply: true
---

## What this project is

Production-ready fullstack SaaS product template. The goal is to be sold as a codebase for buyers who adapt it to their own product. Includes AI photo generation, multi-model chat (SSE streaming), credit system (atomic RPC), Stripe billing, admin dashboard, and E2E test suite. The priority is professional code, separation of concerns, and maximum feature isolation within their own folders.

---

## 🔴 RULE ZERO — Mandatory knowledge file updates

> **This file lives in the System Prompt of ALL Copilot agents.**
> The knowledge accumulated here is the project's memory across sessions.
> If not updated, the next agent works blind.

### 📝 OBLIGATION: At the end of EVERY task (no exceptions)

Before considering any task complete, **read and update** the 4 knowledge files if anything relevant was learned:

| File | When to update |
|---|---|
| `_bmad-output/anti-patterns.md` | Code that went wrong, problematic pattern, risk identified in review |
| `_bmad-output/decisions.md` | Technical or architectural decision made during implementation |
| `_bmad-output/product-decisions.md` | Change in how the product behaves (stakeholder, team, UX) |
| `_bmad-output/notes.md` | Anything else learned (operational gotcha, environment constraint, how parts interact) |

### ⚠️ Pre-save before context compaction

If there is risk of context loss (compaction, agent switch, new session), **update the files BEFORE** the transition — not after. Lost context = permanently lost knowledge.

### 🔄 Standard workflow

```
1. Read the 4 knowledge files (input context)
2. Execute the task
3. Update the 4 knowledge files (output context)
4. Commit (if applicable)
```

---

## BMad artifact structure

```
_bmad-output/
├── projects-history.md          ← Timeline of completed stories
├── anti-patterns.md             ← Patterns to AVOID (mandatory reading — ⚠️ update at end of every task)
├── decisions.md                 ← Technical implementation decisions (do not undo — ⚠️ update at end of every task)
├── product-decisions.md         ← Decisions about product behavior (do not revert without explicit decision — ⚠️ update at end of every task)
├── notes.md                     ← Operational knowledge and insights accumulated across sessions (⚠️ update at end of every task)
├── planning-artifacts/          ← PRD, architecture, epics, UX design
└── implementation-artifacts/    ← Story files + sprint tracking
    ├── sprint-status.yaml       ← ONLY exists during an active sprint — otherwise absent
    └── N-M-story-name.md
```

---

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | React 19 + TypeScript + Vite 7 (SSR + prerender) |
| UI | shadcn/ui + Radix UI + Tailwind CSS v4 |
| State / Routing | Zustand 5 + React Router v7 |
| Backend | FastAPI + Python 3.12 (uv) |
| AI | Google Gemini (genai) + Claude API (Anthropic) |
| Payments | Stripe |
| Database / Auth / Storage | Supabase (PostgreSQL + Auth + Storage + Realtime) |
| Observability | Langfuse |
| Frontend Tests | Vitest 4 + Playwright 1.59 + Pact |
| Backend Tests | pytest + asyncio |


---

## Critical rules — read before implementing

### ❌ Layer separation must never be violated

**Frontend**: `repositories/` → `services/` → `hooks/` → `pages/components/`. Each layer has a single responsibility — repository only talks to Supabase, pages never call Supabase directly.

**Backend**: `infra/` → `repositories/` → `domain/` → `agents/` → `api/`. Agents call only domain services. Infra provides only primitive operations, zero business logic.

### ❌ Storage buckets must ALWAYS be created via SQL migrations

Never create buckets manually in the Supabase Dashboard or in application code. Every new bucket requires a migration in `supabase/migrations/` with `insert into storage.buckets ... on conflict (id) do nothing` and all necessary RLS policies.

### ✅ When implementing anything: use BMad skills and read the knowledge files
Do not implement code directly. Use `/bmad-quick-dev` for ad-hoc changes, `/bmad-dev-story` for stories, `/bagual-bmad-implement-quick-epic` for complete epics. The skills automatically load `anti-patterns.md`, `decisions.md`, `product-decisions.md`, and `notes.md` as context.

---

## How to run the stack locally

```bash
# Backend — FastAPI (http://localhost:8000)
cd backend
uv run uvicorn api.index:app --reload --reload-exclude tests

# Frontend — React (http://localhost:5173)
cd frontend
npm run dev
```

> There is no local Supabase — the project exclusively uses remote Supabase (hosted project). There is no `supabase start` or `config.toml`; migrations are applied via `npx supabase db push` against the remote project.

Backend integration tests use the remote Supabase (credentials via `TEST_SUPABASE_URL`/`TEST_SUPABASE_KEY` in `.env.test`), not a local instance.

---

## Available skills (BMad)

Installed in `.claude/skills/`. Requires Claude Code.

| Skill | When to use |
|---|---|
| `/bagual-bmad-implement-quick-epic {N}` | Implement a complete epic in fast mode (no code review — default) |
| `/bagual-bmad-implement-quick-epic {N} full` | Implement epic with code review loop (up to 2 iterations per story) |
| `/bmad-quick-dev` | Ad-hoc change (bug fix, one-off feature, refactor) |
| `/bmad-dev-story {story-file}` | Implement a specific story |
| `/bmad-code-review` | Review uncommitted code |
| `/bagual-test-pipeline high yolo` | Run full test suite with auto-fix |
| `/bmad-sprint-status` | View current sprint status **(only exists during an active sprint)** |
| `/bmad-create-story {N-M}` | Create a story file from epics |

### 🏃 About sprint-status and sprint-status.yaml

`sprint-status.yaml` and `/bmad-sprint-status` **only exist during an active sprint** — when there are stories in progress or planned. If no sprint is running, the file will be absent and the command will have no effect. Do not create `sprint-status.yaml` artificially; it is generated by the sprint planning flow.

---
