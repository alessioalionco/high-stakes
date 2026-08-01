# Contrato de output — taxonomia A–F + render §0–§7 (core neutro)

> Tipa o que o board ENTREGA (6 formas A–F, escolhidas na devolutiva do Gate B — fluxo v2) e como isso vira o RENDER
> personificado (esqueleto fixo §0–§7). Harness-neutral: o core fixa o CONTRATO; o adapter gera o HTML
> físico. O resumo que
> alimenta este render obedece o contrato lossless de `core/methodology.md` §3f.

## Camada 0 — a unidade atômica é o ITEM (card)
A unidade de output é o **item/card** (cada fraqueza, pergunta, premissa, força — com suas tags). Os
headlines são **views agregadas por cima dos cards**, não uma unidade separada. O card individual é o
que o humano valida no gate ("objeção real ou artefato de LLM?") e o que o loop subtrai.

**Espinha (Decision Quality — Stanford/SDG):** todo item ameaça 1 dos 6 elos → transforma "tem buracos"
em "ONDE a decisão está frágil": 1 Frame (assento da anti-tese) · 2 Alternativas · 3 Informação (missing
evidence + investigar) · 4 Valores/trade-offs · 5 Raciocínio · 6 Comprometimento. *Uma decisão é tão
forte quanto o elo mais fraco da corrente.*

**Tipo do item (pela AÇÃO):** flaw→corrigir · objection→preempt · assumption→testar ·
open_question/unknown→**investigar** · missing_evidence→aterrar · risk→mitigar · dud→cortar ·
**strength**→liderar/proteger · keep→não-over-investir · **indiferente/ruído**→cortar (o emagrecedor).

**⚠️ Trava epistêmica:** o board é MENOS confiável pra CONFIRMAR o que está certo do que pra achar o que
está errado (confirmar = a direção que agrada o proxy/Goodhart). Logo o **positivo sai rotulado como
MENOR-confiança** — hipótese sobre o que funciona, registro de feedback, nunca veredito validado igual
às fraquezas.

**Atributos (5 tags por card):** decision_impact (deal-breaker/material/cosmético) · groundedness
(ancorado-em-evidência vs palpite · checável-vs-subjetivo) · consenso_vs_contestado (nº de lentes +
spread) · actionability + custo · proveniência + viés do assento.

## Camada 1 — a taxonomia de 6 formas de output (A–F)
Todo caso é um combo. A devolutiva do Gate B (`core/sections/interactive-gates.md`; default do
arquétipo no quick, ratificada no cheio) escolhe as formas; elas tipam o CONTEÚDO dos slots do render.

| Forma | O que é |
|---|---|
| **A** Vereditos | binário/categórico ("daria o term sheet?") |
| **B** Quantidades | **sempre faixa, nunca ponto** (valuation range) |
| **C** Lista de mudanças ranqueada | as N sugestões acionáveis, rankeadas |
| **D** Protocolos/forks | mutuamente exclusivos + pré-condição |
| **E** Red-flags / needs-human | deal-breakers + limites da autoridade do board |
| **F** Perguntas a levar | quando o board não é a autoridade final |

## Camada 2 — o esqueleto FIXO do render (§0–§7)
Estrutura fixa, **numeração hierárquica §N.M em TODO item** (âncoras + cross-refs — drill-down
conversacional: "no 2.3, fiquei com dúvida X"):

- **§0 Resumo executivo** — 5+ parágrafos densos, fatos em bold, antecipa a recomendação + como-ler (com a ressalva de que erros se correlacionam entre modelos parecidos).
- **§Escopo (E1-E4):** E1 dimensões de avaliação + RESULTADO por dimensão · E2 insumos fornecidos · E3 o que os conselheiros PEDIRAM e faltava (→ alimenta a agenda) · E4 método em 1 linha.
- **§1 Convergentes:** matriz de checkmarks (peso = conselheiros DISTINTOS, não células) + até 3 quotes/item + mecanismo-do-dano em prosa + ressalva de correlação de erros.
- **§2 Forks:** por fork — contexto + ensaio 🐂 + ensaio 🐻 (até 3 quotes cada) + por-que-divergem + custo-de-errar-por-lado + o-que-resolve (linka à agenda) + pré-condições.
- **§3 Únicas por conselheiro:** item + tags + até 3 quotes + por-que-importa + testabilidade. *(Balde de maior valor esperado — os itens decision-changing vieram daqui.)*
- **§4 Conselho:** por conselheiro — 1 parágrafo de tese (50% maior) + até 5 perguntas + até 5 sugestões + score strip nas dimensões (E1). Quotes verbatim. Spread = sinal, nível = peso fraco.
- **§5 Agenda de investigação:** tabela-resumo + cada item aberto (o que é / por que precede / qual teste resolve / o que destrava).
- **§6 Síntese do Chairman (NO FINAL):** 6.1 convergências · 6.2 divergências sequenciáveis · 6.3 veredito coletivo (dimensões do caso) · 6.4 as sugestões DETALHADAS (mecanismo+como+dono/gate, agrupadas Higiene/Prova/Narrativa/Processo) · 6.5 as perguntas do Chairman (com porquê) · **6.6 guardrails/triggers** (casa canônica da forma E agregada).
- **§7 Apêndice:** descartados-e-porquê · honestidade-de-método · drill-down aos cards crus.

**Físico** (responsabilidade do adapter): single-file HTML, medida de doc (~880px), dark mode, nav
sticky, @media print (⌘P → PDF), groundedness renderizada (**borda sólida = verificado, tracejada =
claim/suprimido**), zero dependência externa.

## Camada 3 — o mapa A–F → § (a costura)
O esqueleto §0–§7 **nunca muda**; o contrato A–F tipa o CONTEÚDO dos slots. O backward generator da devolutiva
gera a montante (assentos, régua, agenda); no render ele só parametriza.

- **A/B → E1 + Tier 0 + §6.3 + score strip §4.** As dimensões E1 SÃO o contrato A/B tipado. Dimensão tipo-B rende **FAIXA em todo slot, nunca ponto**; faixa coletiva do §6.3 = envelope das faixas dos conselheiros, spread = sinal.
- **C → §6.4** (matéria-prima: sugestões do §4; kill-list/cortar-repensar como views). A numeração 1-N é RANK do Chairman (impacto×custo); Higiene/Prova/Narrativa/Processo = tags secundárias. O "15" do sample é calibre do caso, não invariante.
- **D → §2 + Tier 0 + §6.2.** §2 admite DOIS tipos:
  - **fork contestado** (board diverge): aparato completo 🐂/🐻 + por-que-divergem + custo-por-lado.
  - **fork condicional** (board CONVERGE no branch; a pré-condição está no MUNDO, não no board): rende pré-condição + branches + trigger, **sem 🐂/🐻**, peso citado como convergente. **Fabricar bear onde não houve divergência é rigor theater.**
- **E → tags `deal-breaker`/`flaw` (§1–§3) + tabela de guardrails/triggers §6.6 + 🚩 na agenda.** Casa agregada canônica = §6.6.
- **F → roteada por destinatário:** §4 (o que a lente aprofundaria) · E3→§5 (unknowns→teste) · §6.5 (decisor, incl. pré-registro).
- **Marcador `needs-human`:** item §5 ou pergunta §6.5 cuja resolução exige **autoridade humana externa** (médico, advogado, o investidor real) leva o marcador — o board declara o limite da própria autoridade. Cobre a metade needs-human de E e a condição definidora de F.

**Invariante:** forma ausente do contrato → o slot **colapsa com nota de 1 linha** ("contrato sem C —
sem lista ranqueada"), **nunca some em silêncio** nem é preenchido por inércia.

## Personificação (regras de render)
1. **Identidade = persona; modelo = parêntese.** "The Unit Economist (via Opus 4.8)". Conselheiro é a lente; modelo é qual cérebro rodou. *(A atribuição só aparece no RENDER — na visão-de-julgamento o card é ID opaco, `core/methodology.md` §3e.)*
2. **Peso conta CONSELHEIROS distintos, não células.** 4 modelos da mesma persona = 1 lente, não 4 votos.
3. **Quote do conselheiro = trecho verbatim do card cru** (drill-down mantido). No merge, vence a quote mais ESPECÍFICA.
4. **Epígrafe em voz própria** (quote aforística verbatim, NUNCA gerada na síntese) + **fecho-veredito** em bold por bloco de conselheiro.
5. **Antítese RENDERIZADA, não rodada:** o fork já É a antítese; justapor as quotes reais das células independentes (🐂/🐻). Debate real entre células segue proibido: célula que lê célula converge, e convergência induzida não é sinal.
6. **Notas COM spread como sinal + rótulo "peso fraco":** o spread entre conselheiros é sinal real (fork detectado); o nível absoluto é caricatura — personas diferentes pontuam quase idêntico — e vai rotulado como tal.
7. **Rodapé honesto:** "conselheiros são personas sintéticas — a assinatura é da lente, não do humano real que a nomeia."

## Profundidade (o digest EXPANDE dos cards, não resume)
O output custa mais que deep research e deve ser MAIS fundo: cada convergente = 2-3 parágrafos
(mecanismo do dano, nuance, fix e o que ele não resolve); cada fork = contexto + ensaio bull + ensaio
bear + por-que-divergem + custo-de-errar-por-lado + o-que-resolve; cada única = análise + testabilidade;
cada conselheiro = parecer na voz da lente. TODA afirmação carrega número/fonte/confiança. O Chairman
SINTETIZA as células da lente (não inventa); quotes sempre verbatim.

## Gate de render — roda ANTES de entregar o dossiê (não pular)

> **Este gate existe por causa de um modo de falha concreto.** Um dossiê foi
> escrito a partir das contagens agregadas em vez dos cards, saiu raso, e vazou jargão de
> engenharia no texto entregue ao decisor. O contrato em prosa já proibia as duas coisas e não
> segurou — por isso aqui há barra mecânica, não só instrução. O princípio aplicado ao próprio
> motor: **verificar significa evidência, não confiança.**

**R1 — Releitura obrigatória no momento do render.** Antes de escrever a primeira linha do
dossiê, reler esta seção inteira e ABRIR um dossiê de referência (a barra física; o caminho
concreto vem do adapter). Ter lido o contrato lá atrás, nos gates, NÃO conta — horas e um contexto
inteiro separam os dois momentos, e é no render que a barra precisa estar na frente dos olhos.

**R2 — Fonte obrigatória = cards crus.** O dossiê se escreve DOS CARDS (drill-down aberto por
item), nunca só dos agregados/tallies. Tallies dão o esqueleto (pesos, flips, medianas); a carne
(mecanismo, nuance, quote) vem do texto integral das células. Se uma seção foi escrita sem abrir
os cards correspondentes, ela está errada por construção — mesmo que pareça boa.

**R3 — Idioma do decisor.** O dossiê é para quem DECIDE, não para quem construiu o motor.
Códigos internos — de experimento, de mecanismo, de item de evidência, de decisão — são
**proibidos no corpo**. Ou a ideia é dita em português claro, ou o termo entra glosado na primeira
ocorrência. Os avisos de método continuam obrigatórios (que erros se correlacionam, que notas são
caricatura), mas ditos em linguagem de gente. O verificador mecânico reprova por FAMÍLIA de código,
não por lista de instâncias: uma lista de instâncias apodrece assim que alguém inventa o código
seguinte.

**R4 — Checklist mensurável (pisos = os definidos no formato de referência; o sample define o teto —
o gate nunca aperta a barra definida por conta própria):**
- §0: ≥5 parágrafos densos de PROSA (lista não conta), fatos em bold, antecipa a recomendação +
  como-ler.
- §1: cada convergente ≥2 parágrafos de prosa + **≥1 quote verbatim atribuída** (definido:
  "1-2 quotes de referência"; a mais ESPECÍFICA vence — nunca encher pra pontuar) + resultado da
  refutação quando houver; matriz de peso por conselheiro presente.
- §2: cada fork CONTESTADO com os DOIS ensaios (🐂 e 🐻) + ≥1 quote por lado + por-que-divergem +
  custo-de-errar-por-lado + o-que-resolve. Fork CONDICIONAL: sem 🐂/🐻, com pré-condição+trigger,
  **marcado explicitamente com a frase "fork condicional"** no heading ou no bloco de contexto
  (é o marcador que o verificador lê; palavra solta não isenta).
- §3: cada única com análise + por-que-importa + testabilidade.
- §4: cada conselheiro com epígrafe verbatim + parecer ≥1 parágrafo NA VOZ + perguntas e
  sugestões presentes (até 5 cada — teto, não piso; nunca fabricar pra completar) +
  score strip + fecho-veredito em bold.
- §6.4: cada sugestão ≥400 chars com mecanismo+como+dono/gate (calibre de referência ~550c).
  §6.5 e §6.6 presentes como headings próprios.
- §7: descartados-e-porquê + honestidade-de-método + drill-down.

**R5 — Validação mecânica obrigatória.** Rodar o **verificador estrutural apontado pelo adapter**
e obter **exit 0** antes de entregar. Gate vermelho =
corrigir e re-rodar; entregar com gate vermelho é violação de contrato, não julgamento editorial.
O verificador é o piso (estrutura + jargão por família de código); R1-R4 seguem valendo no que
código não mede (voz, nuance, altitude) — a fidelidade das quotes É medida por código, no R6.

**R8 — O marcador viaja COM a atribuição.** Toda quote atribuída carrega, **na própria
linha**, o marcador `(lente simulada · <modelo>)`:

```
> "texto da quote." — **The Unit Economist** (lente simulada · GPT-5.6 Sol)
```

> A regra R7 protege o DOCUMENTO; ela não protege o FRAGMENTO. Uma quote recortada para um
> slide, um print ou uma mensagem sai sem o §Escopo — e o que sobra é uma frase com
> tipografia de citação, atribuída a alguém que existe de verdade. As políticas de uso dos
> provedores de modelo descrevem esse caso quase literalmente: atribuir conteúdo de modo a
> **enganar sobre a origem**. Onde há divulgação explícita, elas não se aplicam; a
> divulgação precisa estar onde o leitor está.
>
> O antigo `(via <modelo>)` continua sendo aceito pelo verificador de quotes, para não
> quebrar dossiês já gravados — mas não satisfaz esta regra: "via" identifica o modelo, não
> avisa que a pessoa é simulada.

**R7 — Declarar que as personas são simuladas.** O §Escopo carrega, obrigatoriamente, uma
frase dizendo que os conselheiros são **lentes simuladas por modelos de linguagem, que NÃO
SÃO AS PESSOAS REAIS**, e que nenhuma frase atribuída a elas foi dita por elas.

> Não é formalidade jurídica: é consequência do próprio formato. As lentes levam nomes de
> pessoas de verdade, a atribuição `— **Nome**` usa a tipografia de citação real, e o
> dossiê **circula** — vai para reuniões, para pessoas que não sabem o que é este motor. A
> regra R6 garante que a quote é verbatim da CÉLULA; ela não garante nada sobre a pessoa.
> Sem a declaração, entrega-se uma garantia forte sobre a coisa errada.
>
> O `(via <modelo>)` na atribuição não substitui isto: lê como metadado de engenharia, não
> como aviso. O verificador mecânico reprova o dossiê sem a frase.

**R6 — Quotes verificadas por código.** Quando as células cruas existem (sempre, num run real),
TODA quote atribuída e toda epígrafe passa pelo verificador de quotes: verbatim contra o card do
conselheiro a quem foi atribuída, exit 0 obrigatório. Quote não-verificada não chega a quem decide
— corrige para o verbatim ou remove.

> Ao verificar um dossiê pronto, **18 de 35 quotes falharam**: cortes que mudavam
> o sentido, emendas entre trechos distantes, e uma frase inteira acrescentada a uma epígrafe.
> Nenhuma alteração tinha sido intencional. É por isso que esta regra é código e não recomendação.


## Em aberto
Não construídos, e portanto não devem ser apresentados como existentes: schema JSON do card ·
cômputo determinístico dos headlines · versionamento de card ao longo do loop · o tipo
`indiferente` no mapeamento.
