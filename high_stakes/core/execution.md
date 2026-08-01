# Contrato de execução — o que o motor exige do harness (core neutro)

> **O core define CAPACIDADES, não um host.** Qualquer harness que ofereça as 3 capacidades abaixo pode
> rodar o motor. Um host específico (uma VPS, uma máquina local, um runner de CI) é **um host possível,
> não a definição.** Um runbook amarrado a um host específico foi deliberadamente mantido fora daqui:
> ele descreve um lugar onde as capacidades existem, não o que elas são.

## As 3 capacidades exigidas do harness

1. **Chamadas paralelas isoladas.** A matriz é `(N+1)×M` células, cada uma **1 chamada com contexto
   limpo** — nenhuma célula lê a outra (`core/methodology.md` §3b). O harness precisa disparar N
   chamadas em paralelo e garantir isolamento de contexto entre elas. Isso inclui a separação do
   brand-blinding (§3e): o mapa `label_to_model` **não** pode entrar no contexto do Chairman/refutador —
   é responsabilidade do harness manter esse arquivo fora do contexto de julgamento e só entregá-lo ao
   passo de render.
2. **Budget tracking com cap hard.** Todo gasto passa por um ledger **reserve-then-reconcile**:
   pré-debita o teto estimado ANTES do dispatch; se a reserva estourar o **cap ($15 default)**, levanta
   antes de mandar a request (overshoot = 0 mesmo com N calls em voo). Pós-resposta reconcilia estimado
   → custo real. O cap é **persistente cross-processo** (o gasto acumulado sobrevive a re-invocações,
   senão cada run ganharia $cap novos).
3. **Escrita em disco.** O motor grava o layout de `core/sections/run-persistence.md` (cells full-log,
   cards, report, manifest com hashes). Escritas atômicas (tmp + rename) pro ledger e pro manifest.

> **Implementação de referência:** o cliente de execução da instância (apontado pelo adapter) realiza
> (1)–(3) sobre OpenRouter — cap reserve-then-reconcile, retry com backoff, custo via `usage.cost`,
> catalog-snapshot pra reprodutibilidade. É referência de contrato na instância, não parte do core neutro.

## Caching de prefixo (v2 — economia estrutural de input)
O material compartilhado (deck/artefato/evidence pack, idêntico em toda célula) deve vir como
**PREFIXO idêntico do prompt** (system genérico curto + material no início do user; o conteúdo
específico da persona vai DEPOIS). Providers com cache de prefixo (OpenAI, Google, Anthropic e
outros, via OpenRouter) cobram fração do input repetido — como o material é a maior fatia do
custo de célula, o run cai de preço sem mudar o método. Invariante: o prefixo tem que ser
byte-idêntico entre as células do mesmo modelo; persona no prefixo quebra o cache.

## Roster pinado (v2)
O pin (arquivo do adapter) carrega juízes/refutador/Chairman com data e validade; o harness lê o
pin e só dispara floor-check sob gatilho (`core/methodology.md` §3a-ter). O manifest de cada run
grava o slug+provider EFETIVO (o que rodou), como sempre.

## Dependência de provider: OpenRouter (nomeada)
O provider default é **OpenRouter** (agrega as famílias de modelo num único endpoint + retorna
`usage.cost` real, que inclui custo de busca interna que o token-math não pega).
- **Chave via env:** `OPENROUTER_API_KEY`, lida do ambiente ou de um `.env` gitignored da instância —
  **nunca hardcoded, nunca logada.**
- **Slugs resolvidos no run** pelo floor-check (`core/methodology.md` §3a-ter), não gravados no core —
  o catálogo de modelos vem do provider e é snapshotado pra reprodutibilidade.
- **Fallback de pricing:** se o `usage.cost` não vier, cai no token-math do catalog-snapshot. Modelo sem
  pricing no catálogo → **fail-closed** (recusa o dispatch; sem estimativa não há cap).
- Trocar de provider = trocar essa camada; o resto do motor não muda (a fronteira já está no cliente).

## Degradação (o motor degrada gracioso, nunca simula)
- **Leg-morta** (uma célula/modelo falha — HTTP error, empty, timeout): **segue com o resto + nota no
  journal** (qual leg caiu e por quê). Uma perna não derruba o run.
- **< 3 famílias vivas:** o quórum mínimo é **3 famílias distintas** (modelos da mesma família erram de forma
  correlacionada, então 2 famílias produzem confiança falsa, não confirmação). Se sobrarem menos de 3 → **aborta ANTES de gastar mais** e reporta
  (não roda um painel que já sabe estar comprometido).
- **Custo real ultrapassa o cap no meio:** o ledger reconcilia real > cap → registra (flush) e
  **interrompe os próximos dispatches** (a estimativa pode subestimar o real).
- **Mecanismo descrito no contrato mas não construído** (ver o roadmap no fim deste arquivo):
  **DECLARAR a degradação e seguir** — por exemplo, marcar uma quote como não-verificada em vez de
  fingir que a verificação rodou. **Nunca simular.** Um passo que finge ter rodado é pior que um
  passo ausente: some o sinal de que faltou.

## Estimativa de custo TOTAL (pro gate custo/egress — no fluxo v2, dentro do Gate B)
O gate de custo (`core/sections/interactive-gates.md`, §Gate B) mostra a soma de TODAS as chamadas
pagas, não só as células:

```
custo_total ≈ células (N personas × M modelos)
            + research (deep-research/search do pre-pass — a perna cara)
            + floor-check (barato; pesquisa de modelos)
            + Chairman (síntese)
            + refutador (quando ligado)
```

Cada componente usa o teto pessimista por chamada (prompt_tokens × in_price + max_tokens × out_price).
Run max estimado ~$5-8 na matriz cheia; **cap hard $15**. Só perguntar ao usuário se a estimativa passar
do cap; abaixo dele, informar e seguir.

## Roadmap — o que este contrato descreve mas ainda NÃO existe

Listado aqui para que a degradação acima seja verificável em vez de vaga. Nada nesta lista
deve ser apresentado como se funcionasse.

| Não construído | O que faria | O que fazer enquanto não existe |
|---|---|---|
| Delta entre rodadas | comparar rodada N com N−1 (resolvido / novo / reaparecido) | escrever o delta à mão, ou declarar que não há |
| Ledger de previsões | acumular micro-previsões × desfecho real ao longo de meses | registrar o falsificador em cada card; o ledger acumula quando houver desfecho |
| Grounding de persona | ancorar cada lente em material real daquele conselheiro | rodar sem grounding e dizer que rodou sem |
| Retomada de run interrompido | checkpoint / resume / idempotência | recomeçar a rodada |
| Adaptador para um 2º harness | rodar fora deste ambiente | a fronteira core/adapter já está pronta; falta o adaptador |
