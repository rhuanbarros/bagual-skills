# gerente-geral-system — kit portável do meta-sistema

Um pacote self-contained do **meta-sistema de orquestração autônoma** (o "Gerente Geral") para
instalar num projeto novo com um comando. Versão **genérica** (destilada do template, sem conteúdo
de nenhum produto específico).

## O que está incluído

| Peça | Onde vai no destino | O que é |
|---|---|---|
| **Gerente Geral** (skill, persona embutida) | `.claude/skills/bagual-gerente-geral/` | Camada de topo autônoma: lê estado, prioriza, despacha, revisa, registra, para. **Nunca executa código** — despacha. A persona vive no próprio `SKILL.md` (sem `.claude/agents/gerente-geral.md` separado — dobrado pra dentro da skill, ver "Arquitetura" abaixo). |
| **Tickets** (skill) | `.claude/skills/bagual-tickets/` + `project_controll/tickets/` | Porta única de entrada de trabalho: raw-check, dedup, checagem de decisão de produto, expansão. Board em `board.yaml`. |
| **Camada de execução** (skill) | `.claude/skills/bagual-epic-runner/` | Executa uma epic/story do início ao fim: create-story → dev-story → [code-review] → retrospective. Despachada pelo Gerente. |
| **Estado do Gerente** | `project_controll/gerente/` | Scripts (stdlib), configs, contrato de despacho, estado/diário, README operacional. |
| **Wiki/Ledger** | `wiki/` | Memória do projeto: Ledger tipado grep-native (decisões/regras/padrões/anti-patterns) + notas operacionais + scripts. |
| **Deps dos testes** | `semgrep/scripts/`, `_bmad/scripts/memlog.py` | Referenciados pelos self-tests/briefing. Stdlib-only. |
| **Fixtures + self-tests** | `project_controll/test-fixtures/` + `test_*.py` espalhados | Provam a máquina e alimentam o **self-heal** (autocorreção). |

## O que foi REMOVIDO (de propósito)

- **QA gate** (`bagual-qa-setup` / `bagual-qa-builder` / `bagual-qa-run`) — as skills não vêm no kit,
  e as referências a QA foram limpas da persona e do epic-runner (o Step 4.5 QA-Gate saiu do
  pipeline). Se você quiser um gate de QA no projeto novo, instale/monte o seu — os pontos onde ele
  entraria estão marcados com "(validação de QA fora do escopo deste kit)".
- **Guards mecânicos por script** (`gerente_tool_guard.py`, `prod_deploy_guard.py`, `.claude/settings.json`)
  — existiam num momento anterior do kit, mas foram removidos daqui seguindo a mesma decisão que o
  template de origem tomou (`wiki/ledger/decisao-tecnica/sem-guards-mecanicos-por-script.md` no
  projeto-filho que originou a decisão): um `PreToolUse` hook que nega a ação no meio do fluxo
  atrapalha mais do que protege quando o dono precisa que o agente execute algo pontualmente em
  Produção, e o guard de edição nunca chegou a ser cabeado de verdade. As duas regras — "o Gerente
  nunca edita `frontend/**`/`backend/**`/`supabase/**` diretamente" e "Produção é exclusiva do
  dono" — continuam existindo, só que como **regra de contrato/disciplina** na persona
  (`.claude/skills/bagual-gerente-geral/references/identity-and-limits.md`), não como backstop
  mecânico.

## Dependências no projeto-destino

- **`python3`** (a máquina é stdlib-only; nenhum `pip install` obrigatório).
- **BMad** — o `bagual-epic-runner` orquestra as skills `bmad-create-story` / `bmad-dev-story` /
  `bmad-code-review` / `bmad-retrospective`. Sem o BMad instalado no destino, o epic-runner não roda
  (o resto — Gerente, Tickets, Wiki — funciona sem BMad).
- **pytest** (opcional) — só para os testes do epic-runner (`scripts/tests/`). Os self-tests da
  máquina (Gerente/Tickets/Wiki) são stdlib e rodam sem pytest.

## Instalação

Noutro computador: clone o `bagual-skills`, e rode:

```bash
cd gerente-geral-system
./install.sh /caminho/do/projeto-destino            # instala (merge não-destrutivo)
./install.sh /caminho/do/projeto-destino --dry-run  # só mostra o que faria
```

O instalador:
1. Copia o `payload/` para a raiz do destino **sem sobrescrever** nada que já exista (conflitos são
   pulados e reportados pra você reconciliar à mão).
2. Semeia o estado vivo a partir dos exemplos (`estado-atual.yaml`, `diario.md/.jsonl` vazios).
3. Roda a **verificação** (`verify.sh`) — os self-tests da máquina.

Depois: preencha os placeholders de domínio (`<PROJETO>`, `<SUPABASE_REF_*>`, hosts) na skill e
nos `*.config.json`, garanta o BMad no destino, e ative com `/bagual-gerente-geral`.

## Verificar a qualquer momento

```bash
./verify.sh /caminho/do/projeto-destino   # roda os self-tests no destino
./verify.sh                               # roda no próprio payload
```

## Arquitetura (resumo)

Três camadas: **Gerente** (decide/despacha, Opus) → **execução** (epic-runner, Sonhet) →
**sub-agente** (tarefa isolada). O Gerente despacha por **marcador em disco** (sobrevive a
crash/compactação) em **background por padrão** — segue pro próximo passo do ciclo sem esperar o
retorno, e revisa quando a notificação do despacho chegar (nunca despacha mais de um Ticket em
paralelo no mesmo checkout, porém). Tem **lock singleton** + **recuperação de crash**, aprende via
**sidecar** (autoaprendizado) e **self-heal** (autocorreção), registra conhecimento no **Ledger**
(RULE ZERO), e aprende o **estilo do dono**. A persona vive no próprio
`payload/.claude/skills/bagual-gerente-geral/SKILL.md` (sem agente separado) e é curta por
construção — progressive disclosure: cada protocolo pesado (identidade/limites completos, Oráculo,
Cérebro de Planejamento, o loop de 6 fases, promoção dev→staging, self-healing) vive em
`payload/.claude/skills/bagual-gerente-geral/references/*.md`, carregado sob demanda só quando a
situação bate, nunca eager-load. Detalhe completo em `payload/project_controll/gerente/README.md`.
As duas regras mais críticas da persona ("nunca edita código de produto", "Produção é exclusiva do
dono") são **regra de contrato**, não backstop mecânico — ver "O que foi REMOVIDO" acima.

> Nota: para **criar skills novas** com essas técnicas de forma curada/genérica (em vez de instalar o
> sistema inteiro), veja a skill separada `bagual-skill-forge` — ela gera skills sob medida escolhendo
> só os blocos de técnica que você quer.
