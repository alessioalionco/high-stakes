# Gates interativos v2 — fluxo novo (2 gates) + fluxo recorrente (core neutro)

> Captura as decisões de **experiência do usuário** dos gates — como o fluxo é EXIBIDO, não a
> metodologia (que vive em `core/methodology.md`). Harness-neutral: o adapter serve os prompts, o
> core define o CONTRATO de cada gate. **Redesenho da v2** (redesenho
> pós-2 usos reais): o fluxo de 5 gates da v1 colapsa em **2 gates pra problema novo** e **1 pra
> problema recorrente**, sem perder os kill-switches (que viram automáticos, não perguntas).

## Convenções globais (valem em todo gate)
- **Toda escolha do usuário sai numerada** (`1 / 2 / 3`).
- **Heading de 2 níveis só:** `## Modo High Stakes · <gate>` + `### seção`.
- **Flags de reconciliação:** o que eu assumo aparece como AFIRMAÇÃO corrigível ("assumi X —
  corrige só se não estiver 100%"), nunca como pergunta que trava o fluxo.
- **Papéis automáticos ficam ESCONDIDOS** (generalista, anti-tese, refutador, contagem de células,
  firewall) → apêndice do relatório ou sob demanda.
- **Kill-switches nunca viram pergunta:** número não-aterrado → gap declarado no dossiê; egress →
  queries abstraídas por default; gates de render → código. Isso roda sozinho.

## FLUXO NOVO (problema inédito) — 2 gates

### Gate A — perguntas + materiais + agenda de research
Disparado pelo problema do usuário. UMA mensagem com três blocos:
1. **Perguntas que movem o teto** (★, 3-6, pré-preenchidas com o que eu já souber — o usuário
   corrige em vez de redigir; cada uma com 1 linha de "por que pergunto"). Archetype-aware.
   **Crença-alvo só aparece quando o objeto é ARTEFATO DE PERSUASÃO** (deck, narrativa,
   posicionamento — é a spec de comunicação do artefato, não expectativa de veredito; nos demais
   arquétipos o campo não existe).
2. **Pedidos de material** (docs, dados internos, contexto não-público). Regra de destino
   explícita: material e respostas factuais VÃO pros conselheiros (pack de evidência idêntico);
   crença-alvo e prior do orquestrador ficam com o Chairman (firewall).
3. **Agenda de deep research proposta PELO MODERADOR** (backward: o que a estrutura da decisão
   exige saber + benchmark do orquestrador), com a regra de novidade: **tema novo ou risco de
   conhecimento externo relevante → research completa; tema repetido dentro da validade → cache.**
   O usuário corta/adiciona itens da agenda.

O usuário responde (passo 3 do desenho do decisor) e o fluxo segue direto pro Gate B.

### Gate B — pré-disparo (board + modelos + custo → GO)
UMA mensagem com o retrato completo, tudo corrigível, nada re-perguntado:
- 🎯 **Brief afiado** (devolutiva do Gate A em tabela + flags de reconciliação).
- 👥 **Board sugerido** (lentes numeradas com "o que encarna"; sizing 3→5→7 por complexidade;
  standing escondidos). Pool curado quando existir; do zero quando não.
- 📤 **Devolutiva default do arquétipo** (formas A–F + régua padrão — 1 bloco corrigível; vira
  conversa SÓ se o arquétipo for inédito). Shape "regras do jogo" quando a régua precisa de
  ratificação (cheio/arquétipo novo):
  > *"As regras de avaliação de cada conselheiro serão: (a) a decisão em binário [sim/não]
  > (b) a quantidade estimada [faixa] (c) a dimensão que mais pesa no caso [1-5]. Mais alguma
  > regra a adicionar ou tirar?"*
- 🤖 **Roster do PIN** (ver "Roster pinado" abaixo): 1 linha de confirmação, não uma pesquisa.
- 💰 **Custo estimado** (fórmula em `core/execution.md`; passa do cap → parar e perguntar; abaixo
  → informar) + política de egress (1 linha).
- 📁 **Onde grava** (layout em `core/sections/run-persistence.md`).
- Ações: `1 Rodar · 2 Ajustar (diga o quê) · 3 Ver charter completo`.

Após o GO: research (se houver) + painel + refutação + síntese + render verificado por código — sem mais paradas;
o dossiê chega pronto. **Board formado do zero e acatado → 1 linha pós-GO:** `1 Salvar como pool ·
2 Só desta vez` (a biblioteca de lentes acumula; o adapter grava no formato-casa).

## FLUXO RECORRENTE (problema já trabalhado) — 1 gate
Disparado por "carrega o problema X". O motor recarrega o diretório da decisão (brief, board
congelado, roster, dossiê, ledger — `core/sections/run-persistence.md`) e pergunta **o que fazer**,
com menu adaptado ao estado:
- `1` **Rodada nova / loop** (artefato v2 → mesmo júri congelado, research em cache, delta por dimensão)
- `2` **Quick run** em material novo do mesmo tema (preset quick; mensagem única → `1 Rodar`)
- `3` **Drill-down** no dossiê existente (por âncora §N.M)
- `4` **Registrar outcome** no ledger (calibração real do motor)
- `5` **Encerrar** a decisão

## Presets — RÁPIDO × CHEIO (calibrados por medição de custo-benefício dos assentos)

| | **quick** (tema recorrente, reversível) | **cheio** (inédito e/ou irreversível) |
|---|---|---|
| Lentes | 3 do pool + generalista | 5-7 + generalista ×M + bull/bear no crux |
| Júri | **M=3 do pin** (flagship + 2 baratos) | **M=4** (pin + 4ª família) |
| Agenda | moderador (backward+benchmark) | + pre-pass dos conselheiros (forward) se domínio novo |
| Research | por novidade/cache (TTL) | idem, com agenda completa |
| Cenários | único (as-is) | A/B em célula + dud-screen quando há movimentos a pesar |
| Devolutiva | default do arquétipo | contrato A–F ratificado no Gate B |
| Gates | 1 (mensagem única → GO) | 2 (Gate A → Gate B) |
| Sempre, nos dois | anti-tese ×1 · refutador de família externa · síntese cega à marca · gates de render por código · persistência do run |

## Roster pinado [substitui o floor-check por-run da v1]
O roster de modelos vive num **PIN da instância** (arquivo do adapter) com data, papéis e
**validade (~30 dias)**. No Gate B ele aparece como 1 linha de confirmação. Re-pesquisa (o método
do floor-check em `core/methodology.md` §3a-ter) roda só quando: o pin vence · sai release
relevante · o domínio exige competência específica que o pin não cobre. **Invariante intacto: o
roster CONGELA dentro de um loop** (delta v1→v2 exige os mesmos juízes). Os assentos do pin são
decididos POR DADO (experimento de assentos; ver a instância) — não por gosto nem por índice só.

## Gate de custo e de saída de dados — fica dentro do Gate B
- **Custo:** a estimativa TOTAL (research + células + refutador) aparece no Gate B, antes de
  qualquer chamada paga. Acima do cap ($15 default) → parar e perguntar; abaixo → informar e, com
  o GO, seguir sem novas paradas.
- **Egress:** default = query externa ABSTRAI (nunca número/trecho sensível); pra enviar trecho
  sensível, mostrar exatamente o que sai e pedir OK. Fatos privados ficam internos (células
  via API, nunca em busca externa).
  ⚠️ **Este gate é a ÚNICA trava de egress que existe** — e ela é humana. Não há filtro de
  conteúdo no código (a denylist que existia foi removida; ver o cabeçalho de
  `high_stakes/evidence.py`), e **roteamento no-retention não existe**: o motor não consulta
  a política de retenção de provedor nenhum. Se você mostrar e o humano der OK, sai.

## Cascata de invalidação
Com 2 gates, a cascata opera dentro do Gate B: uma edição re-deriva os blocos afetados e o gate é
re-apresentado SÓ com o que mudou (nunca o retrato inteiro de novo):
```
brief → board → agenda/evidência → devolutiva/régua → custo → GO
```
- Mudou o brief → re-deriva board + agenda + devolutiva default.
- Mudou o board → re-deriva agenda (e custo).
- Mudou a agenda/evidência → re-checa devolutiva (dimensão nova) e custo.
- Mudou a devolutiva/régua → só custo.
Regra: declarar o que re-derivou; nunca deixar bloco stale no gate.

## Origem
Desenho original de fluxo interativo, redesenhado após os primeiros usos reais e a medição
dos assentos do júri. Os gates de custo e a cascata de invalidação foram preservados.
