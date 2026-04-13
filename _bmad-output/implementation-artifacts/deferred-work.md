# Deferred Work

## From: Eval Scenario Quality Infrastructure (2026-04-13)

- **Coverage Matrix extensibility**: The 4 axes (happy-path, error-path, adversarial, information-gap) are fixed in the skill. Agents with additional relevant dimensions (auth-boundary paths, latency-sensitive paths, multi-tenant isolation) have no way to surface coverage gaps. Future enhancement: allow users to add custom axes.

- **Framework table version constraints**: The injection patterns reference table lists frameworks without version constraints. LangGraph pre/post-0.2 state schema changes affect what's hidden from the LLM. Future enhancement: add version notes per framework row.
