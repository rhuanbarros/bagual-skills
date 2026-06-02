# Epic Pipeline Workflow

**Goal:** Orchestrate an entire epic through the create-story -> dev-story -> code-review pipeline automatically, processing each story sequentially until the epic is complete.

**Your Role:** Pipeline orchestrator. You coordinate sub-skills in sequence, manage the correction loop, handle failures, and track progress.
- You do NOT implement code yourself — you delegate to sub-skills via isolated subagents
- You DO manage state: reading sprint-status.yaml, updating it, committing changes
- You DO handle the correction loop logic for code review
- You DO bridge review findings into the story file for dev-story to pick up
- Communicate all responses in {communication_language}

---

## RULES

- Process stories ONE AT A TIME, in order. Never parallelize.
- Each sub-skill invocation (create-story, dev-story, code-review) MUST run in its own Agent subagent for context isolation.
- If any step fails, HALT the entire pipeline immediately and report which step failed and why.
- The code review correction loop runs a maximum of 5 iterations per story.
- Always append "yolo" to sub-skill args to enable auto-approve mode.

---

## INITIALIZATION

### Configuration Loading

Load config from `{project-root}/_bmad/bmm/config.yaml` and resolve:
- `project_name`, `user_name`
- `communication_language`, `document_output_language`
- `implementation_artifacts`
- `date` as system-generated current date

### Paths

- `sprint_status` = `{implementation_artifacts}/sprint-status.yaml`
- `projects_history` = `{project-root}/projects-history.md`

### Input Validation

Parse the user-provided epic number from the invocation arguments.
- Extract `{epic_num}` from the argument (e.g., "2" from "/bagual-bmad-implement-epic 2")
- If no epic number provided, HALT: "Please provide an epic number, e.g. /bagual-bmad-implement-epic 2"

---

## EXECUTION

<workflow>
  <critical>Process stories ONE AT A TIME in order. Do not parallelize.</critical>
  <critical>Each sub-skill MUST run in its own Agent subagent for context isolation.</critical>
  <critical>If any step fails, HALT the entire pipeline immediately.</critical>

  <step n="1" goal="Parse sprint status and build story queue">
    <action>Read {sprint_status} and parse the development_status section</action>

    <check if="epic-{epic_num} not found">
      <output>PIPELINE HALTED: Epic {epic_num} not found in sprint-status.yaml</output>
      <action>HALT</action>
    </check>

    <check if="epic-{epic_num} status is 'done'">
      <output>PIPELINE HALTED: Epic {epic_num} is already marked as done. Nothing to process.</output>
      <action>HALT</action>
    </check>

    <action>Collect ALL stories for this epic into an ordered list called {story_queue}:
      - Find all keys matching pattern: {epic_num}-*-* (e.g., 2-1-*, 2-2-*, etc.)
      - Exclude epic keys (epic-N) and retrospective keys (epic-N-retrospective)
      - Preserve the order they appear in the file (top to bottom)
      - Record each story's current status
    </action>

    <action>Filter {story_queue} to only stories that are NOT "done"</action>

    <check if="{story_queue} is empty">
      <output>All stories in epic {epic_num} are already done.</output>
      <action>GOTO epic completion check (step 3)</action>
    </check>

    <output>
      EPIC {epic_num} PIPELINE STARTING

      Stories to process ({story_queue_length} remaining):
      {{for each story in story_queue: "- {story_key}: {story_status}"}}

      Processing will begin with: {first_story_key} (status: {first_story_status})
    </output>
  </step>

  <step n="2" goal="Process each story in sequence">
    <critical>Process stories ONE AT A TIME in order. Do not parallelize.</critical>

    <action>For each story in {story_queue}, execute the following sub-steps.
      Set {current_story_key} to the current story's key (e.g., "2-3-invite-family-member-by-email").
      Set {current_story_id} to just the numeric prefix (e.g., "2-3").
      Set {current_story_status} to the current story's status.
      Set {story_file} = "{implementation_artifacts}/{current_story_key}.md"
    </action>

    <output>
      ============================================================
      PROCESSING STORY: {current_story_key} (status: {current_story_status})
      ============================================================
    </output>

    <!-- ==================== SUB-STEP A: Create Story ==================== -->
    <check if="{current_story_status} == 'backlog'">
      <output>[Step A] Creating story definition for {current_story_id}...</output>

      <action>Spawn an Agent subagent with this prompt:
        "Run the skill /bmad-create-story with args: {current_story_id} yolo
         This is running inside an automated pipeline. Auto-approve all checkpoints and prompts.
         Do not ask for user input — proceed automatically with sensible defaults."
      </action>

      <check if="Agent completed successfully">
        <action>Verify {story_file} now exists by reading it</action>
        <output>[Step A] Story created successfully.</output>
      </check>

      <check if="Agent failed or story file was not created">
        <output>
          PIPELINE HALTED at Step A (Create Story) for {current_story_key}.
          Error: {error_description}

          Manual intervention required. After fixing, re-run: /bagual-bmad-implement-epic {epic_num}
        </output>
        <action>HALT</action>
      </check>
    </check>

    <check if="{current_story_status} != 'backlog'">
      <output>[Step A] Skipped — story already created (status: {current_story_status})</output>
    </check>

    <!-- ==================== SUB-STEP B: Develop Story ==================== -->
    <output>[Step B] Implementing story {current_story_key}...</output>

    <action>Spawn an Agent subagent with this prompt:
      "Run the skill /bmad-dev-story with args: {story_file} yolo
       This is running inside an automated pipeline. Auto-approve all checkpoints and prompts.
       Do not ask for user input — proceed automatically.
       Implement all tasks until the story is complete."
    </action>

    <check if="Agent failed or dev-story HALTed">
      <output>
        PIPELINE HALTED at Step B (Dev Story) for {current_story_key}.
        Error: {error_description}

        Manual intervention required. After fixing, re-run: /bagual-bmad-implement-epic {epic_num}
      </output>
      <action>HALT</action>
    </check>

    <output>[Step B] Story implementation complete.</output>

    <!-- ==================== SUB-STEP C: Code Review Correction Loop ==================== -->
    <action>Set {review_iteration} = 0</action>
    <action>Set {review_passed} = false</action>
    <action>Set {spec_lessons} = empty list</action>

    <loop while="{review_iteration} less than 5 AND {review_passed} == false">
      <action>Increment {review_iteration} by 1</action>
      <output>[Step C] Code review iteration {review_iteration}/5 for {current_story_key}...</output>

      <action>Spawn an Agent subagent with this prompt:
        "Run the skill /bmad-code-review with args: uncommitted changes for story {current_story_key}, spec file at {story_file} yolo
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

      <!-- Case 1: Review is clean -->
      <check if="review is clean OR only defer findings remain">
        <action>Set {review_passed} = true</action>
        <output>[Step C] Code review PASSED (iteration {review_iteration}). No actionable findings.</output>
      </check>

      <!-- Case 2: Spec-level issues — quick-fix spec, log lessons -->
      <check if="(intent_gap_count > 0 OR bad_spec_count > 0) AND {review_passed} == false">
        <output>[Step C] Found {intent_gap_count} intent gaps and {bad_spec_count} bad spec items. Quick-fixing spec...</output>

        <action>Read {story_file} and apply minimal corrections to align the spec with the findings.
          Only update the specific sections that are incorrect — do not rewrite the whole spec.
        </action>

        <action>Append to {spec_lessons}:
          {{for each intent_gap/bad_spec finding: "{title}: {detail}"}}
        </action>
      </check>

      <!-- Case 3: Actionable findings — fix via dev-story -->
      <check if="(patch_count > 0 OR intent_gap_count > 0 OR bad_spec_count > 0) AND {review_passed} == false AND {review_iteration} less than 5">
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
            PIPELINE HALTED at Step C (Fix Review Findings) for {current_story_key}.
            Review iteration: {review_iteration}/5
            Error: {error_description}

            Manual intervention required. After fixing, re-run: /bagual-bmad-implement-epic {epic_num}
          </output>
          <action>HALT</action>
        </check>

        <output>[Step C] Fixes applied. Re-running code review...</output>
      </check>
    </loop>

    <!-- Case 4: Loop exhausted -->
    <check if="{review_iteration} >= 5 AND {review_passed} == false">
      <output>
        PIPELINE HALTED: Code review still failing after 5 iterations for {current_story_key}.

        The correction loop has been exhausted. Manual intervention required.
        Review the latest findings and fix manually, then re-run: /bagual-bmad-implement-epic {epic_num}
      </output>
      <action>HALT</action>
    </check>

    <!-- ==================== SUB-STEP D: Mark story as done ==================== -->
    <output>[Step D] Marking {current_story_key} as done...</output>

    <action>Read {sprint_status}. Find the entry for {current_story_key} and update its status to "done". Update the top-level `last_updated` field to {date}. Write the file back, preserving all existing comments, indentation, and structure.</action>

    <action>Read {story_file}. Find the `Status:` field and update its value to "done". Write the file back.</action>

    <output>[Step D] {current_story_key} marked as done.</output>

    <!-- ==================== SUB-STEP E: Update projects-history.md ==================== -->
    <output>[Step E] Updating projects history...</output>

    <action>Read {story_file} and extract: title, what was implemented (from Change Log / Dev Agent Record), key technical decisions, files changed, lessons learned, review findings addressed, and any spec issues from {spec_lessons}.</action>

    <action>Determine area tag (FRONTEND / BACKEND / INFRA / FULLSTACK) based on story content.</action>

    <action>Append entry to {projects_history}:
      ## ({AREA_TAG}) {date} - {story_title}
      - Summary of implementation
      - Key decisions, lessons, spec issues (if any)
    </action>

    <!-- ==================== SUB-STEP F: Git commit ==================== -->
    <output>[Step F] Committing changes for {current_story_key}...</output>

    <action>Stage all changed and new files relevant to this story (implementation files, story file, sprint-status.yaml, projects-history.md). Avoid staging sensitive files (.env, credentials).</action>
    <action>Run: git commit using a HEREDOC:
      feat: implement {current_story_key} — {one_line_summary_of_story}

      Co-Authored-By: Claude <noreply@anthropic.com>
    </action>

    <check if="git commit failed (e.g., pre-commit hook)">
      <output>WARNING: Git commit failed for {current_story_key}. Changes saved but not committed. Continuing...</output>
    </check>

    <output>
      ============================================================
      STORY {current_story_key} COMPLETE
      ============================================================
    </output>

    <action>Move to next story in {story_queue}. If more stories remain, repeat step 2 from the top.</action>
  </step>

  <step n="3" goal="Verify all stories are done before closing epic">
    <action>Re-read {sprint_status} and check if ALL stories for epic {epic_num} are now "done"</action>

    <check if="some stories are not done">
      <output>
        Epic {epic_num} pipeline finished processing available stories.
        Some stories remain incomplete (likely due to earlier interruption).
        Re-run /bagual-bmad-implement-epic {epic_num} after addressing any issues.
      </output>
      <action>HALT</action>
    </check>

    <output>All stories for epic {epic_num} are done. Running retrospective before closing epic...</output>
  </step>

  <step n="4" goal="Run retrospective — epic is NOT done until this completes">
    <critical>The epic is NOT complete until the retrospective finishes successfully. Do NOT mark the epic as done before this step succeeds.</critical>

    <output>[Step 4] Running retrospective for epic {epic_num}...</output>

    <action>Spawn an Agent subagent with this prompt:
      "Run the skill /bmad-retrospective with args: epic {epic_num} yolo
       This is running inside an automated pipeline. Auto-approve all checkpoints and prompts.
       Do not ask for user input — proceed automatically."
    </action>

    <check if="Agent failed">
      <output>
        PIPELINE HALTED at Step 4 (Retrospective) for epic {epic_num}.
        Error: {error_description}
        All stories are done, but the epic CANNOT be marked as done without a completed retrospective.
        Run manually: /bmad-retrospective yolo
      </output>
      <action>HALT</action>
    </check>

    <output>[Step 4] Retrospective complete. Marking epic as done...</output>

    <action>Update {sprint_status}: set epic-{epic_num} and epic-{epic_num}-retrospective to done, update last_updated to current date. Preserve all existing comments and structure.</action>

    <action>Stage sprint-status.yaml and any retrospective artifacts. Avoid staging sensitive files.</action>
    <action>Run: git commit using a HEREDOC:
      docs: epic-{epic_num} retrospective — epic complete

      Co-Authored-By: Claude <noreply@anthropic.com>
    </action>

    <output>
      ============================================================
      EPIC {epic_num} PIPELINE COMPLETE

      All stories implemented, reviewed, and committed.
      Retrospective completed and committed.
      Epic {epic_num} marked as done.
      ============================================================
    </output>
  </step>

</workflow>
