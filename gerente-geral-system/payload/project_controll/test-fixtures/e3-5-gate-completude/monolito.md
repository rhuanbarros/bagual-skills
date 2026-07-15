# Monólito de Brinquedo (fixture E3.5)

Este arquivo simula um monólito real (`notes.md`/`decisions.md` etc.) sendo
fatiado em 3 seções `## H2`, para testar o gate mecânico de completude
(`slice_completeness_gate.py`) sem tocar nos monólitos de verdade.

## Seção Alfa

Texto da seção alfa, com uma frase importante que não pode ser perdida: "o
gato subiu no telhado à noite".
Mais uma linha de contexto para a seção alfa, que também precisa
sobreviver ao fatiamento sem ser resumida ou truncada.

## Seção Beta

Texto da seção beta, com uma frase crítica: "o cachorro correu atrás do
carro pela rua".
Detalhe adicional da seção beta que também precisa sobreviver ao
fatiamento — esta é a frase que a variante "texto truncado" vai derrubar.

## Seção Gama

Texto da seção gama, incluindo a frase-chave: "a chuva parou antes do
meio-dia".
Fecho da seção gama, sem nada de especial, só para fechar a terceira
seção do monólito de brinquedo.
