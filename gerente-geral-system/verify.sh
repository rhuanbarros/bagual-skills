#!/usr/bin/env bash
# verify.sh — roda os self-tests da máquina do meta-sistema no projeto-destino (ou no payload).
# Os self-tests são stdlib-only (não precisam pytest). Os testes do epic-runner que usam pytest
# são rodados só se pytest estiver disponível.
#
# Uso:  ./verify.sh [/caminho/do/projeto]   (default: ./payload)
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${1:-$SCRIPT_DIR/payload}"
ROOT="$(cd "$ROOT" && pwd)"

echo "-- verificando em: $ROOT"
pass=0; fail=0; skip=0; failed=""
has_pytest="no"; python3 -c "import pytest" 2>/dev/null && has_pytest="yes"

while IFS= read -r t; do
  # testes que dependem de pytest: rodam só se pytest existir
  if grep -q "import pytest" "$t" 2>/dev/null; then
    if [ "$has_pytest" = "yes" ]; then
      if python3 -m pytest -q "$t" >/tmp/vt.txt 2>&1; then pass=$((pass+1)); else fail=$((fail+1)); failed="$failed\n  FAIL(pytest): ${t#"$ROOT"/}"; fi
    else
      skip=$((skip+1))
    fi
    continue
  fi
  # self-tests stdlib: rodam direto
  if python3 "$t" >/tmp/vt.txt 2>&1; then
    pass=$((pass+1))
  else
    fail=$((fail+1)); failed="$failed\n  FAIL: ${t#"$ROOT"/}"; echo "  ---- FAIL: ${t#"$ROOT"/} ----"; tail -4 /tmp/vt.txt
  fi
done < <(find "$ROOT" -name 'test_*.py' 2>/dev/null | sort)

echo "-- resultado: $pass verdes, $fail vermelhos, $skip pulados (pytest ausente)"
[ -n "$failed" ] && echo -e "$failed"
[ "$has_pytest" = "no" ] && [ "$skip" -gt 0 ] && echo "-- (instale pytest p/ rodar os $skip testes do epic-runner: 'uv add --dev pytest' ou 'pip install pytest')"
[ "$fail" -eq 0 ]
