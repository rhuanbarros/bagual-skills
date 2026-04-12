# Story Processor

**Goal:** Process a single story through the full pipeline: create-story → dev-story → code-review correction loop → mark done → update history → git commit.

**Your Role:** Isolated story execution agent. You receive one story's key and all paths as inputs, do all work for that story, persist results to disk, and return success or failure.
- You spawn sub-skill agents (create-story, dev-story, code-review) as isolated subagents
- You write all state changes to disk (sprint-status.yaml, story file, projects-history.md)
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

Derived paths:
- `{story_file}` = `{implementation_artifacts}/{story_key}.md`
- `{projects_history}` = `{project_root}/projects-history.md`
- `{deferred_findings_file}` = `{implementation_artifacts}/epic-{epic_num}-deferred-findings.md`

---

## EXECUTION

<workflow>

  <!-- ==================== SUB-STEP A: Create Story ==================== -->
  <step name="A" goal="Create story definition if in backlog">
    <check if="{story_status} == 'backlog'">
      <output>[Step A] Creating story definition for {story_id}...</output>

      <action>Spawn an Agent subagent with this prompt:
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

    <action>Spawn an Agent subagent with this prompt:
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
  <step name="C" goal="Code review with up to 2 correction iterations">
    <action>Set {review_iteration} = 0</action>
    <action>Set {review_passed} = false</action>
    <action>Set {spec_lessons} = empty list</action>
    <action>Set {queued_findings} = empty list</action>

    <loop while="{review_iteration} less than 2 AND {review_passed} == false">
      <action>Increment {review_iteration} by 1</action>
      <output>[Step C] Code review iteration {review_iteration}/2 for {story_key}...</output>

      <action>Spawn an Agent subagent with this prompt:
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

        <action>Spawn an Agent subagent with this prompt:
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
            Review iteration: {review_iteration}/5
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

    <action>Stage all changed and new files relevant to this story (implementation files, story file, sprint-status.yaml, projects-history.md). Avoid staging sensitive files (.env, credentials).</action>
    <action>Run: git commit using a HEREDOC:
      feat: implement {story_key} - {one_line_summary_of_story}

      Co-Authored-By: Claude Opus 4.6 (1M context) &lt;noreply@anthropic.com&gt;
    </action>

    <check if="git commit failed (e.g., pre-commit hook)">
      <output>WARNING: Git commit failed for {story_key}. Changes saved but not committed. Continuing...</output>
    </check>

    <output>
      ============================================================
      STORY {story_key} COMPLETE
      ============================================================
    </output>
  </step>

</workflow>
