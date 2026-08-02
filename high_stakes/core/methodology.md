# High Stakes — metodologia (core neutro)

> **Status: v2.1 (core neutro).** Corpo migrado do adapter para estrutura
> neutro de harness. Este arquivo é o **motor**: os 3 órgãos, o
> fluxo, a formação do board + floor-check, o brand-blinding real e o contrato lossless do digest.
> É **self-contained** e só referencia outros arquivos DENTRO de `core/` (R4). O harness (Claude Code,
> shim futuro) é um **adapter fino** que faz o glue e aponta os paths da instância.
>
> **Princípio-mãe: "checking means evidence, not confidence"** — output confiante-e-errado é o risco
> #1; é um loop-com-barra pra decisão. É um **red-team adversarial estruturado**, NÃO um oráculo de
> resultado — acha fraqueza + sinal RELATIVO, nunca forecast absoluto. O gstack faz isso pra código;
> este faz pra decisão.
>
> **O que foi medido, e o que não foi.** O aparato passou por um teste feito para matá-lo: um
> modelo forte e bem municiado contra o painel de personas. O painel sobreviveu — produziu itens
> acatáveis que o baseline não achou, um deles capaz de mudar a decisão. Mas o resumo enxuto venceu
> na FORMA. É n pequeno, medido por quem construiu o motor: leia como sinal, não como prova.
>
> As consequências operacionais dão forma ao resto deste documento: **consenso não agrega verdade**
> (modelos parecidos erram junto) · **nota de persona é caricatura** (lentes diferentes pontuam quase
> idêntico — o sinal está no CONTEÚDO dos cards, nunca no número) · **evidência calibra mais do que
> descobre** · o valor do painel é **precisão e filtragem**, não criatividade. E o gargalo é o
> resumo, não o motor.

## Como o core se lê (instrução dura, não trabalhe de memória)

Cada passo do fluxo aponta pra a seção do core que o governa. **Antes de executar um passo, LEIA a
seção correspondente — não trabalhe de memória.** As seções:

- **`core/sections/interactive-gates.md`** — fluxo v2 (Gate A/Gate B pra problema novo · menu recorrente) + presets quick×cheio + custo/egress + cascata.
- **`core/sections/output-contract.md`** — a taxonomia A–F da devolutiva + o mapa A–F→§0–§7 do render + `needs-human`.
- **`core/sections/run-persistence.md`** — onde cada decisão real grava em disco (layout, knob sensível, manifest com hashes).
- **`core/execution.md`** — o contrato de execução: capacidades exigidas do harness, OpenRouter, degradação, custo.

## Quando ativar
- **Trigger explícito:** "entra no modo high stakes", "modo high stakes", "high stakes".
- **Auto-sugerir** (perguntar antes de ligar) quando os TRÊS gatilhos batem:
  1. **Stakes altos** — vai pra fora (investidor, board, cliente) ou é caro de refazer.
  2. **Ambiguidade real** — várias interpretações válidas, taste-driven.
  3. **Contexto na cabeça de quem decide** — não dá pra inferir do material disponível.

## NÃO ativar (redirecionar)
- Tarefa mecânica / já-especificada / baixo risco → executar direto com defaults e **mostrar a suposição**, sem brief.
- Código / build / config → **pipeline de engenharia** (investigate→plan→implement→review→ship).
- Nunca virar questionário em branco. Se não há contexto faltando, não pergunte.

---

# O fluxo: 3 órgãos

```
FLUXO v2 (2 gates; ver core/sections/interactive-gates.md):
Gate A: perguntas ★ pré-preenchidas + pedidos de material + AGENDA DE RESEARCH DO MODERADOR
        (crença-alvo SÓ em artefato de persuasão; regra de novidade: tema novo → research
        completa; repetido dentro da validade → cache)
   ↓ usuário devolve respostas + materiais
Gate B: brief afiado + board + devolutiva default do arquétipo + roster do PIN + custo → GO
   ↓ (sem mais paradas)
Órgão 2: ATERRA os inputs (kill-switches automáticos) + BLOCO DE EVIDÊNCIA
Órgão 3: painel adversarial CEGO (matriz (N+1)×M) × cenários (opcionais, modo cheio)
         → refutação (família externa) → síntese de 3 camadas → dossiê verificado por código
Recorrente: carregar decisão do disco → menu (loop/quick/drill-down/outcome/encerrar)
Presets: QUICK (3 lentes+generalista · M=3 do pin · agenda do moderador · 1 gate) ×
         CHEIO (5-7 lentes · M=4 · pre-pass dos conselheiros se domínio novo · 2 gates)
```

O **formato como cada passo é EXIBIDO** (headings, numeração, gates) vive em
`core/sections/interactive-gates.md`. Aqui está a METODOLOGIA (o que cada órgão faz e por quê).

## Órgão 1 — Brief pré-preenchido (premissa)

Preencher cada campo com o que já se sabe do material e da conversa; marcar com ★ só o que falta e que
**move o teto**. Os 6 campos:

1. **Crença-alvo** — a UMA frase que o leitor/decisor deve levar. Proponho um default; peço pra afiar. (muda uma palavra, muda o frame)
2. **Quem está na sala + no que indexa ★** — decisor(es), o que historicamente compram/valorizam, portfólio relevante. *(Vira o roster do painel no Órgão 3.)*
3. **Vizinhos do artefato ★** — o que vem antes/depois (títulos/função), pro handoff.
4. **O que a DD/validação externa vai confirmar ★** — quais clientes/refs serão consultados e a frase mais forte de cada. Destrava "o leitor conclui sozinho".
5. **Benchmark competitivo** — contra quem vai comparar (default: concorrentes óbvios).
6. **Liberdade + restrições** — quebrar a estrutura? formato/tamanho? marca agora ou depois? claims proibidos?

**Mínimo viável:** campos **2, 3, 4 + confirmar 1**. O resto roda no default (e eu digo qual usei).
Apresentar como prosa pré-preenchida com os ★ destacados — nunca uma parede de perguntas.

## Órgão 2 — Aterrar os inputs na verdade (GATE, o que define a honestidade)

**Antes do painel.** Score sintético sobre número falso = otimizar um deck lindo apoiado em mentira.
Cada número/claim do artefato carrega `{valor, fonte, status}`:
- **aterrado** — reconciliado com a fonte canônica de verdade (dados financeiros, base própria). Entra.
- **não-verificado** — sem fonte → marcado, NÃO vira premissa.
- **fabricado-suspeito** — contradiz a fonte → **para e levanta**.

**Kill-switches (load-bearing):**
- número não-aterrado → **recusa rodar o painel** sobre ele (sinaliza, não fabrica).
- claim sem fonte → "não-verificado", não premissa.
- contradição com a fonte canônica → para.

*(Exemplo do formato: "reconciliar a métrica de retenção com a fonte financeira canônica; NÃO
fabricar percentual de parceiro, prazo de payback nem benchmark de mercado".)* É o órgão mais
difícil de generalizar — depende de existir uma fonte canônica de verdade. Quando ela existe, é
exigível; quando não existe, o número não aterra e o dossiê tem de dizer isso.

### Pre-pass do board — define a agenda de evidência (antes da pesquisa rodar)
> ⚠️ **v2: o DEFAULT da agenda é o MODERADOR** (geradores backward + benchmark, no Gate A) — o
> pre-pass dos conselheiros (forward) roda só no modo CHEIO em domínio novo, onde a 3ª camada de
> "não sei o que não sei" paga o custo/latência. Quando rodar, vale o abaixo.
> ⚠️ **Ordem:** a formação do board (§3a) e o preset (§3a-bis) **sobem pra cá** — o board precisa existir
> pra ser consultado. Forme o board logo após o brief.

Passe **LEVE e cego** (cada member 1×, modelo único — objetivo é a UNIÃO dos pedidos, não medir
divergência; a matriz cheia fica pro julgamento). Pergunta a cada board member:
- **(a)** que evidência/refs/fatos você precisaria ver pra avaliar?
- **(b)** sobre que dimensões você julgaria isso? *(alimenta o bloco de scorecard)*

Os pedidos de (a) vão pra **dois destinos**:
- **→ deep-research/search:** "valor médio do m² na região", "benchmark de S&M efficiency", "estudos clínicos de XYZ".
- **→ o usuário:** fatos privados — "qual sua renda? perfil familiar?" — que alimentam o grounding do Órgão 2 (o board diz qual fato falta, em vez de eu adivinhar).

Dedup + **prioriza por nº de members que pediram** + **teto de budget de pesquisa**. Cada pedido é
**roteado pra a natureza certa** (ver bloco de evidência); pedidos sem resposta alimentam o **crítico de
completude**. **Roda cego à crença-alvo** (firewall §3a). É a 3ª camada da defesa "não sei o que não
sei" (benchmark do orquestrador → board define a agenda → board surfa gaps no run).

### Bloco de evidência (parte do Órgão 2)
**Roteador por NATUREZA, não 2 tiers de profundidade** (profundidade rápido/deep é eixo ortogonal).
**5 naturezas**, cada uma fonte/confiança/forma própria:
| Natureza | Fonte | Confiança |
|---|---|---|
| Acadêmica/científica | PubMed/Semantic Scholar/Scholar | peer-review + citações |
| Benchmark de indústria | Gartner/Forrester/SaaS benchmarks | reputação do analista (⚠ vendor-sponsored) |
| Dado estruturado | APIs/DBs: FipeZap/Crunchbase/IBGE | proveniência do dado |
| Atual/notícia | web recente | recência + veículo |
| Privada/interna | dados próprios e documentos injetados pelo usuário | máxima (passa pelo gate) |

Pack = **material bruto compartilhado IDÊNTICO com todas as células** (divergência no julgamento, não
nos fatos). Cada item: `{natureza, fonte, tier-confiança, timestamp+meia-vida, bruto-vs-sintetizado,
conflita-com}`. **Travas:**
- **Bruto + síntese com a linha:** síntese SOBRE a evidência OK, **sobre o artefato/decisão NÃO**; toda afirmação linka a primária (atravessável) + tag; painel julga contra as primárias; **grounding só conta a primária**.
- **Conflitante = ambos + flag** (divergência de evidência é sinal; nunca escolher em silêncio).
- **Hierarquia de confiança** (painel pesa por ela): primária/peer-reviewed > analista/estatística oficial > imprensa > vendor/sponsored > blog/fórum. **Flag forte** em tier-baixo/contestado; **tier-baixo NÃO aterra número**.
- **No-leak default + ask-gate:** query externa **abstrai** (nunca nosso número); pra mandar trecho sensível, **mostro o que vou enviar e peço OK**; fatos privados ficam internos. *(O gate de egress é formalizado em `core/sections/interactive-gates.md`.)* ⚠️ **"sensível → só provider no-retention" saiu daqui:** é promessa sem mecanismo — o motor não consulta a política de retenção de provedor nenhum. Está no roadmap do `execution.md`. E não há filtro de conteúdo na saída: existiu uma denylist de termos, foi **removida** de propósito (o porquê está no cabeçalho de `high_stakes/evidence.py`). A trava que resta é humana, e é o Gate B.
- **Agenda = 3 geradores (v1.7):** forward (board pede no pre-pass) + **backward (estrutura da decisão/claims — o que é logicamente necessário saber, independente do que o board pediu)** + benchmark do orquestrador.
- **Loop de auto-verificação de fontes (v1.7) — ⚠️ NÃO CONSTRUÍDO:** o LLM fabrica fontes que parecem reais (link morto / que não sustenta o claim) e fica confiante. O desenho: a evidência se auto-verifica como loop — abre cada fonte, confirma que sustenta o claim, descarta fabricada/morta, busca substituta, só para quando tudo confere. **Nada disso roda.** O que o motor faz hoje é COLETAR a citação e classificar o domínio por tier (`evidence.py`); ninguém abre a fonte nem confere se ela sustenta o claim. Enquanto não existir, a conferência é sua — e uma citação de tier alto continua podendo ser inventada. Está no roadmap do `execution.md`.
- **Crítico de completude (checklist):** depois do pack, antes do painel — checa os **3 geradores** sem resposta → **gaps a você** (anexa/aceita), não auto-preenche. Generalista = backstop no run.
- **TTL por natureza no loop:** meia-vida por natureza (m² dias-semanas · notícia curtíssima · benchmark ~1ano · acadêmica anos); re-run só re-busca o que venceu (caching por-item).
- **Regra de NOVIDADE (v2, palavras do decisor):** research completa dispara quando "o tema é novo
  e há risco de ficar conhecimento de fora"; tema repetido dentro da validade → cache. Packs de
  conselheiro com corpus ESTÁVEL (livro-só) usam delta-mode barato (frames ativadores, sem research
  pesada); research pesada fica pros corpus vivos/falados.
- **Acoplamento:** a natureza-default é prevista pelo arquétipo (médico→acadêmica, deck→benchmark+dado, proxy→buyer-studies), ajustável pelo pre-pass.
- **Perguntar ao usuário:** *"Quer anexar algum doc pro board? (estudos, dados internos, contexto não-público — ex: Gartner não-indexada)."* → natureza privada, passa pelo gate.

### Bloco de scorecard — *a refinar (debate em aberto; vai ficar mais sofisticado)*
ANTES de rodar o painel: **pesquisa de benchmark → PROPOR as dimensões → pedir input** (ratifica/edita).
O critério vira um **scorecard multi-dimensional**; **perspectiva ≠ persona** (persona = QUEM julga;
perspectiva = sobre QUE eixo pontua).

**Escolher as dimensões — triangular 4 fontes:** (1) prior do tipo de decisão (rubric do mundo:
fundraising, ISO 42001…); (2) a audiência/personas (as lentes do board já são dimensões candidatas);
(3) **benchmark externo** (pesquisa — defesa #1 contra "não sei o que não sei"); (4) os claims do
artefato. Testes: **MECE-ish** (se dá pra maximizar tudo e ainda perder, falta dimensão) + **outcome-linked**.

**Regras travadas:**
- **REGISTRO ABERTO de tipos de resposta** (não lista fixa — *área de aprendizado: "não sei o que não sei"*). Cada tipo carrega: como **emite** · como **agrega** · como calcula o **delta**. Starter: binária (proporção/flips) · ordinal 1-5/1-7 (mediana+spread) · Likert (mediana+top-2-box) · quantitativa $/% (faixa/distribuição) · categórica/nominal (**moda**, sem média) · ranking (mediana de rank) · par-a-par (win-rate) · confiança (mediana) · livre (clusteriza, não agrega). **Princípio durável: a agregação RESPEITA o nível de medição** (nominal→moda · ordinal→mediana · intervalar→média) — vale até pra tipo novo. *(Exemplo: numa avaliação de investimento, "daria o aporte? [sim/não]" + faixa de valor.)*
- **SEM peso, SEM nota composta** — dimensões são incomensuráveis → saída = **vetor por dimensão**, nunca um escalar. Delta por-dimensão, na própria unidade.
- **Escala ancorada** — definir o que 1/3/5 parecem; **5 genuinamente difícil** (artefato atual cai no meio pra discriminar). Sem âncora, o 4 de um modelo ≠ o 4 de outro. **Âncora ≠ peso** (marcação da régua dentro da dimensão, não importância entre dimensões). Eu **rascunho as 3 âncoras**; o usuário **ratifica as dimensões + a âncora do "5"** de cada.
- **Spread é sinal** — média E spread por dimensão; alto-spread = onde está o risco.
- **Delta > absoluto** — uso primário é comparativo (run N vs N+1); o absoluto é termômetro grosso.
- **Rubric TRAVADO por run** (delta comparável); dimensões surfadas pelo painel entram no rubric do run **seguinte** (loop). **Rubrics emergem por decisão — sem biblioteca** (critério é efêmero; o board é que é perene).

**UX = "regras do jogo" + ask aberto** (com proveniência) — no fluxo v2 a régua entra como default do arquétipo no Gate B (shape em `core/sections/interactive-gates.md` §Gate B); ratificação vira conversa só em arquétipo inédito (modo cheio).

## Órgão 3 — Painel adversarial cego + síntese

### 3a. Formar o board (TASK-DRIVEN — arquétipo → skills matrix → ancoragem → composição)
**A formação é SEMPRE dirigida pela tarefa.** O que é perene é a **biblioteca de lentes** (pool por
domínio, mantido na instância pelo adapter), NÃO o board — ele nasce/morre na decisão e **congela
durante o loop** (fresco só por decisão nova, senão o delta v1→v2 compara coisas diferentes).

**Pergunta de abertura = origem do pool:**
> *"Pra essa decisão, uso um grupo/biblioteca que você já tem curado, ou monto o board do zero pra esse problema?"*
> **[A]** pool curado · **[B]** do zero (problema novo; eu proponho).

Ambos caem no MESMO motor. O antigo "co-formado" não é modo — é o **gate de ratificação** (Passo 6), que sempre roda.

**Passo 0 — Classificar o arquétipo** (define o critério de qualificação; maioria é híbrido):
| Arquétipo | Cobre por | Qualifica por | Membros | Ex |
|---|---|---|---|---|
| **Expert/especialidade** | disciplinas necessárias | credencial + reconhecimento-por-pares | complementares | tumor board, imóvel |
| **Adversarial/cético** | jeitos-de-falhar | autoridade-de-eixo | adversariais | deck, plano de CRO |
| **Proxy-de-audiência** | segmentos da persona | **representatividade (NÃO expertise)** | amostras do comprador | landing page |

**Passo 1 — Mapa de cobertura (skills matrix):** listar o que PRECISA ser coberto — disciplinas /
jeitos-de-falhar / segmentos-da-persona. **É onde mora a inteligência** (eixo não-listado = ponto cego
→ job do generalista).
**Passo 2 — 1 assento por item.**
**Passo 3 — Qualificar:** sinal = **reconhecimento-POR-pares** (citado por experts, autoria de
guideline, track record, h-index), **NÃO volume** de produção nem fama. **Fama ≠ autoridade.**
**Passo 4 — Ancorar** (mesma máquina nos 3, muda só o alvo):
- alta densidade nomeada → **name-anchor** (nome = tempero) **+ spec do eixo embaixo** (substância; nome nunca sozinho).
- baixa densidade (local/nicho/regional) → **spec-anchor é o PRIMÁRIO** (de guidelines/dados).
- proxy-de-audiência → **perfil-do-arquétipo** (estudos de comprador e reviews públicas, filtrados) + **camada privada (brain win/loss)** que localiza e mata o estereótipo.

> **Ancorar a persona em material real do conselheiro — medido, NÃO construído.** O padrão
> observado em 2 experimentos: quando o conselheiro é muito documentado, a ancoragem **afia**
> (calibra melhor, atribui melhor, traz o recente); quando é pouco documentado, ela **descobre**
> (aparecem categorias de objeção novas e divergência genuína entre as lentes). Dois experimentos
> não são uma lei — trate como hipótese com evidência a favor. **Como não está construído, não
> simule:** rode sem ancoragem e declare que rodou sem.

**Passo 5 — Composição (cobertura + 3 papéis standing):**
- lentes de cobertura: **3** (simples) → **5** → **7** (complexo);
- **+ generalista ×M** (1/modelo — o eixo esquecido; divergência entre os M = anti-groupthink);
- **+ anti-tese ×1** (ataca a premissa/"é a pergunta errada");
- **bull/bear no eixo-crux** (par no MESMO eixo — não fura ortogonalidade: vetor oposto = alto spread = "o risco mora aqui"; só no crux).
- **Dois botões:** cobertura escala com *complexidade*; profundidade adversarial (bull/bear+anti-tese+M+loop) escala com *risco/reversibilidade*.

**Passo 6 — Gate de ratificação:** mostrar roster + eixos + **viés conhecido de cada assento** +
proveniência → você troca/confirma. Co-form profundo só se audiência-específica ou push-back. *(Viés =
feature: o urologista puxa pra cirurgia, o radio-oncologista cancela.)*

**Firewall:** as células veem o **charter** (o quê/quem/job) + artefato + evidence pack — **NUNCA a
crença-alvo** (fica comigo; senão contamina). O pre-pass também roda cego.

### 3a-bis. Presets — QUICK × CHEIO (v2, 22/Jul; supera o "sempre max" de 02/Jul)
Dois presets, ambos matriz cega `(N+1)×M` com anti-tese, refutador e síntese cega à marca (o que
NUNCA se corta): **QUICK** (tema recorrente/reversível — 3 lentes + generalista, M=3 do pin,
agenda do moderador, cenário único, devolutiva default, 1 gate, ~$1.5-2.5) e **CHEIO** (inédito
e/ou irreversível — 5-7 lentes, M=4 com a 4ª família do pin, pre-pass dos conselheiros se domínio
novo, cenários+dud-screen quando há movimentos a pesar, 2 gates). Tabela completa em
`core/sections/interactive-gates.md`. **Cap hard $15** segue como guarda (harness impõe; ver
`core/execution.md`). A regra de roteamento continua: pergunta de FATO/verificável → 1 modelo sem painel,
sempre explicitando o corte (soberania > economia). A economia estrutural adicional vem do
**caching de prefixo** (material compartilhado primeiro no prompt — ver `core/execution.md`).

### 3a-ter. Roster de MODELOS — PIN com validade + floor-check sob gatilho (v2) [M1]
> **O roster vive num pin da instalação, com validade (~30 dias)** — no gate
> ele é 1 linha de confirmação, não uma pesquisa. O método do floor-check abaixo roda sob GATILHO:
> pin vencido · release relevante · domínio que exige competência que o pin não cobre. **Os
> assentos do pin são decididos POR DADO** (experimento de assentos — mesmas células, candidatos
> lado a lado, contribuição marginal por dólar), não por índice/gosto.

Quando o floor-check roda: **eu pesquiso, recomendo (quantidade + quais), o usuário só aprova.**
Mede QUALIDADE por fonte confiável, não popularidade/spend.

**Método (fontes a cada run):**
- **Piso de inteligência:** AA Intelligence Index (ou equivalente vigente).
- **Competência de domínio:** benchmark do domínio (HealthBench p/ saúde · LegalBench p/ jurídico · finance-bench…) — o piso *deste* arquétipo.
- **Recência:** releases das últimas semanas (pega o modelo novo antes do default envelhecer).
- **Diversidade:** famílias de linhagem distintas acima do piso — **evitando a família do Chairman** (com Chairman de uma família, não colocar um juiz da mesma família: dobra a família → self-preference same-family, medido na literatura de erros correlacionados).

**Quantidade de juízes (M, os modelos — não confundir com N=lentes da matriz) = 3º botão:** M=3
no quick (pin: flagship + 2 baratos de linhagens distintas) → M=4 no cheio/irreversível (soma a
4ª família do pin). Satura em 3 (cobertura 93→99→100%; 4º/5º ≈ +0 e correlacionado); o 4º compra
anti-correlação, não cobertura. O número é ruído; a divergência de decisão é o sinal.

**Composição do PIN:** famílias distintas acima do piso, Chairman de família *fora* das dos juízes
(o floor-check já pegou exatamente esse erro num default anterior: juiz + Chairman da mesma
família). Os slugs concretos vivem no pin da instância, não aqui (senão o core apodrece). O
histórico experimental fixa GLM na família de baixo custo por **comparabilidade** (os experimentos rodaram
nele) — vale pros EXPERIMENTOS, que seguem com roster fixo próprio.

**Invariante (senão quebra o loop):** o roster do pin **congela dentro de cada loop** (v1→v2 exige
os mesmos juízes pro delta valer). Entre decisões, o pin vale até o gatilho (validade vencida ·
release relevante · domínio fora da competência do pin) — aí o floor-check re-roda e o pin é
re-gravado.

### 3b. A matriz (cobertura + papéis standing) × M — CEGA, sem rounds
- **Lentes de cobertura** (cada persona = um EIXO, não um nome famoso; 3→5→7 por complexidade) **+ 3 papéis standing**: **generalista ×M** (anti-groupthink; o eixo esquecido; auto-add, NÃO mora no pool) · **anti-tese ×1** (ataca a premissa) · **bull/bear no eixo-crux** (par no mesmo eixo = alto spread). Ver §3a pra a lógica de formação.
- **Célula = (persona × modelo), 1 chamada PARALELA ISOLADA** (multi-agente — o orquestrador garante o contexto limpo; ninguém se lê; **sem rounds**). ✅ **Verificado no código, e por CONSTRUÇÃO, não por gate:** `build_quick_tasks` monta a mensagem de cada célula a partir de três entradas e nada mais — o material (prefixo byte-idêntico), o sufixo da persona e o ask do arquétipo. Não existe caminho por onde a resposta de uma célula entre no prompt de outra; o único append é o retry de formato, que devolve à célula a resposta DELA mesma. Ressalva honesta: `ask_builder` e `parse` são funções passadas de fora, e **nenhum teste trava esta invariante** — quem amanhã adicionar um "round 2" que realimenta saídas não vai ver nada ficar vermelho. A divergência é o PRODUTO. Aposentar o "1 prompt/modelo com todas as personas" (contamina → mata a divergência-de-persona). *(A capacidade "chamadas paralelas isoladas" é exigida do harness — ver `core/execution.md`.)*
- Preset único: matriz cheia (ver §3a-bis; `value` extinto).

**Schema de output de cada célula — taxonomia de 6 ações + scores** (cada tipo vira uma AÇÃO; tudo é
clusterizado na síntese — 3 board members em 2 modelos pedindo o NRR = ponto cego de alta confiança):

| Output | Ponto cego de… | Ação |
|---|---|---|
| Gostou | (força) | MANTER/amplificar |
| Não gostou | artefato | CORRIGIR |
| Faria diferente | artefato (alternativa) | SUBSTITUIR |
| Gostaria de ver / perguntaria | artefato (conteúdo ausente — caso NRR/GRR) | ADICIONAR |
| Indiferente / ruído | artefato (baixo impacto) | **CORTAR** (raro e precioso) |
| Dimensão faltando | rubric (meta) | RE-PONTUAR (loop) |
| Scores (vetor por dimensão + justificativa + spread) | medição | termômetro + delta |

⚠️ **ponto cego do RUBRIC** (faltou dimensão) ≠ **ponto cego do ARTEFATO** (faltou conteúdo — o board
quis ver o NRR). Generalista = instrumento do 1º; o painel inteiro surfa o 2º. *(A taxonomia de
CONSUMO/render A–F que tipa a devolutiva vive em `core/sections/output-contract.md`.)*

### 3c. Cenários contrafactuais — OPCIONAIS
Rodar o painel sobre VERSÕES alternativas (não só "nota da as-is") → comparação relativa = análise
marginal. **Só quando há movimentos a pesar** ("ache as fraquezas deste as-is" = zero cenário). Rodam
**DENTRO da célula** (o juiz compara; ×1, não ×S; **ordem randomizada** anti-pattern-completion).
- **Quem propõe:** decisor semeia os candidatos + **board propõe os do ponto cego do decisor** (cego à crença-alvo) + decisor ratifica.
- **DOIS RAMOS (depende do arquétipo):**
  - **Variação-de-artefato** (adversarial/audiência): edições CUMULATIVAS → **default BUNDLE** (as-is vs tudo-junto), **sem medir peso individual**. **Dud-screen:** o painel também responde *"alguma mudança você TIRARIA/que piora?"* = **flag binário**; só o flagado roda **isolado** (confirma o dud). *(Sem isso o bundle embarca a mudança ruim: uma edição que PIORA some dentro do pacote.)* Isolação = **só por suspeita**, nunca o power set.
  - **Opção-de-decisão** (expert): forks mutuamente EXCLUSIVOS (cirurgia vs radio vs vigilância) → **colapsa no Mapa de Protocolos (§3f)**, sem mecanismo novo.

### 3d. Passo de refutação (cego) — o LOTE calibra, o POR-ITEM aprofunda
Antes de marcar consenso como blocker/recomendação forte, uma voz de família distinta tenta
**REFUTAR** — independente, não se lê com as outras. Consenso que sobrevive = alta confiança;
refutado → "needs human". **Desenho em 2 estágios (medido no experimento de refutação):**
(1) **LOTE** (claims lado a lado, 1 chamada) — é quem CALIBRA vereditos (exibe os 3 níveis);
(2) **POR-ITEM** (mecanizado no motor) — gerador de PROFUNDIDADE sobre
os itens que viram blocker/fork: concessão obrigatória (anti-advogado), fatos novos checáveis
como produto principal (verificar contra o material antes do dossiê), veredito só SUGERIDO.
⚠️ Viés medido: por-item com papel puramente adversarial dá REFUTADO em ~tudo (8/8 no
experimento) — por isso ele nunca decide veredito sozinho. Em uso, o por-item corrigiu um
erro do próprio Chairman num dossiê publicado.

### 3e. Brand-blinding na visão-de-julgamento — procedimento, não trava [M2]

> ⚠️ **Leia isto antes do resto da seção.** O que está descrito abaixo é o
> **procedimento** que a visão-de-julgamento deve seguir. **Nada no código o impõe.** Não
> existe `label_to_model` em Python, não existe verificação de que a marca ficou fora do
> contexto, e o passo do Chairman/refutador não é código — é contrato, executado por quem
> orquestra. Se a marca vazar pro contexto de julgamento, o run segue e ninguém avisa.
> Chamar isto de blinding "real" era forte demais: é blinding **por disciplina**. Está no
> roadmap do `execution.md`.
> Roubado do llm-council (Karpathy) + pesquisa de self-preference (modelos inflam próprio/mesma-família
> −38%/+90%). **Explicitar ≠ "cego":** aqui "cego" quer dizer **sem rounds e sem marca**, não sem
> instrução. O firewall da crença-alvo (§3a) é uma coisa; o brand-blinding é outra.

Duas visões separadas do MESMO card:
- **Visão-de-julgamento (cega à marca):** o Chairman e o refutador (§3d) raciocinam sobre cards
  identificados por **IDs OPACOS** (`C1`, `C2`, `C3`…) — a marca do modelo **não aparece** ("via
  <modelo>" some). O mapa **`label_to_model`** (qual ID = qual modelo) fica **FORA do contexto** do
  Chairman/refutador: é um **arquivo à parte que só o passo de RENDER lê**. O motor de julgamento nunca
  o recebe.
- **Visão-de-display (personificada):** a reatribuição (`C2` → "The Unit Economist (via Opus 4.8)") acontece **só no
  render**, pro usuário. Personificação e groundedness ficam intactas.

Complementa a regra da família (§3a-ter, que tira a família da SALA): esta **cega a marca DENTRO da
sala**. Invariante de implementação: se `label_to_model` vazar pro contexto de julgamento, o blinding
está furado — o harness deve garantir a separação (ver `core/execution.md`).

### 3f. Síntese de 3 camadas (divergência é o produto; recomendação EM CIMA, não no lugar)
NÃO colapsar num "caminho dourado". Nessa ordem:
1. **Mapa de Protocolos** — a divergência preservada: cada cluster de visão = um protocolo coerente, com pré-condição + o que otimiza ("siga A se quer velocidade; B se quer segurança").
2. **Red-team + análise marginal** — a fraqueza de cada protocolo, qual move a agulha, o que é dud, teto honesto vs âncora.
3. **Recomendação do Chairman** (o modelo-host) — "incorporo isto, dropo aquilo, por quê", SENTANDO em cima do mapa visível. É opinativa — mas **a caneta fica na mão do decisor**. ⚠️ O prior do modelo-host NÃO ganha peso extra (ele já tem um generalista na matriz); o Chairman arbitra, não re-vota.

**Contrato do resumo — sem perda:**
1. **Convergência → comprime com peso** (N células repetindo = 1 item, peso N; repetição é ruído, o peso é sinal).
2. **Divergência → fork estruturado, nunca média/escolha** (teses opostas + pré-condição). É trava anti-colapso: mediar duas teses opostas produz uma terceira que ninguém defende.
3. **Item único sobrevive por MÉRITO, não por voto** (no experimento, o item que mudou a decisão era quase invisível em frequência — teria morrido numa contagem de votos).
4. **Merge preserva a versão mais ESPECÍFICA** (a nuance ganha do genérico).
5. **Digest = atenção, não armazenamento** — todo item linka aos cards crus (drill-down); descarte só por refutação factual, e vai pra apêndice "descartados e por quê".
6. **Quote verbatim verificada por código** (construído; ver o gate de render em
   gatilho): toda quote atribuída + epígrafe do dossiê é conferida como substring do card cru do
   conselheiro (normalização de aspas/ênfase/espaço; elipse verificada por segmento; match em
   conselheiro errado = `atribuicao_divergente`). O verificador mecânico é apontado pelo adapter e
   roda junto do gate de render. Já reprovou 18 de 35 quotes de um dossiê pronto, todas distorcidas pelo próprio editor.

O render que consome este contrato (§0–§7, personificado) é especificado em
`core/sections/output-contract.md`.

### 3g. Modo loop — perguntar após a 1ª rodada
Oferecer iterar: *"Quer entrar no modo loop? Você traz a nova versão incorporando o que decidiu, eu
re-rodo o painel e mostro o DELTA no scorecard."*
- Usuário traz a **nova versão dos inputs** → **re-run** → a síntese mostra o **delta por dimensão** (defensibilidade 2.8→4.1 etc.). Sobe = ajudou; neutro/cai = a edição não pagou.
- **Research CACHEADA** na re-rodada (a evidência não mudou; só o painel re-julga o artefato novo) → rápido e barato.
- **Charter de loop (v1.7, estilo `/goal` — até platôar, não num ritmo):** GOAL (estado final mensurável) / WHERE / HOW TO WORK / **HOW TO CHECK YOURSELF** (evidência, não confiança) / HOW TO REMEMBER (state file = persistência entre runs, ver `core/sections/run-persistence.md`) / WHEN TO STOP (sucesso · no-op · blocker · plateau=piso de ruído · limite). **Lista "needs me":** item de decisão só-humana (gastar capital, deletar, mandar pra fora) → para nele, loga, segue = o ask-gate dentro do loop.
- **Piso de ruído:** re-rodar um subconjunto com os MESMOS inputs mede a variância de reprodução = o piso; só conta melhora o delta que **passa do piso E move múltiplas células** (senão 3.2→3.5 = falsa-precisão).
- **MUST-HAVE do loop = split de atribuição** (não A/B dentro da célula): **(1) score FRESCO-CEGO** da v2 (célula não vê v1; o **orquestrador** calcula o delta) → número limpo; **(2) passe de atribuição leve** (mostra v1+v2 → "por que mudou?", dimensão a dimensão; clusterizado = alta confiança). A/B-na-célula é rejeitado: introduz viés sistemático pró-melhora que o piso de ruído NÃO pega. O delta é o produto → não pode contaminar. *(O comparador de versões e o ledger de previsões NÃO estão construídos; o contrato de disco de ambos está em `core/sections/run-persistence.md`.)*
- O **delta é o sinal relativo robusto** — substitui o forecast absoluto (que o red-team externo matou).

---

## Executar com o loop aberto
Front-load o contexto-restrição na largada **E** manter o loop aberto pras correções de meio-de-curso —
é onde o ouro aparece (o salto de qualidade costuma vir de correção mid-flight, não do brief perfeito).
Defaults salvo instrução: posso quebrar a estrutura se achar frame melhor; identidade visual fica pra
depois; nunca inventar número.

## Critério de sucesso — como saber se o motor está valendo o custo
O painel **acha as fraquezas que um expert humano (ou o desfecho real) também apontaria**, e o **ranking
relativo de cenários se sustenta** entre re-runs e modelos. NÃO "prediz o resultado absoluto" (rejeitado
como não-validável). Se o painel não acha as fraquezas óbvias OU o ranking é instável → é teatro, não usar.

## Princípio
Definir os critérios de avaliação (category framing): não afirmar que somos o vencedor — **enquadrar o
problema nos eixos onde somos mais fortes**, pra que a DD do leitor convirja em nós. "Enterprise work
demands X" (verdade de domínio) carrega o produto sem virar pitch.
