# Diário de <NOME-SKILL> (APPEND-ONLY)

> Trilha cronológica do que aconteceu, em prosa humana. Companheiro do `diario.jsonl` (mesma trilha,
> legível por máquina). **Só append** — nunca edite nem apague entradas passadas. Marque início e
> fim de cada ciclo para que uma ativação futura (ou uma recuperação de crash) saiba onde parou.

Formato de cada ciclo:

```
## CICLO-INICIO <ISO-UTC> <cycle-id>
- <o que decidi / despachei / observei>
- ...
## CICLO-FIM <ISO-UTC> <cycle-id>
- desfecho: <resumo em uma linha>
```

<!-- Scaffold vazio — nenhum ciclo ainda neste projeto. As entradas nascem ao rodar a skill. -->
