# Princípios do kit — leia antes de gerar qualquer skill

> Regras transversais que valem para **todos** os blocos de técnica deste kit. Uma skill gerada
> pelo `bagual-skill-forge` que viole um destes princípios está errada, independentemente de quais
> técnicas ela carregue.

## P0 — Genérico, nunca acoplado a um projeto

Este kit foi **destilado** de um sistema real de orquestração de agentes (um "Gerente Geral"
autônomo construído sobre BMad), mas tudo que era **específico daquele produto** foi cortado na
curadoria: roteamento contra telas de UX, gates de QA por visão, pipelines de epic/story,
integração de billing, promoção entre ambientes, consciência de cota de uma assinatura específica.

O que sobrou são **padrões de arquitetura de agentes** que servem para qualquer projeto e qualquer
assunto — não só programação. Ao gerar uma skill nova:

- **Nunca** copie nomes, telas, entidades de domínio ou caminhos do projeto de origem.
- Os `templates/` usam placeholders `<ASSIM>` — preencha-os com o domínio do projeto **destino**,
  perguntando ao usuário quando não for óbvio.
- Se uma técnica só faz sentido para software, o doc dela diz isso explicitamente em "Quando NÃO
  usar" — respeite.

## P1 — Ativação enxuta (progressive disclosure) — a regra que mais importa

O maior defeito do sistema de origem era a **ativação lenta**: a skill de topo lia uma persona de
1100+ linhas **inteira** + vários arquivos de estado + rodava 5 scripts, tudo *antes* de decidir
qualquer coisa. Isso é o anti-padrão nº 1 a **não repetir**.

Toda skill gerada por este kit nasce com **ativação enxuta**:

1. **`SKILL.md` minúsculo** — só o gatilho, os limites invioláveis, e um roteador de 1 parágrafo
   que diz "para X, leia `references/x.md`". Nunca despeje o contrato inteiro no SKILL.md.
2. **Persona/contrato curtos** — o arquivo em `.claude/agents/<nome>.md` carrega o **esqueleto** de
   decisão (quem é, os limites, o loop em uma lista curta). Os detalhes de cada técnica ficam em
   `references/` e são lidos **sob demanda** (grep-native), não eager.
3. **Estado lido só quando a fase precisa** — não leia todos os arquivos de estado na ativação;
   leia o que a fase atual do trabalho exige, quando exige.
4. **Regra prática:** se ligar a skill gerada faz o agente ler >~300 linhas antes de fazer a
   primeira decisão útil, o desenho está errado — quebre em referências sob demanda.

## P2 — Persona-como-arquivo, fora da skill

A definição de um agente autônomo (a "persona": quem ele é, seus limites, seu loop) vive em
**`.claude/agents/<nome>.md`**, não embutida no `SKILL.md`. A skill é só um **invocador fino** que
diz "adote a persona de `.claude/agents/<nome>.md` e rode o que o usuário pediu".

Por quê: mantém a definição do agente **num lugar só** (editável, versionável, reutilizável por
despacho headless via `subagent_type`), e mantém o `SKILL.md` enxuto (P1). Skills de **tarefa pura**
(que não são um agente autônomo) podem não ter persona separada — o doc de cada bloco diz quando
uma persona é necessária.

## P3 — Duas naturezas de skill: TOPO vs TAREFA

O kit gera dois tipos, e a escolha muda quais blocos fazem sentido:

- **Skill de TOPO** (um agente que decide/despacha/cura — como o "Gerente"): tem persona separada
  (P2), estado persistente (Bloco B), e tipicamente **não executa** o trabalho pesado — despacha
  para sub-agentes. Blocos A/B fazem sentido pleno aqui.
- **Skill de TAREFA** (executa uma unidade de trabalho do início ao fim): pode dispensar persona e
  estado persistente, mas se beneficia muito de autoaprendizado (Bloco D) e captura de conhecimento
  (Bloco E).

## P4 — "O topo nunca executa"

Se a skill gerada é de topo (P3), ela **decide, despacha e cura contexto** — o trabalho que muda
arquivos/o mundo roda sempre num **sub-agente despachado**, nunca na própria camada de topo. Isto é
uma **regra da persona** (texto), não um guard mecânico — o kit não gera hooks de bloqueio (foi
cortado na curadoria como excessivo). Mantê-lo é disciplina declarada, reforçada pelo contrato de
despacho (Bloco A).

## P5 — RULE ZERO herdada

Toda skill gerada carrega a obrigação do Bloco E (captura de conhecimento ao fim de cada tarefa),
mesmo que o projeto destino ainda não tenha uma Wiki/Ledger montada — nesse caso o doc do Bloco E
gera o esqueleto mínimo. Conhecimento não registrado entre execuções = o próximo agente trabalha às
cegas.

## P6 — Não forke skills de terceiros

Se o projeto destino usa frameworks de skill de terceiros (BMad/WDS/etc.), a skill gerada **compõe**
com eles (chama, referencia) mas **nunca os copia/forka**. O kit gera skills novas, próprias do
projeto; não duplica máquina alheia.
