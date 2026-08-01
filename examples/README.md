# examples/

## `sample-dossier.html` — o dossiê de referência

Abra este arquivo antes de escrever qualquer dossiê. É a **barra física** que o gate de
render manda consultar no ato do render, e o motivo de ela existir é um modo de falha concreto:
um dossiê já foi escrito a partir de contagens agregadas, saiu raso, e
o contrato em prosa não segurou. Uma referência aberta na tela segura.

**É material 100% sintético.** Empresa (Meridian), números, conselheiros e citações são
inventados. Os conselheiros são **arquétipos fictícios** de propósito — um exemplo público
não deve fabricar citações atribuídas a pessoas reais.

## O que este exemplo demonstra

| Onde | O que observar |
|---|---|
| §0 | 5 parágrafos densos que **antecipam a recomendação** em vez de suspendê-la para o fim |
| §1 | convergência com o mecanismo do dano em prosa, não só a contagem de quem concordou |
| §2.1 | fork contestado: os dois lados defendidos **na voz de quem os defende**, com custo de errar por lado |
| §2.2 | fork **condicional** — sem 🐂/🐻, com pré-condição e gatilho explícitos |
| §3.1 | item que apareceu numa lente só e **sobreviveu à refutação** — e por isso pesa mais, não menos |
| §4.4 | a anti-tese atacando o **enquadramento**, não a conclusão |
| §5 | notas rotuladas como sinal fraco, com o espalhamento valendo mais que o nível |
| §6.4 | sugestões com mecanismo, dono e gate — não uma lista de verbos |
| §7 | o que foi descartado, onde o dossiê é fraco, e o que a refutação mudou |

## Regenerar

```bash
bin/high-stakes render_gate    examples/sample-dossier.md   # exit 0 obrigatório
bin/high-stakes render_dossier examples/sample-dossier.md examples/sample-dossier.html
```

**Nada aqui pode conter dado real** — empresa, receita, cliente ou nome de conselheiro de
verdade.
