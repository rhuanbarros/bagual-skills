# `<NOME-SKILL>` — mapa dos arquivos

> Gerado por `bagual-skill-forge`. Esta skill foi equipada com os blocos de técnica: <LISTA-BLOCOS>.
> Ativação enxuta — o SKILL.md é fino e as técnicas são lidas sob demanda.

## Onde vive o quê

| Arquivo | Papel | Bloco |
|---|---|---|
| `.claude/skills/<NOME-SKILL>/SKILL.md` | Invocador fino | A |
| `.claude/agents/<NOME-SKILL>.md` | Persona (esqueleto de decisão) | A / P2 |
| `<CAMINHO-ESTADO>/estado-atual.yaml` | Snapshot "onde parei" | B |
| `<CAMINHO-ESTADO>/diario.md` + `.jsonl` | Trilha append-only | B |
| `<CAMINHO-SIDECAR>/lessons-log.md` | Reflexões cruas (append-only) | D1 |
| `<CAMINHO-SIDECAR>/playbook.md` | Regras curadas (feed-forward) | D1 |
| `<CAMINHO-CONFIG>` | Superfície de config declarada | vários |
| `<CAMINHO-WIKI>/ledger/` | Ledger tipado do projeto | E |

## Próximos passos (o dono preenche a lógica de domínio)
1. Edite `.claude/agents/<NOME-SKILL>.md` — preencha o ciclo operacional com os passos reais do seu
   domínio (o kit instalou a máquina; a lógica de negócio é sua).
2. Primeiro run: o sidecar/estado/diário nascem vazios e se populam ao rodar.
3. <SE-D2: reveja `selfheal_mode` — comece em `capture-only`, mude para `auto-fix` quando confiar.>

## O que NÃO foi instalado (cortado na curadoria do kit)
wake/scheduling/loop, consciência de cota, guards mecânicos por hook, roteamento de produto, gate de
QA, pipeline de epic/story. Se precisar de algum, é trabalho manual — não veio deste kit.
