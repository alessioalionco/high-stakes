---
name: high-stakes
description: "Modo High Stakes: motor de rigor para DECISÃO de alto risco e ambígua (deck/slide para investidor, board ou cliente; narrativa; posicionamento; decisão estratégica). Refina o pedido com um brief pré-preenchido, aterra os inputs na verdade, roda um painel adversarial cego (personas × modelos de famílias diferentes) sobre cenários contrafactuais, refuta o próprio consenso, e devolve um dossiê com quotes verificadas por código. Use quando o usuário disser 'entra no modo high stakes', 'modo high stakes', 'high stakes', ou ao pedir um artefato/decisão que vai para fora e é caro de refazer."
---

# Modo High Stakes — adapter

> Este arquivo é o **adapter**: gatilhos, cola e os caminhos desta instalação. A
> metodologia inteira vive no core, que é neutro de harness. **Este adapter não duplica o
> motor — ele aponta para ele.**

## O core (leia estes arquivos — não trabalhe de memória)

O core viaja dentro do pacote Python. Descubra onde ele está:

```bash
<raiz-do-plugin>/bin/high-stakes paths core
```

> **A raiz do plugin** é dois níveis acima deste arquivo (este é
> `<raiz>/skills/high-stakes/SKILL.md`). Use `${CLAUDE_PLUGIN_ROOT}` se o harness a
> expuser. **Sempre invoque pelo `bin/high-stakes`**: `python3 -m high_stakes.X` só
> funciona se o pacote já estiver no `sys.path`, o que é falso numa instalação limpa.

**Antes de executar cada passo, leia a seção correspondente.** É instrução dura: ler no
começo e trabalhar de memória depois é como se produz um dossiê raso.

| Quando | Leia |
|---|---|
| Sempre, na ativação | `methodology.md` — os 3 órgãos, floor-check, cegamento de marca, síntese sem perda |
| Nos gates | `sections/interactive-gates.md` — Gate A/Gate B, presets rápido×cheio, custo |
| Na devolutiva e no render | `sections/output-contract.md` — taxonomia, mapa §0–§7, o gate de render |
| Ao gravar uma decisão | `sections/run-persistence.md` — layout, material sensível, manifesto |
| Ao disparar chamadas pagas | `execution.md` — capacidades, provedor, degradação, custo |

## Modos de entrada

- **Problema NOVO** → 2 gates. Gate A: perguntas essenciais + materiais + agenda de
  pesquisa. Gate B: brief afiado + composição do board + devolutiva padrão + roster + custo
  estimado → GO.
- **Problema JÁ TRABALHADO** ("carrega o problema X") → recarregar o run gravado
  (brief, board, roster, dossiê, ledger) e oferecer o menu: nova rodada · run rápido ·
  aprofundar um item · registrar o desfecho real · encerrar.
- **Preset rápido** (tema recorrente): 3 lentes + generalista, júri de 3, cenário único.
  **Preset cheio** (inédito ou irreversível): 5–7 lentes, júri de 4, os 2 gates.

## Caminhos e comandos desta instalação

```bash
bin/high-stakes config          # config efetivo + de onde cada coisa veio
bin/high-stakes paths core      # contratos       (dentro do pacote)
bin/high-stakes paths boards    # lentes que vêm na instalação
bin/high-stakes paths examples  # o dossiê de referência que a regra R1 manda abrir
```

- **Roster de modelos:** `bin/high-stakes config` mostra o `pin_path` em vigor. O
  arquivo do usuário (`$HIGH_STAKES_HOME/roster-pin.yaml`, padrão `~/.high-stakes/`) ganha
  do que vem embarcado. **Congela dentro de um loop** — trocar juiz no meio mata a
  comparação entre rodadas.
- **Onde a decisão é gravada:** `runs_dir` do config (padrão `./high-stakes-runs`).
- **Pool de lentes:** `boards_dir` do config. Quando o board for formado do zero, ofereça
  salvar o pool ali para reuso.
- **Chave de API:** `OPENROUTER_API_KEY` no ambiente. Nunca no config, nunca no repo.

## Quando ativar / NÃO ativar

- **Gatilho explícito:** "entra no modo high stakes", "modo high stakes", "high stakes".
- **Auto-sugerir** (perguntando antes) só quando os TRÊS batem: stakes altos (vai para
  fora ou é caro de refazer) · ambiguidade real (decisão de gosto/julgamento, não de fato)
  · contexto que está na cabeça do usuário e não dá para inferir do repositório.
- **NÃO ativar → redirecionar:** tarefa mecânica ou de baixo risco → executar direto com
  defaults e mostrar a suposição · código, build ou config → o pipeline de engenharia
  normal. Nunca virar questionário em branco.

## Guardrails

### O render do dossiê passa por gates de código

As regras moram no core (`sections/output-contract.md`, seção do gate de render) e devem
ser **relidas no ato do render** — ter lido no começo do fluxo não conta. Os três
comandos, todos com exit 0 obrigatório antes de entregar:

```bash
bin/high-stakes render_gate    <report.md>              # estrutura §0–§7 + jargão
bin/high-stakes qverify        <report.md> <cells_dir>  # toda quote é verbatim
bin/high-stakes render_dossier <report.md>              # HTML single-file
```

**Toda quote atribuída leva `(lente simulada · <modelo>)` na própria linha**, e o §Escopo
carrega a declaração completa. A primeira protege o fragmento recortado; a segunda, o
documento. O gate reprova sem qualquer uma das duas.

**O §Escopo declara que as personas são simuladas.** As lentes levam nomes de pessoas
reais e a atribuição `— **Nome**` tem a tipografia de citação real — e o dossiê circula. A
verificação de quotes garante fidelidade ao que o MODELO escreveu naquela lente, nunca que
a pessoa disse aquilo. Sem a declaração, o gate reprova.

O dossiê é escrito **a partir dos cards brutos**, nunca de contagens agregadas. Esta é a
falha que originou o gate: um dossiê montado de tallies perde a voz dos conselheiros e
vira relatório técnico ilegível.

### Mecanismo sem build → DECLARAR e degradar, nunca simular

Onde um mecanismo descrito no contrato não estiver construído, **declare a degradação
explicitamente** e siga. Jamais apresentar um contrato como se o build existisse, e jamais
fingir que um passo rodou.

### O painel é ferramenta de estresse, não oráculo

O motor mede como uma decisão **resiste a ataque**, não prevê como uma sala reagirá. A
lente cética roda sempre — inclusive quando a audiência é amistosa. Um painel calibrado
para agradar não tem valor de teste.
