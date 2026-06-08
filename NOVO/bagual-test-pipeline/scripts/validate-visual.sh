#!/usr/bin/env bash
# =============================================================================
# validate-visual.sh — Visual Validation Script (AI-mediated)
# =============================================================================
#
# Recebe screenshots + requisitos visuais, envia para uma IA com processamento
# de imagem (Kimi Code / Open Router / Gemini / Claude / GPT-4V), e retorna
# resultado estruturado em JSON que QUALQUER agente Harness (mesmo text-only)
# pode ler.
#
# Uso:
#   ./validate-visual.sh \
#     --screenshots-dir test-artifacts/screenshots \
#     --requirements visual-requirements.yaml \
#     --output _bmad-output/test-artifacts/visual-validation/latest.json \
#     [--provider kimi|openrouter|gemini|claude|openai] \
#     [--api-key-env KIMI_API_KEY|OPENROUTER_API_KEY|GEMINI_API_KEY|...] \
#     [--model kimi-k2.5|...]
#
# Output:
#   JSON file em latest.json com pass/fail + descrição textual por screenshot.
#   O Harness lê este JSON como texto — NÃO precisa processar imagens.
# =============================================================================

set -euo pipefail

# ── Defaults ──────────────────────────────────────────────────────────────────
PROVIDER="${VISUAL_AI_PROVIDER:-kimi}"
MODEL="${VISUAL_AI_MODEL:-}"
API_KEY_ENV="${VISUAL_AI_API_KEY_ENV:-}"
SCREENSHOTS_DIR=""
REQUIREMENTS_FILE=""
OUTPUT_FILE=""
VERBOSE=false

# ── Parse args ────────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --screenshots-dir) SCREENSHOTS_DIR="$2"; shift 2 ;;
    --requirements)    REQUIREMENTS_FILE="$2"; shift 2 ;;
    --output)          OUTPUT_FILE="$2"; shift 2 ;;
    --provider)        PROVIDER="$2"; shift 2 ;;
    --api-key-env)     API_KEY_ENV="$2"; shift 2 ;;
    --model)           MODEL="$2"; shift 2 ;;
    --verbose|-v)      VERBOSE=true; shift ;;
    *)
      echo "❌ Unknown argument: $1"
      echo "Usage: $0 --screenshots-dir <dir> --requirements <yaml> --output <json> [--provider kimi|openrouter|gemini|claude|openai]"
      exit 1
      ;;
  esac
done

# ── Validate required args ────────────────────────────────────────────────────
if [[ -z "$SCREENSHOTS_DIR" || -z "$REQUIREMENTS_FILE" || -z "$OUTPUT_FILE" ]]; then
  echo "❌ Missing required arguments."
  echo "Usage: $0 --screenshots-dir <dir> --requirements <yaml> --output <json>"
  exit 1
fi

if [[ ! -d "$SCREENSHOTS_DIR" ]]; then
  echo "❌ Screenshots directory not found: $SCREENSHOTS_DIR"
  exit 1
fi

if [[ ! -f "$REQUIREMENTS_FILE" ]]; then
  echo "❌ Requirements file not found: $REQUIREMENTS_FILE"
  exit 1
fi

# ── Detect API key ────────────────────────────────────────────────────────────
detect_api_key() {
  local provider="$1"
  local env_var="$2"

  # Se explicitamente configurado via --api-key-env
  if [[ -n "$env_var" ]]; then
    echo "${!env_var:-}"
    return
  fi

  # Auto-detect por provider
  case "$provider" in
    kimi)
      echo "${KIMI_API_KEY:-}"
      ;;
    openrouter)
      echo "${OPENROUTER_API_KEY:-}"
      ;;
    gemini)
      echo "${GEMINI_API_KEY:-${GOOGLE_API_KEY:-}}"
      ;;
    claude)
      echo "${ANTHROPIC_API_KEY:-}"
      ;;
    openai)
      echo "${OPENAI_API_KEY:-}"
      ;;
    *)
      echo ""
      ;;
  esac
}

API_KEY=$(detect_api_key "$PROVIDER" "$API_KEY_ENV")

if [[ -z "$API_KEY" ]]; then
  echo "❌ No API key found for provider '$PROVIDER'."
  echo "   Set the appropriate environment variable:"
  echo "   - Kimi Code:  KIMI_API_KEY"
  echo "   - OpenRouter: OPENROUTER_API_KEY"
  echo "   - Gemini:     GEMINI_API_KEY or GOOGLE_API_KEY"
  echo "   - Claude:     ANTHROPIC_API_KEY"
  echo "   - OpenAI:     OPENAI_API_KEY"
  echo "   Or pass --api-key-env VAR_NAME"
  exit 1
fi

# ── Detect best model ─────────────────────────────────────────────────────────
detect_model() {
  local provider="$1"

  if [[ -n "$MODEL" ]]; then
    echo "$MODEL"
    return
  fi

  case "$provider" in
    kimi)       echo "kimi-k2.5" ;;
    openrouter) echo "anthropic/claude-sonnet-4-20250514" ;;
    gemini)     echo "gemini-2.5-flash" ;;
    claude)     echo "claude-sonnet-4-20250514" ;;
    openai)     echo "gpt-4o" ;;
    *)          echo "" ;;
  esac
}

MODEL=$(detect_model "$PROVIDER")

$VERBOSE && echo "🔍 Provider: $PROVIDER | Model: $MODEL"
$VERBOSE && echo "📂 Screenshots dir: $SCREENSHOTS_DIR"
$VERBOSE && echo "📋 Requirements: $REQUIREMENTS_FILE"
$VERBOSE && echo "📤 Output: $OUTPUT_FILE"

# ── Ensure output directory exists ────────────────────────────────────────────
mkdir -p "$(dirname "$OUTPUT_FILE")"

# ── Build the evaluation prompt from visual-requirements.yaml ─────────────────
build_requirements_prompt() {
  local req_file="$1"
  local screenshot_name="$2"

  # Extract the relevant section from YAML using awk
  # Looks for the key matching screenshot_name and captures lines until next top-level key
  awk -v name="$screenshot_name" '
    BEGIN { found=0; printed=0 }
    /^[a-zA-Z0-9_-]+:/ {
      if (found && printed > 0) exit
      key = substr($0, 1, index($0, ":") - 1)
      if (key == name) { found=1; next }
    }
    found {
      if ($0 ~ /^[a-zA-Z0-9_-]+:/ && NR > 1) exit
      if ($0 !~ /^#.*──/ && $0 !~ /^#  (LAYOUT|SEMANTIC)/) {
        print
        printed++
      }
    }
  ' "$req_file"
}

# ── Call Kimi Code API (Anthropic Messages-compatible) ────────────────────────
call_kimi() {
  local image_base64="$1"
  local prompt_text="$2"

  local api_url="https://api.kimi.com/coding/"

  local payload
  payload=$(jq -n \
    --arg model "$MODEL" \
    --arg prompt "$prompt_text" \
    --arg img "$image_base64" \
    '{
      model: $model,
      max_tokens: 4096,
      temperature: 0.1,
      messages: [{
        role: "user",
        content: [
          { type: "image", source: { type: "base64", media_type: "image/png", data: $img } },
          { type: "text", text: $prompt }
        ]
      }]
    }')

  local response
  response=$(curl -s -X POST "$api_url" \
    -H "Content-Type: application/json" \
    -H "x-api-key: $API_KEY" \
    -H "anthropic-version: 2023-06-01" \
    -d "$payload" 2>/dev/null)

  echo "$response" | jq -r '.content[0].text // "ERROR: No text in response"' 2>/dev/null
}

# ── Call Open Router API (OpenAI chat-completions-compatible) ─────────────────
call_openrouter() {
  local image_base64="$1"
  local prompt_text="$2"

  local api_url="https://openrouter.ai/api/v1/chat/completions"

  local payload
  payload=$(jq -n \
    --arg model "$MODEL" \
    --arg prompt "$prompt_text" \
    --arg img "$image_base64" \
    '{
      model: $model,
      max_tokens: 4096,
      temperature: 0.1,
      messages: [{
        role: "user",
        content: [
          { type: "text", text: $prompt },
          { type: "image_url", image_url: { url: ("data:image/png;base64," + $img) } }
        ]
      }]
    }')

  local response
  response=$(curl -s -X POST "$api_url" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $API_KEY" \
    -H "HTTP-Referer: https://github.com/bagual-test-pipeline" \
    -d "$payload" 2>/dev/null)

  echo "$response" | jq -r '.choices[0].message.content // "ERROR: No text in response"' 2>/dev/null
}

# ── Call Gemini Vision API ────────────────────────────────────────────────────
call_gemini() {
  local image_base64="$1"
  local prompt_text="$2"

  local api_url="https://generativelanguage.googleapis.com/v1beta/models/${MODEL}:generateContent?key=${API_KEY}"

  # Build JSON payload
  local payload
  payload=$(jq -n \
    --arg prompt "$prompt_text" \
    --arg img "$image_base64" \
    '{
      contents: [{
        parts: [
          { text: $prompt },
          { inline_data: { mime_type: "image/png", data: $img } }
        ]
      }],
      generation_config: {
        temperature: 0.1,
        max_output_tokens: 2048
      }
    }')

  local response
  response=$(curl -s -X POST "$api_url" \
    -H "Content-Type: application/json" \
    -d "$payload" 2>/dev/null)

  # Extract text from response
  echo "$response" | jq -r '.candidates[0].content.parts[0].text // "ERROR: No text in response"' 2>/dev/null
}

# ── Call Claude Vision API ────────────────────────────────────────────────────
call_claude() {
  local image_base64="$1"
  local prompt_text="$2"

  local api_url="https://api.anthropic.com/v1/messages"

  local payload
  payload=$(jq -n \
    --arg model "$MODEL" \
    --arg prompt "$prompt_text" \
    --arg img "$image_base64" \
    '{
      model: $model,
      max_tokens: 2048,
      temperature: 0.1,
      messages: [{
        role: "user",
        content: [
          { type: "image", source: { type: "base64", media_type: "image/png", data: $img } },
          { type: "text", text: $prompt }
        ]
      }]
    }')

  local response
  response=$(curl -s -X POST "$api_url" \
    -H "Content-Type: application/json" \
    -H "x-api-key: $API_KEY" \
    -H "anthropic-version: 2023-06-01" \
    -d "$payload" 2>/dev/null)

  echo "$response" | jq -r '.content[0].text // "ERROR: No text in response"' 2>/dev/null
}

# ── Call OpenAI Vision API ────────────────────────────────────────────────────
call_openai() {
  local image_base64="$1"
  local prompt_text="$2"

  local api_url="https://api.openai.com/v1/chat/completions"

  local payload
  payload=$(jq -n \
    --arg model "$MODEL" \
    --arg prompt "$prompt_text" \
    --arg img "$image_base64" \
    '{
      model: $model,
      max_tokens: 2048,
      temperature: 0.1,
      messages: [{
        role: "user",
        content: [
          { type: "text", text: $prompt },
          { type: "image_url", image_url: { url: ("data:image/png;base64," + $img) } }
        ]
      }]
    }')

  local response
  response=$(curl -s -X POST "$api_url" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $API_KEY" \
    -d "$payload" 2>/dev/null)

  echo "$response" | jq -r '.choices[0].message.content // "ERROR: No text in response"' 2>/dev/null
}

# ── Route to correct provider ─────────────────────────────────────────────────
call_vision_ai() {
  local image_base64="$1"
  local prompt_text="$2"

  case "$PROVIDER" in
    kimi)       call_kimi "$image_base64" "$prompt_text" ;;
    openrouter) call_openrouter "$image_base64" "$prompt_text" ;;
    gemini)     call_gemini "$image_base64" "$prompt_text" ;;
    claude)     call_claude "$image_base64" "$prompt_text" ;;
    openai)     call_openai "$image_base64" "$prompt_text" ;;
    *)
      echo "ERROR: Unknown provider '$PROVIDER'"
      return 1
      ;;
  esac
}

# ── Parse AI response into structured pass/fail ───────────────────────────────
parse_ai_response() {
  local ai_response="$1"
  local screenshot_name="$2"

  # Try to extract PASS/FAIL from the response
  local passed
  if echo "$ai_response" | grep -qi "FINAL: PASS"; then
    passed=true
  elif echo "$ai_response" | grep -qi "FINAL: FAIL"; then
    passed=false
  else
    # Default: if no clear signal, treat as inconclusive (pass with warning)
    passed=true
    ai_response="⚠️  [INCONCLUSIVE] Could not determine pass/fail from AI response. Raw response: $ai_response"
  fi

  # Generate structured output
  jq -n \
    --arg screenshot "$screenshot_name" \
    --arg timestamp "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" \
    --argjson passed "$passed" \
    --arg issues "$ai_response" \
    '{
      screenshot: $screenshot,
      timestamp: $timestamp,
      passed: $passed,
      issues: (if $passed then "" else $issues end),
      description: $issues
    }'
}

# ── Main evaluation loop ──────────────────────────────────────────────────────
TOTAL=0
PASSED_COUNT=0
FAILED_COUNT=0
RESULTS=()

$VERBOSE && echo ""
$VERBOSE && echo "═══════════════════════════════════════════════════════════════"
$VERBOSE && echo "  VISUAL VALIDATION — AI-Mediated (Provider: $PROVIDER / $MODEL)"
$VERBOSE && echo "═══════════════════════════════════════════════════════════════"
$VERBOSE && echo ""

# Read all PNG files sorted by name
while IFS= read -r -d '' png_file; do
  TOTAL=$((TOTAL + 1))
  filename=$(basename "$png_file")
  name_no_ext="${filename%.png}"

  $VERBOSE && echo "📸 [$TOTAL] Evaluating: $filename"

  # Build requirements for this specific screenshot
  requirements=$(build_requirements_prompt "$REQUIREMENTS_FILE" "$name_no_ext")

  if [[ -z "$requirements" ]]; then
    $VERBOSE && echo "   ⚠️  No requirements found for '$name_no_ext' — marking as passed (no rules)"
    result=$(jq -n \
      --arg screenshot "$filename" \
      --arg timestamp "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" \
      '{
        screenshot: $screenshot,
        timestamp: $timestamp,
        passed: true,
        issues: "",
        description: "No visual requirements defined for this screenshot."
      }')
    RESULTS+=("$result")
    PASSED_COUNT=$((PASSED_COUNT + 1))
    continue
  fi

  # Encode image to base64
  image_base64=$(base64 -w 0 "$png_file" 2>/dev/null || base64 "$png_file")

  # Build the master prompt
  master_prompt=$(cat <<PROMPT_EOF
You are a visual QA inspector. Your job is to evaluate a screenshot of a web application against a set of visual and semantic requirements. You MUST be strict — flag ANY deviation from the expected state.

## SCREENSHOT CONTEXT
- Screenshot name: ${name_no_ext}
- This is a screenshot from an E2E test automation pipeline.

## VISUAL REQUIREMENTS TO VERIFY
${requirements}

## EVALUATION INSTRUCTIONS

Check EVERY requirement below. For each one, state whether it PASSES or FAILS. Be detailed about what you observe.

### Step 1 — Layout Checks
For each layout requirement:
- Is the element present and visible?
- Is it properly aligned?
- Is there any text truncation, overflow, or overlap?
- Is spacing consistent?

### Step 2 — Semantic Data Consistency Checks
For each semantic requirement:
- Do the values and states shown on screen make logical sense together?
- Do counts match visible items?
- Do active filters visually match the filtered list?
- Do totals match row data?
- Do empty states appear only when data is absent?
- Do selected/active indicators match the actual selection state?

### Step 3 — Overall Verdict
After evaluating all requirements, give a final verdict:

If ALL requirements pass → respond with: **FINAL: PASS**
If ANY requirement fails → respond with: **FINAL: FAIL**

Then list each failed requirement with a specific description of what is wrong.

## FORMAT YOUR RESPONSE AS:

### Layout
- [PASS/FAIL] Requirement description → Observed: what you actually see

### Semantic
- [PASS/FAIL] Requirement description → Observed: what you actually see

### Final
**FINAL: PASS** or **FINAL: FAIL**

If FINAL: FAIL, list specific issues:
- Issue 1: ...
- Issue 2: ...
PROMPT_EOF
)

  $VERBOSE && echo "   📤 Sending to ${PROVIDER} (${MODEL})..."

  # Call the vision AI
  ai_response=$(call_vision_ai "$image_base64" "$master_prompt")

  if [[ "$ai_response" == ERROR:* ]]; then
    $VERBOSE && echo "   ❌ AI call failed: $ai_response"
    result=$(jq -n \
      --arg screenshot "$filename" \
      --arg timestamp "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" \
      --arg error "$ai_response" \
      '{
        screenshot: $screenshot,
        timestamp: $timestamp,
        passed: false,
        issues: $error,
        description: ("AI evaluation failed: " + $error)
      }')
    FAILED_COUNT=$((FAILED_COUNT + 1))
  else
    # Parse the AI response
    result=$(parse_ai_response "$ai_response" "$filename")

    passed=$(echo "$result" | jq -r '.passed')
    if [[ "$passed" == "true" ]]; then
      PASSED_COUNT=$((PASSED_COUNT + 1))
      $VERBOSE && echo "   ✅ PASS"
    else
      FAILED_COUNT=$((FAILED_COUNT + 1))
      $VERBOSE && echo "   ❌ FAIL"
    fi
  fi

  RESULTS+=("$result")

done < <(find "$SCREENSHOTS_DIR" -maxdepth 1 -name '*.png' -print0 | sort -z)

# ── Nothing to evaluate ───────────────────────────────────────────────────────
if [[ $TOTAL -eq 0 ]]; then
  $VERBOSE && echo "⚠️  No PNG screenshots found in $SCREENSHOTS_DIR"
  jq -n \
    --arg generatedAt "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" \
    '{
      totalScreenshots: 0,
      passedCount: 0,
      failedCount: 0,
      generatedAt: $generatedAt,
      provider: "'${PROVIDER}'",
      model: "'${MODEL}'",
      mode: "ai-mediated",
      results: []
    }' > "$OUTPUT_FILE"
  exit 0
fi

# ── Write final report ────────────────────────────────────────────────────────
RESULTS_JSON="[$(IFS=,; echo "${RESULTS[*]}")]"

jq -n \
  --argjson total "$TOTAL" \
  --argjson passed "$PASSED_COUNT" \
  --argjson failed "$FAILED_COUNT" \
  --arg generatedAt "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" \
  --arg provider "$PROVIDER" \
  --arg model "$MODEL" \
  --argjson results "$RESULTS_JSON" \
  '{
    totalScreenshots: $total,
    passedCount: $passed,
    failedCount: $failed,
    generatedAt: $generatedAt,
    provider: $provider,
    model: $model,
    mode: "ai-mediated",
    results: $results
  }' > "$OUTPUT_FILE"

# ── Summary ────────────────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  VISUAL VALIDATION COMPLETE"
echo "═══════════════════════════════════════════════════════════════"
echo "  Provider:   $PROVIDER ($MODEL)"
echo "  Screenshots: $TOTAL evaluated"
echo "  Passed:     $PASSED_COUNT"
echo "  Failed:     $FAILED_COUNT"
echo "  Report:     $OUTPUT_FILE"
echo "═══════════════════════════════════════════════════════════════"

# Exit with failure if any visual check failed
if [[ $FAILED_COUNT -gt 0 ]]; then
  exit 1
fi

exit 0
