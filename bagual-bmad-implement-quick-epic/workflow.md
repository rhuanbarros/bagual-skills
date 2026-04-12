# Epic Pipeline Workflow

**Goal:** Orchestrate an entire epic through the create-story -> dev-story -> code-review pipeline automatically, processing each story sequentially until the epic is complete.

**Your Role:** Thin pipeline orchestrator. You build the story queue, spawn one isolated Agent per story, verify completion, and run the retrospective.
- You do NOT implement code, run sub-skills, or manage story state yourself
- You DO read sprint-status.yaml to build the queue and verify results after each story
- You DO spawn one isolated Agent per story using story-processor.md
- Communicate all responses in {communication_language}

---

## RULES

- Process stories ONE AT A TIME, in order. Never parallelize.
- Each story MUST run in its own Agent subagent (story-processor.md) for full context isolation.
- If any story agent fails, HALT the entire pipeline immediately and report which story failed and why.
- Never modify sprint-status.yaml yourself — story-processor agents handle all story-level writes.

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
- `story_processor` = `.claude/skills/bagual-bmad-implement-quick-epic/story-processor.md`
- `deferred_findings_file` = `{implementation_artifacts}/epic-{epic_num}-deferred-findings.md`

### Input Validation

Parse the user-provided epic number from the invocation arguments.
- Extract `{epic_num}` from the argument (e.g., "2" from "/bagual-bmad-implement-quick-epic 2")
- If no epic number provided:
  - Read the FULL `{sprint_status}` file
  - Find the first epic key (pattern: `epic-N`) whose status is NOT "done"
  - If found, set `{epic_num}` to that epic's number and output: "No epic number provided. Auto-selected epic {epic_num} (first not done)."
  - If none found, HALT: "All epics are done. Nothing to process."

---

## EXECUTION

<workflow>
  <critical>Process stories ONE AT A TIME in order. Do not parallelize.</critical>
  <critical>Each story MUST run in its own Agent subagent for full context isolation. Do not process stories inline.</critical>
  <critical>If any story agent fails, HALT immediately.</critical>

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
      <action>GOTO step 3 (epic completion check)</action>
    </check>

    <output>
      EPIC {epic_num} PIPELINE STARTING

      Stories to process ({story_queue_length} remaining):
      {{for each story in story_queue: "- {story_key}: {story_status}"}}

      Processing will begin with: {first_story_key}
    </output>
  </step>

  <step n="2" goal="Process each story via isolated story-processor agent">
    <critical>Each story runs in its own Agent subagent. Do not implement stories inline.</critical>

    <action>For each story in {story_queue}:
      Set {current_story_key} = the story's full key (e.g., "1-8-text-message-handler")
      Set {current_story_id} = numeric prefix only (e.g., "1-8")
      Set {current_story_status} = the story's current status
    </action>

    <output>
      ============================================================
      SPAWNING STORY AGENT: {current_story_key} (status: {current_story_status})
      ============================================================
    </output>

    <action>Spawn an Agent subagent with this prompt:
      "You are a story processor agent. Read and follow ALL instructions in the file: {story_processor}

      Input values:
      - story_key: {current_story_key}
      - story_id: {current_story_id}
      - story_status: {current_story_status}
      - config_path: {project-root}/_bmad/bmm/config.yaml
      - implementation_artifacts: {implementation_artifacts}
      - sprint_status: {sprint_status}
      - date: {date}
      - project_root: {project-root}
      - epic_num: {epic_num}

      This is running inside an automated pipeline. Auto-approve all checkpoints.
      Do not ask for user input — proceed automatically."
    </action>

    <check if="Agent returned failure or HALTED">
      <output>
        PIPELINE HALTED: Story agent failed for {current_story_key}.
        Error: {error_description}

        Manual intervention required. After fixing, re-run: /bagual-bmad-implement-epic {epic_num}
      </output>
      <action>HALT</action>
    </check>

    <action>Re-read {sprint_status} to verify {current_story_key} is now "done"</action>

    <check if="{current_story_key} status is NOT 'done' in sprint_status">
      <output>
        PIPELINE HALTED: Story agent completed but {current_story_key} was not marked done in sprint-status.yaml.
        Check the story agent output for errors.

        Manual intervention required. After fixing, re-run: /bagual-bmad-implement-epic {epic_num}
      </output>
      <action>HALT</action>
    </check>

    <output>
      ============================================================
      STORY {current_story_key} COMPLETE — moving to next story
      ============================================================
    </output>

    <action>Move to next story in {story_queue}. Repeat this step for each remaining story.</action>
  </step>

  <step n="3" goal="Verify all stories are done before running retrospective">
    <action>Re-read {sprint_status} and verify ALL stories for epic {epic_num} are "done"</action>

    <check if="some stories are not done">
      <output>
        Epic {epic_num} pipeline finished processing available stories.
        Some stories remain incomplete (likely due to earlier interruption).
        Re-run /bagual-bmad-implement-epic {epic_num} after addressing any issues.
      </output>
      <action>HALT</action>
    </check>

    <output>All stories for epic {epic_num} are done. Checking for deferred findings...</output>
  </step>

  <step n="4" goal="Address deferred findings from review loops via bmad-quick-dev">
    <action>Check if {deferred_findings_file} exists and contains content</action>

    <check if="file does not exist or is empty">
      <output>[Step 4] No deferred findings. Skipping batch fix pass.</output>
    </check>

    <check if="file exists and has content">
      <output>[Step 4] Deferred findings found. Running bmad-quick-dev batch fix pass...</output>

      <action>Spawn an Agent subagent with this prompt:
        "Run the skill /bmad-quick-dev with the following intent:

        Address all deferred code review findings from epic {epic_num}. Read the findings file at {deferred_findings_file}. These are issues flagged during per-story review that were not resolved within the 2-iteration review limit.

        IMPORTANT: Re-validate each finding first before acting — some may already be resolved by later story implementations. Only fix confirmed active issues. Group related fixes across stories when possible.

        This is running inside an automated pipeline. Auto-approve all checkpoints.
        Do not ask for user input — proceed automatically."
      </action>

      <check if="Agent failed">
        <output>WARNING: Deferred findings batch fix failed. File preserved at {deferred_findings_file}. Continuing to retrospective.</output>
      </check>

      <check if="Agent succeeded">
        <action>Stage all files changed by the batch fix (avoid staging sensitive files like .env or credentials).</action>
        <action>Run: git commit using a HEREDOC:
          fix: epic-{epic_num} deferred review findings — batch fix pass

          Co-Authored-By: Claude Opus 4.6 (1M context) &lt;noreply@anthropic.com&gt;
        </action>
        <action>Delete {deferred_findings_file} to prevent stale findings from accumulating on re-runs.</action>
        <output>[Step 4] Deferred findings addressed, committed, and findings file cleaned up.</output>
      </check>
    </check>
  </step>

  <step n="5" goal="Run retrospective and mark epic done">
    <critical>The epic is NOT complete until the retrospective finishes. Do NOT mark epic as done before this step succeeds.</critical>

    <output>[Step 5] Running retrospective for epic {epic_num}...</output>

    <action>Spawn an Agent subagent with this prompt:
      "Run the skill /bmad-retrospective with args: epic {epic_num} yolo
       This is running inside an automated pipeline. Auto-approve all checkpoints and prompts.
       Do not ask for user input — proceed automatically."
    </action>

    <check if="Agent failed">
      <output>
        PIPELINE HALTED at Step 5 (Retrospective) for epic {epic_num}.
        Error: {error_description}
        All stories are done but the epic cannot be marked done without a completed retrospective.
        Run manually: /bmad-retrospective yolo
      </output>
      <action>HALT</action>
    </check>

    <output>[Step 5] Retrospective complete. Marking epic as done...</output>

    <action>Update {sprint_status}: set epic-{epic_num} and epic-{epic_num}-retrospective to done, update last_updated to current date. Preserve all existing comments and structure.</action>

    <action>Stage sprint-status.yaml and any retrospective artifacts. Avoid staging sensitive files.</action>
    <action>Run: git commit using a HEREDOC:
      docs: epic-{epic_num} retrospective — epic complete

      Co-Authored-By: Claude Opus 4.6 (1M context) &lt;noreply@anthropic.com&gt;
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
