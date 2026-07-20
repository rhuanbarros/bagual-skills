> **Referência sob demanda.** Extraído verbatim de `.claude/agents/gerente-geral.md` §
> "Fluxo: promoção dev→staging" na decomposição do `SKILL.md` de `bagual-gerente-geral`
> para progressive disclosure. Único lugar onde este fluxo vive. Leia por inteiro quando o
> dono pedir para promover `dev` → `staging`.

## Fluxo: promoção dev→staging

Quando o dono pedir para **promover `dev` → `staging`** (ex.: "faz o merge do dev pra staging",
"promove pra staging", "sobe o que tá pronto pra staging"), NÃO faça um merge cego. Rode este
fluxo (validação de QA fora do escopo deste kit — instale seu próprio gate se quiser rodá-lo
depois do merge, em staging):

1. **Delta.** Calcule o que está sendo promovido: `git diff --stat staging..dev`. Guarde o
   resumo das features/telas tocadas para o relato.
2. **Checagem de promoção byte-idêntica — SEMPRE aqui, antes de fazer qualquer trabalho de
   merge/deploy.** Rode `git rev-list --count staging..dev` (commits presentes em `dev` e
   ausentes em `staging` — a mesma direção do delta do passo 1).
   - **Se a contagem for `0` (byte-idêntico):** não há nada de novo para promover — `staging`
     já contém tudo que `dev` tem. **Reporte isso no Briefing** ("promoção pedida, mas `dev` e
     `staging` já são byte-idênticos — nada a mergear/deployar") e **pare aqui**, sem tocar em
     `git merge`/deploy. Nunca faça um merge/deploy vazio só para "cumprir o pedido".
   - **Se a contagem for não-zero:** siga para o passo 3 normalmente.
3. **Merge `dev` → `staging`** (operação livre, staging não é Produção): `git checkout staging`,
   `git merge dev` (resolva conflitos ou pare e reporte se houver), `git push origin staging`.
4. **Deploy staging:** `make deploy-frontend-staging` + `make deploy-backend-staging` (livre —
   já aplicam `migrate-staging`). Volte a `dev` (`git checkout dev`) ao terminar.
5. **Reporte no Briefing** o que foi promovido — e lembre que a promoção a Produção
   (`staging → main`) é exclusiva do dono, com autorização expressa (ver a regra crítica de
   Produção).

> A promoção `staging → main` (Produção) **não** é deste fluxo — é sempre uma ação separada, do
> dono, com autorização expressa e específica (ver "🚨 REGRA CRÍTICA — Deploy … Produção" no
> AGENTS.md). Este fluxo entrega staging validado; o go pra Produção é outro momento.
