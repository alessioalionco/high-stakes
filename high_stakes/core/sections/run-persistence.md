# Persistência de runs — layout de disco por decisão (core neutro)

> Define COMO cada decisão real vira artefato recuperável e iterável ao longo do tempo — os 2 usos:
> (1) recuperar todo o contexto no futuro; (2) rodar mais rodadas sobre a mesma decisão conforme
> evidência nova chega. Harness-neutral: o core fixa o CONTRATO de disco (layout, o que é
> tracked/gitignored, o manifest); o **root é configurável** e o adapter aponta a instância. Fonte:
> run-persistence-v1 (definido). É camada por cima do que o motor já cospe — **não muda o
> motor.**

## Fronteira: experimento ≠ decisão real

| | Experimento | Decisão real (este contrato) |
|---|---|---|
| Mora em | `experiments/` (da instância) | **root configurável** (`runs_dir`) — default `./high-stakes-runs/` |
| Roster | fixo (comparabilidade histórica) | floor-check por decisão, congelado no loop |
| Ledger | não | micro-previsões × desfecho real *(não construído)* |

O **root é um parâmetro** (`runs_dir` no config): o adapter injeta o caminho da instância; o
default é `./high-stakes-runs/`, relativo ao diretório de onde o motor foi chamado.

## Layout (contrato)

```
<root>/<YYYY-MM-DD>-<slug>/
  README.md          # recap + journal por rodada + auto-observação + estado (aberta/decidida/desfecho)
  brief.md           # brief afiado + board ratificado + contrato A–F + floor-check (por-que-vs-default)
  manifest.yaml      # machine-readable: roster congelado, dims E1, formas A–F, rounds[] (data/custo/sha)
  inputs/            # GITIGNORED (sensível) — assets crus + MDs de extração
    MANIFEST.md      # TRACKED: sha256 + origem + path no backup (Drive) de cada asset
  research/          # deep research — TRACKED (fonte externa, não-sensível por natureza)
  rounds/
    r1/
      cells/         # FULL LOG — texto integral por célula + material de trabalho do Chairman
      cards/         # SoR estruturado (dual-emit)
      report.md      # SoR do dossiê
      report.html    # snapshot CONGELADO (procedência do que foi lido/enviado)
      report.pdf     # idem (⌘P → PDF)
    r2/ … + delta.md # resolvido/novo/reaparecido vs rodada anterior (não construído)
  ledger.md          # micro-previsões × desfecho, atualizado ao longo de meses (não construído)
```

## As decisões de contrato (fechadas 17/Jul)

1. **Inputs sensíveis: gitignored; backup canônico = fora do git (Drive).** `inputs/MANIFEST.md`
   (tracked) carrega **sha256 + origem + path do backup** de cada asset — mesmo sem os bytes no git,
   você SABE o que falta e VALIDA o que recuperou. *(Resolve o H-D1: assets local-only fazem backfill
   nesta convenção.)*
2. **HTML/PDF committados como snapshot CONGELADO por rodada.** Não contradiz "HTML é render, não SoR":
   o snapshot é PROCEDÊNCIA (o artefato exato sobre o qual se decidiu), não fonte. Só o render final por
   rodada; nunca intermediários. MD regenera; HTML/PDF registram.
3. **Um diretório por run, não repo por run** (repo por run fragmenta histórico; gitignore + backup já
   isola o peso dos assets).
4. **Rodadas imutáveis em subdirs** (`rounds/rN/`) + `delta.md` gerado por diff card-a-card contra a
   rodada anterior — resolvido / novo / reaparecido. *(O gerador do delta ainda não existe; o
   contrato de disco está aqui para quando existir.)*
5. **`cells/` = full log por rodada.** Texto integral de cada célula + material de trabalho do Chairman
   antes do digest. Sem isso, o drill-down do contrato lossless (o digest linka aos cards crus) morre na
   2ª camada.
6. **`brief.md` + journal no README.** `brief.md` = o que o fluxo interativo ratificou (brief
   afiado, board aprovado, contrato A–F, resultado do floor-check com por-que-mudou-vs-default);
   `manifest.yaml` = a versão machine-readable do congelamento; README = journal (1 entrada/rodada:
   data, o que mudou, custo) + um campo de **auto-observação**: "li o mapa inteiro ou pulei direto
   para a recomendação?". Quem decide pular sistematicamente está usando o motor como oráculo, que é
   o modo em que ele não vale o custo.

## Chave `sensitivity` — run sensível não vaza pelos derivados
> **Failure mode:** um run sobre decisão sensível (M&A, saúde, jurídico) grava as CÉLULAS e o REPORT
> tracked → o número sigiloso vaza pelo git mesmo com `inputs/` gitignored.

O contrato carrega um **knob `sensitivity`** (default: não-sensível). Quando **sensível**, o caminho dos
insumos e derivados que carregam o dado bruto segue a mesma regra do `inputs/`:
- **gitignored + backup fora do git (Drive) + sha256 no MANIFEST.** Vale pra `inputs/`, `cells/`,
  `research/` e os `report.*` que embutem o dado sensível.
- **Só `README.md` + `manifest.yaml` ficam tracked** (o esqueleto: estado, journal, hashes, roster —
  sem o conteúdo sensível).
- O adapter é quem materializa o gitignore da instância; o core declara O QUE é sensível.

## Manifesto por rodada — cada rodada é um snapshot dos próprios insumos
> **Failure mode:** o delta v1→v2 fica contaminado se o slug foi re-roteado (provider diferente) ou o
> insumo mudou embaixo (mesmo arquivo, bytes diferentes) — o delta mede infra/insumo, não a decisão.

`manifest.yaml` por rodada carrega, além do roster congelado / dims E1 / formas A–F:
- **slug + provider efetivo** de cada modelo (o que REALMENTE rodou, não o pedido);
- **data + parâmetros** do run;
- **sha256 do brief E do evidence pack** daquela rodada.

Assim cada rodada é um **snapshot completo dos próprios insumos** — o delta só é comparável entre
rodadas cujos hashes de insumo batem (ou cuja diferença é declarada). É o que torna o loop reprodutível.

## Iteração ao longo do tempo (uso 2)
Rodada nova = **mesmos juízes** (invariante do floor-check: roster congela pelo loop; fresco só em
decisão nova). Evidência nova entra por `inputs/` (+ MANIFEST atualizado) e `brief.md` (delta do
contexto); o motor roda, grava `rounds/rN/` imutável, gera `delta.md` vs r(N-1). O `ledger.md` atravessa
rodadas: cards com `falsifier` viram micro-previsões checadas contra o outcome real — calibração
acumulada. *(O acumulador ainda não existe; o gatilho para construí-lo é a 1ª decisão com
desfecho registrado.)*

## O que este contrato NÃO muda
Nada no motor. É camada de persistência por cima do que o motor já produz e do que os gates já
ratificam.

**Três coisas aqui têm contrato mas não têm build** — estão marcadas como tal em cada ocorrência
acima, e é assim que devem ser tratadas: o delta entre rodadas, o ledger de previsões × desfecho, e
o campo de auto-observação no README. Descrever contrato como se fosse build é a falha que este
aviso existe para impedir.
