#!/usr/bin/env python3
"""transition_ledger_entry.py — E4.2/E4.3 escrita de transições de estado do Ledger.

Story E4.2 (ideias/sistema-artifacts/E4-2-ciclo-vida-causa-morte.md),
E4.3 (E4-3-contador-utilidade.md) — PRD 01 FR-5/FR-7, ideias/epics.md Epic E4.

Mecaniza as três únicas mutações de front-matter que uma Entrada de Ledger sofre depois
de criada — sempre com escrita atômica (temp + flush + `fsync` + rename), a MESMA
primitiva usada por `_bmad/scripts/memlog.py` (adaptada aqui para mutar o front-matter
de um arquivo de entrada individual, já que `memlog.py` em si é escopado a um único log
plano por workspace de skill, não a documentos com front-matter YAML por entrada — ver
Dev Notes da Story E4.2 para o racional completo desta escolha):

  retire         Marca uma entrada `estado: aposentada` com `causa-da-morte`
                 obrigatória. Registra a transição (data + motivo) também no corpo,
                 numa seção `## Transições` (criada se ainda não existir).

  revert         As DUAS metades da mesma transição (FR-5: "reverter cria transição
                 com link para a entrada original, nunca uma entrada solta"):
                   (a) a entrada NOVA (--new, já criada por quem revisa/escreve o
                       conteúdo — este script não inventa prosa) ganha
                       `reverte: <path relativo para --original>` no front-matter;
                   (b) a entrada ORIGINAL (--original) é retirada
                       (estado: aposentada) com
                       `causa-da-morte: "revertida por <path de --new>"`.

  bump-utilidade Incrementa `contador-de-utilidade` em N (default 1) — o PONTO DE
                 EXTENSÃO que o enforcement mecânico (PRD 04/Epic E7, ainda não
                 construído) vai acionar quando uma `regra` barrar um problema real.
                 Aqui é só a mecânica de escrita; QUEM chama este comando (o
                 enforcement de verdade) é trabalho de outra story/epic.

  mark-automated Seta `automatizado: true` numa entrada `tipo: anti-pattern` — o elo
                 que a Story E7.4 (PRD 04 FR-4) fecha entre "uma regra Semgrep foi
                 autorada a partir deste candidato" e a query de
                 `query_semgrep_candidates.py` (E4.4), que já exclui entradas
                 `automatizado: true` da fila. NÃO é destrutivo (não muda `estado`,
                 a entrada continua viva/consultável) — por isso, ao contrário de
                 `retire`/`revert`, esta mutação é "cria/marca", não "remove", e
                 cai fora do território proposal-only da bibliotecária (E3.4,
                 `curation-guide.md` §1: só fundir/aposentar são exclusivos da
                 ratificação noturna). Recusa entradas que não são
                 `tipo: anti-pattern` (o campo `automatizado` só existe nesse tipo,
                 per `ledger/README.md` §1) — evita marcar por engano uma `regra` ou
                 `decisão-*`, que não têm esse campo no schema.

Nunca escreve fora do front-matter além de anexar a linha de transição em `retire`
(append-only dentro de `## Transições`, nunca reescreve corpo existente).

Uso:
    python3 transition_ledger_entry.py retire --entry caminho/entrada.md --causa "..."
    python3 transition_ledger_entry.py revert --original caminho/velha.md --new caminho/nova.md
    python3 transition_ledger_entry.py bump-utilidade --entry caminho/regra.md [--by 1]
    python3 transition_ledger_entry.py mark-automated --entry caminho/anti-pattern.md --rule-id no-foo

Só biblioteca padrão (stdlib) — nenhuma dependência externa.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import date
from pathlib import Path

FRONT_MATTER_DELIM = "---"


def today() -> str:
    return date.today().isoformat()


def split_front_matter(text: str) -> tuple[list[str], list[str], int]:
    """Retorna (linhas_front_matter_sem_delimitadores, linhas_corpo, índice_do_fechamento).

    Levanta ValueError se não houver front-matter bem formado (dois `---`).
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != FRONT_MATTER_DELIM:
        raise ValueError("arquivo sem front-matter (primeira linha não é '---')")
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == FRONT_MATTER_DELIM), None)
    if end is None:
        raise ValueError("front-matter nunca fechado (segundo '---' não encontrado)")
    fm_lines = lines[1:end]
    body_lines = lines[end + 1 :]
    return fm_lines, body_lines, end


def _yaml_quote(value: str) -> str:
    escaped = value.replace('"', '\\"')
    return f'"{escaped}"'


def set_front_matter_field(fm_lines: list[str], key: str, value: str, quote: bool = False) -> list[str]:
    """Substitui (ou insere, se ausente) uma linha `key: value` no bloco de front-matter."""
    rendered_value = _yaml_quote(value) if quote else value
    pattern = re.compile(rf"^{re.escape(key)}\s*:")
    out: list[str] = []
    found = False
    for line in fm_lines:
        if pattern.match(line.strip()):
            comment = ""
            if not quote and "#" in line:
                comment = "  #" + line.split("#", 1)[1]
            out.append(f"{key}: {rendered_value}{comment}")
            found = True
        else:
            out.append(line)
    if not found:
        out.append(f"{key}: {rendered_value}")
    return out


def get_front_matter_field(fm_lines: list[str], key: str) -> str | None:
    pattern = re.compile(rf"^{re.escape(key)}\s*:\s*(.*)$")
    for line in fm_lines:
        m = pattern.match(line.strip())
        if m:
            raw = m.group(1).split("#")[0].strip()
            if raw.startswith('"') and raw.endswith('"') and len(raw) >= 2:
                raw = raw[1:-1]
            return raw
    return None


def append_transition_note(body_lines: list[str], motivo: str) -> list[str]:
    """Anexa `- YYYY-MM-DD: <motivo>` a uma seção `## Transições`, criando-a no fim se ausente."""
    text = "\n".join(body_lines)
    marker = "## Transições"
    entry = f"- {today()}: {motivo}"
    # "seção já existe" decidido pelo MESMO critério da inserção (linha EXATA == marker) — não
    # substring. Com `marker in text`, um heading tipo "## Transições históricas" casava aqui mas
    # nenhuma linha exata batia no laço abaixo → `inserted` ficava False e a nota de transição
    # era descartada em silêncio (perda de audit trail FR-5, com o comando ainda imprimindo OK).
    if any(line.strip() == marker for line in text.splitlines()):
        lines = text.splitlines()
        out: list[str] = []
        inserted = False
        i = 0
        while i < len(lines):
            out.append(lines[i])
            if lines[i].strip() == marker and not inserted:
                # insere logo após o heading (e uma linha em branco existente, se houver)
                j = i + 1
                while j < len(lines) and lines[j].strip() == "":
                    out.append(lines[j])
                    j += 1
                out.append(entry)
                inserted = True
                i = j
                continue
            i += 1
        return out
    else:
        new_section = ["", marker, "", entry, ""]
        return body_lines + new_section


def write_atomic(path: Path, text: str) -> None:
    """Temp + flush + fsync + rename atômico — mesma primitiva de memlog.py."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def render(fm_lines: list[str], body_lines: list[str]) -> str:
    return "\n".join([FRONT_MATTER_DELIM, *fm_lines, FRONT_MATTER_DELIM, *body_lines]).rstrip("\n") + "\n"


def cmd_retire(args: argparse.Namespace) -> int:
    entry_path = Path(args.entry)
    if not entry_path.exists():
        print(f"erro: entrada não encontrada: {entry_path}", file=sys.stderr)
        return 2
    if not args.causa or not args.causa.strip():
        print("erro: --causa é obrigatória e não pode ser vazia (FR-5)", file=sys.stderr)
        return 2

    text = entry_path.read_text(encoding="utf-8")
    fm_lines, body_lines, _ = split_front_matter(text)

    fm_lines = set_front_matter_field(fm_lines, "estado", "aposentada")
    fm_lines = set_front_matter_field(fm_lines, "causa-da-morte", args.causa, quote=True)
    fm_lines = set_front_matter_field(fm_lines, "updated", today())
    body_lines = append_transition_note(body_lines, f"aposentada — {args.causa}")

    write_atomic(entry_path, render(fm_lines, body_lines))
    print(f"OK: {entry_path} -> estado: aposentada (causa: {args.causa})")
    return 0


def cmd_revert(args: argparse.Namespace) -> int:
    original_path = Path(args.original)
    new_path = Path(args.new)
    if not original_path.exists():
        print(f"erro: entrada original não encontrada: {original_path}", file=sys.stderr)
        return 2
    if not new_path.exists():
        print(
            f"erro: entrada nova não encontrada: {new_path} "
            "(este script mecaniza a TRANSIÇÃO, não escreve a prosa da entrada nova — crie-a primeiro a partir de template-entrada.md)",
            file=sys.stderr,
        )
        return 2

    rel_new_to_original_dir = os.path.relpath(new_path, start=original_path.parent)
    rel_original_to_new_dir = os.path.relpath(original_path, start=new_path.parent)

    # (a) entrada nova ganha `reverte: <original>`
    new_text = new_path.read_text(encoding="utf-8")
    new_fm, new_body, _ = split_front_matter(new_text)
    new_fm = set_front_matter_field(new_fm, "reverte", rel_original_to_new_dir)
    new_fm = set_front_matter_field(new_fm, "updated", today())
    write_atomic(new_path, render(new_fm, new_body))

    # (b) entrada original é retirada, com causa apontando para a nova
    causa = f"revertida por {rel_new_to_original_dir}"
    orig_text = original_path.read_text(encoding="utf-8")
    orig_fm, orig_body, _ = split_front_matter(orig_text)
    orig_fm = set_front_matter_field(orig_fm, "estado", "aposentada")
    orig_fm = set_front_matter_field(orig_fm, "causa-da-morte", causa, quote=True)
    orig_fm = set_front_matter_field(orig_fm, "updated", today())
    orig_body = append_transition_note(orig_body, f"aposentada — {causa}")
    write_atomic(original_path, render(orig_fm, orig_body))

    print(f"OK: {new_path} -> reverte: {rel_original_to_new_dir}")
    print(f"OK: {original_path} -> estado: aposentada (causa: {causa})")
    return 0


def cmd_bump_utilidade(args: argparse.Namespace) -> int:
    entry_path = Path(args.entry)
    if not entry_path.exists():
        print(f"erro: entrada não encontrada: {entry_path}", file=sys.stderr)
        return 2

    text = entry_path.read_text(encoding="utf-8")
    fm_lines, body_lines, _ = split_front_matter(text)

    current_raw = get_front_matter_field(fm_lines, "contador-de-utilidade") or "0"
    try:
        current = int(current_raw)
    except ValueError:
        current = 0
    new_value = current + args.by

    fm_lines = set_front_matter_field(fm_lines, "contador-de-utilidade", str(new_value))
    fm_lines = set_front_matter_field(fm_lines, "updated", today())

    write_atomic(entry_path, render(fm_lines, body_lines))
    print(f"OK: {entry_path} -> contador-de-utilidade: {current} -> {new_value}")
    return 0


def cmd_mark_automated(args: argparse.Namespace) -> int:
    entry_path = Path(args.entry)
    if not entry_path.exists():
        print(f"erro: entrada não encontrada: {entry_path}", file=sys.stderr)
        return 2

    text = entry_path.read_text(encoding="utf-8")
    fm_lines, body_lines, _ = split_front_matter(text)

    tipo = get_front_matter_field(fm_lines, "tipo")
    if tipo != "anti-pattern":
        print(
            f"erro: {entry_path} tem tipo '{tipo}' — `automatizado` só existe no schema de "
            "tipo: anti-pattern (ledger/README.md §1); regra/decisão-*/padrão não têm este "
            "campo. Recusando marcar por engano.",
            file=sys.stderr,
        )
        return 2

    already = get_front_matter_field(fm_lines, "automatizado")
    if already is not None and already.strip().lower() == "true":
        print(f"OK (idempotente): {entry_path} já está automatizado: true — nenhuma mudança.")
        return 0

    fm_lines = set_front_matter_field(fm_lines, "automatizado", "true")
    fm_lines = set_front_matter_field(fm_lines, "updated", today())
    motivo = f"automatizado: true — regra Semgrep '{args.rule_id}' autorada (PRD 04/Epic E7)" if args.rule_id else "automatizado: true — regra Semgrep autorada (PRD 04/Epic E7)"
    body_lines = append_transition_note(body_lines, motivo)

    write_atomic(entry_path, render(fm_lines, body_lines))
    print(f"OK: {entry_path} -> automatizado: true ({motivo})")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_retire = sub.add_parser("retire", help="Marca uma entrada como aposentada, com causa obrigatória")
    p_retire.add_argument("--entry", required=True, help="Path da entrada .md")
    p_retire.add_argument("--causa", required=True, help="Causa da morte (obrigatória, não-vazia)")
    p_retire.set_defaults(func=cmd_retire)

    p_revert = sub.add_parser("revert", help="Liga entrada nova <-reverte-> entrada original, retirando a original")
    p_revert.add_argument("--original", required=True, help="Path da entrada original (será aposentada)")
    p_revert.add_argument("--new", required=True, help="Path da entrada nova (já existente, ganha `reverte:`)")
    p_revert.set_defaults(func=cmd_revert)

    p_bump = sub.add_parser("bump-utilidade", help="Incrementa contador-de-utilidade (ponto de extensão do enforcement, PRD 04)")
    p_bump.add_argument("--entry", required=True, help="Path da entrada .md")
    p_bump.add_argument("--by", type=int, default=1, help="Incremento (default: 1)")
    p_bump.set_defaults(func=cmd_bump_utilidade)

    p_mark = sub.add_parser("mark-automated", help="Seta automatizado:true numa entrada tipo:anti-pattern (Story E7.4, PRD 04 FR-4)")
    p_mark.add_argument("--entry", required=True, help="Path da entrada .md (deve ser tipo: anti-pattern)")
    p_mark.add_argument("--rule-id", required=False, default="", help="id da regra em semgrep/rules.yaml (registrado na nota de transição, rastreabilidade)")
    p_mark.set_defaults(func=cmd_mark_automated)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
