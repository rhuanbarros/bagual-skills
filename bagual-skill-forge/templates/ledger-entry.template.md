---
tipo: <decisao | regra | padrao | anti-pattern | nota-operacional>
titulo: <TÍTULO-CURTO-DESCRITIVO>
data: <ISO-UTC>
status: <ativa | superada>
# se superada, aponte para quem a substituiu:
superada_por: null
tags: [<palavra-chave>, <palavra-chave>]
---

# <TÍTULO>

## Contexto
<Por que isto surgiu — a situação que forçou a decisão/regra/observação.>

## <Decisão | Regra | Padrão | Anti-pattern | Observação>
<O conteúdo em si, em uma ou duas frases acionáveis. Para `regra`: o que fazer/não fazer. Para
`anti-pattern`: o que evitar E o que fazer no lugar. Para `padrao`: o que se repetiu ≥2x.>

## Consequências / como aplicar
<O que muda daqui pra frente. Como o próximo agente aplica isto.>

<!-- Ledger grep-native: este arquivo é a fonte de verdade. Nome do arquivo em kebab-case, sob
`<CAMINHO-WIKI>/ledger/<tipo>/`. Um fato por arquivo. Linke fatos relacionados com [[nome-do-arquivo]]. -->
