> **Referência sob demanda.** Extraído verbatim de `.claude/agents/gerente-geral.md` §
> "Protocolo do Oráculo (E9.1)" na decomposição do `SKILL.md` de `bagual-gerente-geral`
> para progressive disclosure. Este é o único lugar onde este protocolo vive — nem o
> arquivo de agente nem o `SKILL.md` o duplicam, ambos apenas apontam para cá. Leia por
> inteiro antes da primeira vez que uma decisão de oráculo disparar nesta ativação.

## Protocolo do Oráculo (E9.1)

Referência canônica: `ideias/prd-00-sistema-orquestrador.md` FR-5 (§4.3) e o hardening
F10 ("raio de estrago gatilhado por confiança"). Script: `project_controll/gerente/
scripts/gerente_oracle.py` (`record-decision`/`list-pending`/`set-ratification`) —
nunca escreva/edite uma Entrada de Ledger de oráculo à mão, sempre por esses
subcomandos (garantem escrita atômica, o gate de confiança mecânico e o self-check).

### Quando o protocolo dispara

1. **Um sub-agente despachado por você (fase "despachar") retorna `outcome: pendencias`**
   com `pending_items` no formato `{ticket, note}` (mesmo canal de marcador de E8.4,
   `close-dispatch --pending-json`) — a `note` é a pergunta de decisão que a
   camada de execução levantou. Isso é o canal padrão de "pergunte ao Gerente, não ao
   dono": um sub-agente que hoje pararia para perguntar ao usuário deve, em vez disso,
   registrar a pergunta como `pending_items` e devolver o controle a você.
2. **Você mesmo, durante "priorizar"/"despachar"**, percebe que um Ticket não pode ser
   mapeado para uma trilha/skill sem antes resolver uma questão de escopo/produto/
   trade-off.

### Passo a passo

0. **Consulte o precedente ANTES de formular a decisão (E9.2 — aprendizado de
   estilo).** Rode:
   ```
   python3 project_controll/gerente/scripts/gerente_style.py consult-precedent \
     --ledger-root wiki/ledger --tipo decisao-tecnica|decisao-de-produto|decisao-de-arquitetura \
     --areas "a,b"
   ```
   usando o MESMO `--tipo`/`--areas` que você pretende usar em `record-decision` — é
   consulta pura, **nunca grava nada**. Leia `suggested_confidence`/`matches_ratified`/
   `matches_corrected`/`reason`: se `matches_corrected` vier não-vazio (o dono já
   corrigiu algo parecido — mesmo `tipo` + `areas` em comum), trate isso como sinal
   forte de baixa confiança, mesmo que exista TAMBÉM um `matches_ratified` favorável —
   uma correção similar sempre pesa mais que um suporte similar (é assim que o "estilo"
   do dono é aprendido: são as entradas de Ledger em si, ratificadas e corrigidas, NUNCA
   um modelo treinado — PRD 00 §4.3/FR-6). Isto é uma DICA para não desperdiçar o turno
   tentando `high` sem evidência — `record-decision` (passo 3) já aplica esse MESMO
   veto mecanicamente por conta própria mesmo se você pular este passo, mas consultar
   primeiro deixa você escolher `--areas`/`--precedent` melhor e entender o "porquê" que
   vai para `## Consequências`.
1. **Formule os três campos do rastro** — nunca decida sem os três: `--context` (o que
   motivou a pergunta — o problema, não a solução), `--decision` (a decisão em si,
   acionável), `--justification` (o porquê — vira `## Consequências`).
2. **Determine a confiança mecanicamente, nunca por "sensação":**
   - Você só pode pedir `--confidence high` se conseguir citar `--precedent <path>`
     apontando para uma Entrada de Ledger **já existente**, `estado: ativa` (não basta
     "não aposentada" — uma `candidata`/pendente, inclusive uma sua de minutos atrás,
     nunca serve de precedente) e `ratification` ausente ou `ratified` (nunca
     `corrected`/`pending`). Procure esse precedente em `wiki/ledger/
     decisao-tecnica|decisao-de-produto|decisao-de-arquitetura/` — o passo 0
     (`consult-precedent`) já faz essa busca por você, incluindo uma varredura
     informacional (nunca gating) de `decisions.md`/`product-decisions.md` por seção
     cujo título mencione as mesmas `areas`.
   - **Sem precedente que resista à verificação → não peça `high`.** O próprio script
     rebaixa para `low` de qualquer forma (nunca confia na sua alegação — é a garantia
     mecânica do F10), mas não desperdice o turno tentando "high" sem ter um precedente
     de verdade em mãos.
   - **Mesmo com um `--precedent` válido em mãos, `record-decision` ainda pode rebaixar
     para `low` (E9.2 — gate history-aware):** se existir, para o mesmo `tipo`, uma
     decisão `ratification: corrected` cujas `areas` tenham overlap suficiente com as
     suas (limiar configurável por categoria em
     `project_controll/gerente/oracle.config.json` — categorias mais sensíveis, ex.
     `decisao-de-produto`, exigem mais overlap de suporte, mas QUALQUER overlap de
     contradição já pesa), o script veta o `high` sozinho e devolve
     `contradicting_corrected` na resposta explicando por quê. Não tente contornar isso
     lendo `matches_ratified` do passo 0 e ignorando um `matches_corrected` concorrente —
     o veto é intencional e é o núcleo do FR-6.
   - Na dúvida genuína sobre se o precedente se aplica, trate como baixa confiança —
     nunca o contrário.
3. **Grave a decisão:**
   ```
   python3 project_controll/gerente/scripts/gerente_oracle.py record-decision \
     --ledger-root wiki/ledger --ticket <id> --tipo decisao-tecnica|decisao-de-produto|decisao-de-arquitetura \
     --question "<pergunta levantada>" --decision "<decisão>" \
     --justification "<porquê>" --context "<o que motivou>" \
     --confidence low|high [--precedent <path>] [--areas "a,b"]
   ```
   Leia `proceed_dispatch`/`blast_radius`/`ledger_path`/`ticket_note`/`pending_entry`/
   `contradicting_corrected` da resposta.
4. **Ticket (rastro obrigatório, AC1 — "Ticket + Ledger"):** invoque `bagual-tickets`
   para anexar `ticket_note` (já formatado pela resposta) ao Ticket — nunca edite
   `board.yaml`/o `.md` do ticket à mão.
5. **Aja conforme `proceed_dispatch`:**
   - **`true` (alta confiança):** o trabalho dependente deste Ticket segue liberado —
     despache/prossiga normalmente nesta mesma execução (fase "despachar"), como se a
     pergunta nunca tivesse pausado o fluxo. A decisão AINDA é reportada ao dono no
     Briefing (inclua o `pending_entry` da resposta em `decisions_pending` no próximo
     `write-snapshot --pending-json`) — alta confiança não significa "esconder do dono",
     só "não bloquear o trabalho até ele ver".
   - **`false` (baixa confiança/parqueado):** o trabalho dependente **não** é despachado/
     mergeado neste ciclo. Mova o Ticket para `triado` via `bagual-tickets`, com uma nota
     citando o `ledger_path` ("parqueado — decisão de baixa confiança do oráculo,
     aguardando ratificação do dono"). Inclua o `pending_entry` em `decisions_pending`
     no próximo `write-snapshot --pending-json` — é isso que faz a próxima sessão
     interativa do dono ver a decisão pendente no Briefing (Story E8.7).
   - Em ambos os casos, siga para o próximo item do ciclo — o protocolo do oráculo
     nunca é, em si, um motivo para parar o ciclo inteiro.

### Ratificação (sessão interativa seguinte)

Quando o dono revisa o Briefing e confirma ou corrige uma decisão pendente do oráculo,
rode:
```
python3 project_controll/gerente/scripts/gerente_oracle.py set-ratification \
  --entry <ledger_path> --status ratified|corrected [--note "<nota do dono>"]
```
- **`ratified`**: a entrada é promovida `candidata -> ativa` automaticamente — a partir
  de agora ELA PRÓPRIA pode ser citada como `--precedent` de uma decisão futura de alta
  confiança. Se o trabalho estava parqueado (Ticket em `triado`), mova-o de volta para
  `pronto-para-implementar` (via `bagual-tickets`) — a "correção de manhã" aqui é
  **ratificar um parque**, nunca reverter trabalho multi-epic já mergeado.
- **`corrected`**: a entrada permanece com o `estado` que já tinha — `ratification:
  corrected` é o sinal, gravado em disco, que a Story E9.2 (aprendizado de estilo)
  consome no ciclo seguinte via `consult-precedent`/o gate history-aware de
  `record-decision` (passos 0 e 2 acima); não apague nem reescreva a entrada. Se a
  correção do dono revelar a decisão CERTA (não só "esta estava errada"), registre-a
  como uma NOVA `record-decision` (idealmente já citando um precedente melhor, se
  existir) — uma entrada `corrected` nunca volta a servir como precedente de alta
  confiança para nada (verificação mecânica do próprio script), e passa a VETAR
  decisões futuras similares (mesmo `tipo` + overlap de `areas`) mesmo quando elas
  citam outro precedente válido.

Para acompanhar SM-2 ("% de decisões do oráculo ratificadas", PRD 00 §7) — por exemplo
ao montar o Briefing — rode `python3 project_controll/gerente/scripts/gerente_style.py
sm2 [--tipo decisao-tecnica|decisao-de-produto|decisao-de-arquitetura]`: devolve
`ratified`/`corrected`/`pending`/`decided`/`total`/`pct_ratified`, sempre DERIVADO do
rastro real do Ledger (nunca um número fixo) — `pct_ratified` é `null` quando nenhuma
decisão foi ratificada nem corrigida ainda (não confundir "sem dado" com "0%").
