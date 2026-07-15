# Story Processor

**Goal:** Process a single story through the full pipeline: create-story → dev-story → code-review correction loop → mark done → update history → Ledger gravação → git commit → Ticket gravação.

**Your Role:** Isolated story execution agent. You receive one story's key and all paths as inputs, do all work for that story, persist results to disk, and return success or failure.
- You spawn sub-skill agents (create-story, dev-story, code-review) as isolated subagents, each pinned to `model: sonnet` explicitly (Story E6.5, PRD 03 FR-12 — you, the Orchestrator, keep whatever model you were invoked with)
- You write all state changes to disk (sprint-status.yaml, story file, projects-history.md, Ledger entries under `wiki/ledger/`, and a Ticket's `## Fechamento` when the epic traces back to one — Story E6.6, PRD 03 FR-13)
- You do NOT communicate with the parent orchestrator — your result is implicit in the disk state

---

## INPUTS

You receive these values from the orchestrator:

- `{story_key}` — full story key, e.g. "1-8-text-message-handler"
- `{story_id}` — numeric prefix only, e.g. "1-8"
- `{story_status}` — current status in sprint-status.yaml (backlog / in-progress / review)
- `{config_path}` — path to `_bmad/bmm/config.yaml`
- `{implementation_artifacts}` — path to the artifacts directory
- `{sprint_status}` — path to sprint-status.yaml
- `{date}` — current date string
- `{project_root}` — root directory of the project
- `{epic_num}` — epic number (e.g. "2"), used for deferred findings file
- `{fast_mode}` — if true, skip code review step C (default: true)

Derived paths:
- `{story_file}` = `{implementation_artifacts}/{story_key}.md`
- `{projects_history}` = `{project_root}/_bmad-output/projects-history.md`
- `{deferred_findings_file}` = `{implementation_artifacts}/epic-{epic_num}-deferred-findings.md`
- `{anti_patterns_file}` = `{project_root}/_bmad-output/anti-patterns.md`
- `{decisions_file}` = `{project_root}/_bmad-output/decisions.md`
- `{product_decisions_file}` = `{project_root}/_bmad-output/product-decisions.md`
- `{notes_file}` = `{project_root}/_bmad-output/notes.md`

---

## EXECUTION

<workflow>

  <!-- ==================== PRE-STEP 0: Load knowledge files ==================== -->
  <step name="0" goal="Load project knowledge files for context continuity across compactions">
    <action>NOTE (Epic E17): these 4 files are FROZEN/archived legacy history — migrated to the
    Wiki (`wiki/` — `ledger/` + `nota-operacional/`), no new knowledge is written
    to them (see Step D.5 below). Live knowledge is grep'd from the Wiki by the create-story/
    quick-dev grounding tomls at spec-time, not loaded here. This read stays only as a
    best-effort legacy-context safety net across compactions; do not treat it as the live
    source.</action>
    <action>Read all four knowledge files before doing anything else:
      - {anti_patterns_file} — code patterns to avoid in this project
      - {decisions_file} — technical decisions already made (do not undo without context)
      - {product_decisions_file} — product behavior decisions (do not revert without explicit decision)
      - {notes_file} — operational knowledge, system gotchas, how parts interact
    If any file does not exist, skip it silently.</action>
    <output>[Step 0] Project knowledge loaded (legacy, frozen — Epic E17). Starting story {story_key}.</output>
  </step>

  <!-- ==================== SUB-STEP A: Create Story ==================== -->
  <step name="A" goal="Create story definition if in backlog">
    <check if="{story_status} == 'backlog'">
      <output>[Step A] Creating story definition for {story_id}...</output>

      <action>Spawn an Agent subagent using the Agent tool's `model` parameter set explicitly to `sonnet` (Story E6.5, PRD 03 FR-12 — executors run Sonnet; the Orchestrator itself stays on the model it was invoked with, typically Opus. Do NOT omit this param and let the subagent inherit the parent's model.) with this prompt:
        "Run the skill /bmad-create-story with args: {story_id} yolo
         This is running inside an automated pipeline. Auto-approve all checkpoints and prompts.
         Do not ask for user input — proceed automatically with sensible defaults."
      </action>

      <check if="Agent completed successfully">
        <action>Verify {story_file} now exists by attempting to read it</action>
        <check if="story file does not exist">
          <output>
            STORY PROCESSOR HALTED at Step A: story file was not created.
            Story: {story_key}
            Expected file: {story_file}
          </output>
          <action>HALT and return failure</action>
        </check>
        <output>[Step A] Story created successfully.</output>
      </check>

      <check if="Agent failed">
        <output>
          STORY PROCESSOR HALTED at Step A (Create Story).
          Story: {story_key}
          Error: {error_description}
        </output>
        <action>HALT and return failure</action>
      </check>
    </check>

    <check if="{story_status} != 'backlog'">
      <output>[Step A] Skipped — story already created (status: {story_status})</output>
    </check>
  </step>

  <!-- ==================== SUB-STEP B: Develop Story ==================== -->
  <step name="B" goal="Implement the story">
    <output>[Step B] Implementing story {story_key}...</output>

    <action>Spawn an Agent subagent using the Agent tool's `model` parameter set explicitly to `sonnet` (Story E6.5, PRD 03 FR-12 — executors run Sonnet; do NOT let this subagent inherit the parent Orchestrator's model) with this prompt:
      "Run the skill /bmad-dev-story with args: {story_file} yolo
       This is running inside an automated pipeline. Auto-approve all checkpoints and prompts.
       Do not ask for user input — proceed automatically.
       Implement all tasks until the story is complete."
    </action>

    <check if="Agent failed or dev-story HALTed">
      <output>
        STORY PROCESSOR HALTED at Step B (Dev Story).
        Story: {story_key}
        Error: {error_description}
      </output>
      <action>HALT and return failure</action>
    </check>

    <output>[Step B] Story implementation complete.</output>
  </step>

  <!-- ==================== SUB-STEP C: Code Review Correction Loop ==================== -->
  <step name="C" goal="Code review with up to 2 correction iterations (skipped in fast mode)">
    <check if="{fast_mode} == true">
      <output>[Step C] Skipped — fast mode active. No code review for {story_key}.</output>
      <action>GOTO step D</action>
    </check>

    <action>Set {review_iteration} = 0</action>
    <action>Set {review_passed} = false</action>
    <action>Set {spec_lessons} = empty list</action>
    <action>Set {queued_findings} = empty list</action>

    <loop while="{review_iteration} less than 2 AND {review_passed} == false">
      <action>Increment {review_iteration} by 1</action>
      <output>[Step C] Code review iteration {review_iteration}/2 for {story_key}...</output>

      <action>Spawn an Agent subagent using the Agent tool's `model` parameter set explicitly to `sonnet` (Story E6.5, PRD 03 FR-12 — executors run Sonnet; do NOT let this subagent inherit the parent Orchestrator's model) with this prompt:
        "Run the skill /bmad-code-review with args: uncommitted changes for story {story_key}, spec file at {story_file} yolo
         This is running inside an automated pipeline. Auto-approve all checkpoints.
         Review mode: uncommitted changes (staged + unstaged).
         Spec file: {story_file}
         Auto-confirm all HALT checkpoints and proceed automatically.

         IMPORTANT: After presenting your findings, provide a structured summary at the end with this exact format:

         ## Pipeline Review Summary
         - patch_count: [number of patch/fixable findings]
         - intent_gap_count: [number of intent gap findings]
         - bad_spec_count: [number of bad spec findings]
         - defer_count: [number of defer/pre-existing findings]
         - clean: [true if zero actionable findings, false otherwise]

         Then list each finding as:
         ### Finding [N]
         - category: [patch|intent_gap|bad_spec|defer]
         - severity: [high|medium|low]
         - title: [short title]
         - detail: [description of the issue]
         - location: [file:line or file]
        "
      </action>

      <action>Parse the Agent's output to extract:
        - patch_count, intent_gap_count, bad_spec_count, defer_count
        - Whether the review is "clean" (zero actionable findings)
        - Individual findings with their details
      </action>

      <!-- Case 1: Clean review -->
      <check if="review is clean OR only defer findings remain">
        <action>Set {review_passed} = true</action>
        <output>[Step C] Code review PASSED (iteration {review_iteration}). No actionable findings.</output>
      </check>

      <!-- Case 2: Spec-level issues — quick-fix spec, log lessons -->
      <check if="(intent_gap_count > 0 OR bad_spec_count > 0) AND {review_passed} == false">
        <output>[Step C] Found {intent_gap_count} intent gaps and {bad_spec_count} bad spec items. Fixing spec...</output>

        <action>Read {story_file} and apply minimal corrections to align the spec with the findings.
          Only update specific sections that are incorrect — do not rewrite the whole spec.
        </action>

        <action>Append to {spec_lessons}:
          {{for each intent_gap/bad_spec finding: "{title}: {detail}"}}
        </action>
      </check>

      <!-- Case 3: Actionable findings — bridge to dev-story for fixes -->
      <check if="(patch_count > 0 OR intent_gap_count > 0 OR bad_spec_count > 0) AND {review_passed} == false AND {review_iteration} less than 2">
        <output>[Step C] Found actionable issues. Writing review findings to story file and re-running dev-story...</output>

        <action>Read the current {story_file}</action>
        <action>Write/update the "Senior Developer Review (AI)" section in {story_file}:

          ## Senior Developer Review (AI)
          **Review Date:** {date}
          **Review Outcome:** Changes Requested
          **Iteration:** {review_iteration}

          ### Action Items
          {{for each actionable finding (patch, intent_gap, bad_spec): "- [ ] [{severity}] [{category}] {title}: {detail} ({location})"}}

        </action>

        <action>Also add/update a "Review Follow-ups (AI)" subsection under Tasks/Subtasks:
          ### Review Follow-ups (AI)
          {{for each actionable finding (patch, intent_gap, bad_spec): "- [ ] [AI-Review] [{severity}] {title}: {detail}"}}
        </action>

        <action>Save the story file</action>

        <action>Spawn an Agent subagent using the Agent tool's `model` parameter set explicitly to `sonnet` (Story E6.5, PRD 03 FR-12 — executors run Sonnet; do NOT let this subagent inherit the parent Orchestrator's model) with this prompt:
          "Run the skill /bmad-dev-story with args: {story_file} yolo
           This is running inside an automated pipeline. Auto-approve all checkpoints.
           This is a REVIEW CONTINUATION — the story file has a 'Senior Developer Review (AI)' section
           with action items that need to be fixed. Focus on resolving those review findings.
           Do not ask for user input — proceed automatically."
        </action>

        <check if="dev-story Agent failed">
          <output>
            STORY PROCESSOR HALTED at Step C (Fix Review Findings).
            Story: {story_key}
            Review iteration: {review_iteration}/2
            Error: {error_description}
          </output>
          <action>HALT and return failure</action>
        </check>

        <output>[Step C] Fixes applied. Re-running code review...</output>
      </check>
    </loop>

    <!-- Loop exhausted without passing — defer remaining findings to end-of-epic batch fix -->
    <check if="{review_iteration} >= 2 AND {review_passed} == false">
      <output>[Step C] Review loop limit reached (2/2). Deferring remaining findings to end-of-epic batch fix.</output>

      <action>Collect all unresolved actionable findings (patch, intent_gap, bad_spec) from the last review iteration into {queued_findings}</action>

      <action>Append to {deferred_findings_file} (create the file if it does not exist):

        ## Story: {story_key} — deferred after {review_iteration} review iteration(s) ({date})

        {{for each finding in {queued_findings}:
        ### Finding
        - category: {finding.category}
        - severity: {finding.severity}
        - title: {finding.title}
        - detail: {finding.detail}
        - location: {finding.location}
        }}
      </action>

      <output>[Step C] {queued_findings_count} finding(s) written to {deferred_findings_file}. Continuing story pipeline.</output>
    </check>
  </step>

  <!-- ==================== SUB-STEP D: Mark story as done ==================== -->
  <step name="D" goal="Update sprint-status.yaml ({story_key} → done, update last_updated) and set Status to done in {story_file}. Preserve all existing comments and structure.">
    <output>[Step D] Marking {story_key} as done...</output>

    <action>Read {sprint_status}. Find the entry for {story_key} and update its status to "done". Update the top-level `last_updated` field to {date}. Write the file back, preserving all existing comments, indentation, and structure.</action>

    <action>Read {story_file}. Find the `Status:` field and update its value to "done". Write the file back.</action>

    <output>[Step D] {story_key} marked as done in sprint-status.yaml and story file.</output>
  </step>

  <!-- ==================== SUB-STEP D.5: Record operational learnings to the Wiki (Epic E17) ==================== -->
  <step name="D.5" goal="Persist operational learnings from this story to the Wiki before git commit — the 4 legacy monolith files are FROZEN (Epic E17), no longer written to">
    <output>[Step D.5] Recording operational learnings from {story_key} to the Wiki...</output>

    <action>Review what was implemented and encountered during this story for operational knowledge that does NOT fit a typed Ledger entry — Step D.6 below already covers decisão-técnica/decisão-de-produto/decisão-de-arquitetura/regra/padrão/anti-pattern, so do not duplicate those categories here. Look specifically for: system behavior discoveries, operational gotchas, environment quirks, how parts interact. Only genuinely new insight not already documented in the Wiki.</action>

    <check if="at least one genuinely new operational insight found">
      <action>Write a new `tipo: nota-operacional` document under `wiki/nota-operacional/` (or append a dated section to an existing, topically matching one), following the front-matter/structure conventions in `wiki/document-types.md`. Use a `### {date} — {story_key}` header for traceability within the doc.</action>
      <output>[Step D.5] Wiki: nota-operacional criada/atualizada com aprendizado(s) de {story_key}.</output>
    </check>

    <check if="nothing new to record">
      <output>[Step D.5] Wiki: nenhum aprendizado operacional novo para {story_key}.</output>
    </check>

    <action>Do NOT append to {anti_patterns_file}, {decisions_file}, {product_decisions_file}, or {notes_file} — they are FROZEN/archived (Epic E17). Typed decisions/rules/patterns/anti-patterns are classified and emitted to the Ledger by Step D.6 below, not here.</action>
  </step>

  <!-- ==================== SUB-STEP D.6: Ledger gravação na conclusão (E6.6) ==================== -->
  <step name="D.6" goal="Emit Ledger entries for this story's completion, per on-complete-contract.md, generalizing E4.5's wiring beyond bmad-retrospective">
    <output>[Step D.6] Classifying Ledger-worthy items from {story_key}...</output>

    <action>This step is ADDITIVE to Step D.5 — D.5 keeps writing the 4 legacy knowledge files unchanged (still the source those files' consumers read today). D.6 generalizes the `on_complete` mechanism that Story E4.5 wired ONLY into `bmad-retrospective` (epic-level) down to this story-level completion point, per `wiki/ledger/on-complete-contract.md` §7 ("Skills de execução em geral... é o trabalho da Story E6.6"). This step REUSES that contract verbatim — it does not redefine schema, gramática, or criteria.</action>

    <action>Read {story_file} (Change Log, Dev Agent Record, Review Findings) and everything reviewed in Step D.5. Classify each candidate insight against on-complete-contract.md §2 (nem toda conclusão emite): only emit for an item that generalizes beyond this one story — a decision between alternatives that holds going forward (`decisão-técnica`/`decisão-de-arquitetura`), a product-visible behavior decision (`decisão-de-produto`), an actionable/verifiable convention (`regra`), a repeated-≥2x consolidatable way of doing something (`padrão`), or a recurring gotcha with a known fix (`anti-pattern`). When in doubt, do NOT emit — same strict default as the contract (§2: "o custo de perder uma lição pontual é menor que o custo de poluir o Ledger").</action>

    <check if="at least one item classified Ledger-worthy">
      <action>For each item, write a new file per on-complete-contract.md §3: classify `tipo` (one of the 6 slugs), full front-matter (`tipo`, `estado: candidata` — always `candidata`, never `ativa`, per §4 — `causa-da-morte: null`, `contador-de-utilidade: 0`, `areas: [...]` best-effort from this story's touched features, `reverte: null`, `created`/`updated` = {date}; `anti-pattern` also gets `selo` 🟢/🟡/🔴 + `automatizado: false`), and the full MADR body (`## Contexto`, `## Decisão`, `## Alternativas consideradas e rejeitadas` — never omit even if no real alternative was debated, state so plainly — `## Consequências`; `regra` also gets `## Enforcement`). Write to `wiki/ledger/<tipo-slug-ascii>/<slug-descritivo>.md` (mapping table in the contract §3.4). On filename collision, append a numeric suffix (`-2`, `-3`, ...) — never overwrite (§3.5). Use the same atomic write primitive (temp + flush + fsync + rename) as `wiki/ledger/scripts/transition_ledger_entry.py`'s `write_atomic()`.</action>

      <action>Run: `python3 wiki/ledger/scripts/validate_ledger.py --ledger-root wiki/ledger --json` and confirm each entry just written does NOT appear in `violations`. If one does, this step is that entry's own author in the same execution (contract §5) — fix that specific entry's front-matter/body and re-run; never touch other authors' pre-existing violations.</action>

      <output>[Step D.6] Ledger: {N} entrada(s) emitida(s) (estado: candidata) para {story_key}: {{for each: "- {tipo} candidata: {path}"}}</output>
    </check>

    <check if="zero items classified Ledger-worthy">
      <output>[Step D.6] Ledger: nenhuma entrada emitida para {story_key} (nenhum item classificado Ledger-worthy — só execução, sem generalização nova).</output>
    </check>

    <action>CRITICAL for auditability (PRD 03 FR-13, "conclusão sem gravação é estado incompleto detectável"): this step's output line above (with an explicit count, even zero) MUST be present in the pipeline's run log for {story_key}. A story completion with NO Step D.6 output line at all (not even the zero-count line) is itself the detectable incomplete-conclusion signal this FR requires — never silently skip printing it.</action>
  </step>

  <!-- ==================== SUB-STEP E: Update projects-history.md ==================== -->
  <step name="E" goal="Append a summary entry to {projects_history}">
    <output>[Step E] Updating projects history...</output>

    <action>Read {story_file} and extract: title, what was implemented (from Change Log / Dev Agent Record), key technical decisions, files changed, lessons learned, review findings addressed, and any spec issues from {spec_lessons}.</action>

    <action>Determine area tag (FRONTEND / BACKEND / INFRA / FULLSTACK) based on story content.</action>

    <action>Append entry:
      ## ({AREA_TAG}) {date} - {story_title}
      - Summary of implementation
      - Key decisions, lessons, spec issues (if any)
    </action>
  </step>

  <!-- ==================== SUB-STEP F: Git commit ==================== -->
  <step name="F" goal="Commit all changes for this story">
    <output>[Step F] Committing changes for {story_key}...</output>

    <action>Stage all changed and new files relevant to this story (implementation files, story file, sprint-status.yaml, and any knowledge written in step D.5: the new `wiki/nota-operacional/*.md` doc + `projects-history.md`, plus any Ledger entries written in step D.6 under `wiki/ledger/`). Note (Epic E17): the 4 monoliths `anti-patterns/decisions/product-decisions/notes.md` are FROZEN/archived — D.5 no longer writes them, so they are not staged here. Avoid staging sensitive files (.env, credentials).</action>
    <action>Run: git commit using a HEREDOC:
      feat: implement {story_key} - {one_line_summary_of_story}

      Co-Authored-By: Claude Opus 4.6 (1M context) &lt;noreply@anthropic.com&gt;
    </action>

    <check if="git commit failed (e.g., pre-commit hook)">
      <output>WARNING: Git commit failed for {story_key}. Changes saved but not committed. Continuing...</output>
    </check>

    <check if="git commit succeeded">
      <action>Run: `git rev-parse HEAD` and record the resulting hash as {story_commit_hash} — this is what Step F.5 below writes to the Ticket's `## Fechamento`, when applicable.</action>
    </check>

    <output>
      ============================================================
      STORY {story_key} COMPLETE
      ============================================================
    </output>
  </step>

  <!-- ==================== SUB-STEP F.5: Ticket gravação na conclusão (E6.6) ==================== -->
  <step name="F.5" goal="If this epic traces back to a bagual-tickets Ticket, record this story's commit hash in that Ticket's ## Fechamento — non-blocking, per E5.4's contract">
    <check if="{story_commit_hash} is not set (commit failed in Step F)">
      <output>[Step F.5] Skipped — no commit hash produced in Step F (commit failed). Nothing to record.</output>
      <action>GOTO end of step</action>
    </check>

    <action>Search {sprint_status} for the comment convention already used by this project's product epics (e.g. epic-38/39/40): a line matching `origem: (TCK-[\w-]+)` (one or more ticket ids, possibly comma/`+`-separated) in the comment block immediately above the `epic-{epic_num}:` entry. This is a best-effort, read-only lookup — no new field is invented; it reuses the exact convention already present in `_bmad-output/implementation-artifacts/sprint-status.yaml`.</action>

    <check if="no origem: TCK-* found for this epic">
      <output>[Step F.5] Ticket: nenhum Ticket de origem rastreável para epic {epic_num} — nada a gravar. (Não é um erro: nem toda epic nasce de um Ticket, PRD 02 FR-4 não exige.)</output>
    </check>

    <check if="one or more origem: TCK-* ids found">
      <action>For each `TCK-{id}` found, locate `project_controll/tickets/TCK-{id}.md`. If the file exists, read its `## Fechamento` section (create it if absent, per the template in `.claude/skills/bagual-tickets/SKILL.md` § Armazenamento). Append {story_commit_hash} as a new line UNLESS that exact hash already appears in the section (idempotent — do not duplicate across re-runs or across multiple stories of the same epic that share the same Ticket). Format: one hash per line, simple list, no per-commit summary — reuse E5.4's exact format, do not redefine it.</action>
      <action>This write is non-blocking (E5.4's contract, PRD 02 FR-4): if the Ticket file does not exist, is malformed, or the write fails for any reason, log a WARNING and continue — never HALT the story pipeline over a Ticket write.</action>
      <output>[Step F.5] Ticket: hash {story_commit_hash} gravado em ## Fechamento de {{each TCK-id found}}.</output>
    </check>
  </step>

</workflow>
