# Flow: dev→staging promotion (Story E21.4)

When the owner asks to **promote `dev` → `staging`** (e.g., "merge dev into staging", "promote to
staging", "push what's ready to staging"), do NOT do a blind merge. Run this flow (QA validation
is out of scope for this kit — install your own gate if you want to run it after the merge, on
staging):

1. **Delta.** Compute what is being promoted: `git diff --stat staging..dev`. Keep the summary of
   touched features/screens for the report.
2. **Byte-identical promotion check — ALWAYS here, before doing any merge/deploy work.** Run
   `git rev-list --count staging..dev` (commits present in `dev` and absent from `staging` — same
   direction as step 1's delta).
   - **If the count is `0` (byte-identical):** there is nothing new to promote — `staging`
     already contains everything `dev` has. **Report this in the Briefing** ("promotion
     requested, but `dev` and `staging` are already byte-identical — nothing to merge/deploy") and
     **stop here**, without touching `git merge`/deploy. Never do an empty merge/deploy just to
     "fulfill the request."
   - **If the count is non-zero:** proceed to step 3 normally.
3. **Merge `dev` → `staging`** (free operation, staging isn't Production): `git checkout staging`,
   `git merge dev` (resolve conflicts or stop and report if any), `git push origin staging`.
4. **Deploy staging:** `make deploy-frontend-staging` + `make deploy-backend-staging` (free —
   already applies `migrate-staging`). Go back to `dev` (`git checkout dev`) when done.
5. **Report in the Briefing** what was promoted — and remind that promotion to Production
   (`staging → main`) is exclusive to the owner, with express authorization (see the critical
   Production rule).

> `staging → main` (Production) promotion is **not** part of this flow — it's always a separate
> action, by the owner, with express and specific authorization (see "🚨 CRITICAL RULE — Deploy …
> Production" in AGENTS.md). This flow delivers a validated staging; the go-ahead for Production is a
> different moment.
