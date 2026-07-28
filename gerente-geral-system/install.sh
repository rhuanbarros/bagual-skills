#!/usr/bin/env bash
# install.sh — instala o kit "gerente-geral-system" (Gerente Geral + Tickets + Wiki/Ledger +
# camada de execução epic-runner) num projeto novo.
#
# Uso:
#   ./install.sh /caminho/do/projeto-destino          # instala
#   ./install.sh /caminho/do/projeto-destino --dry-run # só mostra o que faria
#
# NÃO sobrescreve arquivos já existentes no destino (merge não-destrutivo). Arquivos que já
# existem no destino são PULADOS e reportados no fim para você reconciliar à mão.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PAYLOAD="$SCRIPT_DIR/payload"

TARGET="${1:-}"
DRY_RUN="no"
[ "${2:-}" = "--dry-run" ] && DRY_RUN="yes"

if [ -z "$TARGET" ]; then
  echo "erro: informe o projeto-destino.  Uso: ./install.sh /caminho/do/projeto [--dry-run]" >&2
  exit 1
fi
if [ ! -d "$TARGET" ]; then
  echo "erro: destino '$TARGET' não existe ou não é diretório." >&2
  exit 1
fi
if [ ! -d "$PAYLOAD" ]; then
  echo "erro: payload não encontrado em '$PAYLOAD'." >&2
  exit 1
fi
TARGET="$(cd "$TARGET" && pwd)"

if [ ! -d "$TARGET/.git" ]; then
  echo "aviso: '$TARGET' não parece um repositório git. Recomenda-se instalar num repo versionado"
  echo "       (pra você revisar o diff da instalação). Continuando mesmo assim em 3s..."
  sleep 3 || true
fi

echo "== Instalando gerente-geral-system em: $TARGET"
[ "$DRY_RUN" = "yes" ] && echo "== MODO DRY-RUN (nada será escrito)"

copied=0; skipped=0; skiplist=""
while IFS= read -r src; do
  rel="${src#"$PAYLOAD"/}"
  dst="$TARGET/$rel"
  if [ -e "$dst" ]; then
    skipped=$((skipped+1)); skiplist="$skiplist\n  PULADO (já existe): $rel"
    continue
  fi
  copied=$((copied+1))
  if [ "$DRY_RUN" = "no" ]; then
    mkdir -p "$(dirname "$dst")"
    cp "$src" "$dst"
  fi
done < <(find "$PAYLOAD" -type f | sort)

echo "== Arquivos: $copied copiados, $skipped pulados (já existiam)."
[ -n "$skiplist" ] && echo -e "== Conflitos a reconciliar à mão:$skiplist"

# --- Semear estado vivo a partir dos exemplos (só se ainda não existir) ---
if [ "$DRY_RUN" = "no" ]; then
  GER="$TARGET/project_controll/gerente"
  if [ -f "$GER/estado-atual.example.yaml" ] && [ ! -f "$GER/estado-atual.yaml" ]; then
    cp "$GER/estado-atual.example.yaml" "$GER/estado-atual.yaml"
    echo "== Semeado: project_controll/gerente/estado-atual.yaml (do exemplo)"
  fi
  [ -f "$GER/diario.md" ]   || { printf '# Diário do Gerente Geral (APPEND-ONLY)\n' > "$GER/diario.md"; echo "== Criado: diario.md vazio"; }
  [ -f "$GER/diario.jsonl" ] || { : > "$GER/diario.jsonl"; echo "== Criado: diario.jsonl vazio"; }
fi

echo
echo "== Verificação (self-tests da máquina)..."
if [ "$DRY_RUN" = "no" ]; then
  bash "$SCRIPT_DIR/verify.sh" "$TARGET" || echo "== aviso: alguns self-tests falharam — ver acima."
else
  echo "   (pulada no dry-run)"
fi

cat <<EOF

== PRONTO. Próximos passos:
   1. Revise o diff da instalação (git status / git diff no destino).
   2. Preencha os placeholders do domínio (<PROJETO>, <SUPABASE_REF_*>, hosts) na skill
      .claude/skills/bagual-gerente-geral/SKILL.md (+ references/identity-and-limits.md)
      e nos configs de project_controll/gerente/*.config.json.
   3. A camada de execução (bagual-epic-runner) depende das skills BMad
      (bmad-create-story / bmad-dev-story / bmad-code-review / bmad-retrospective).
      Garanta que o projeto destino tem o BMad instalado, senão o epic-runner não roda.
   4. Ative:  /bagual-gerente-geral   (ou "rodar o ciclo do Gerente")
              /bagual-tickets         (porta de entrada de trabalho)
   Ver README.md deste kit para o que está incluído, o que foi removido (QA + os guards
   mecânicos por script), e a arquitetura.
EOF
