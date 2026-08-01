# high-stakes

Motor de rigor para decisões caras de refazer.

Você tem um deck para o board, uma narrativa de posicionamento, uma decisão estratégica —
algo que vai para fora e que você não vai poder desfazer. Pedir uma opinião a um modelo
devolve um conselheiro simpático. Este motor faz outra coisa: monta um **painel
adversarial cego**, faz cada conselheiro atacar o material sem saber o que os outros
disseram, **refuta o próprio consenso**, e devolve um dossiê onde toda citação atribuída
foi verificada por código contra a resposta original.

Ele não prevê como a sala vai reagir. Ele mede **onde a sua decisão quebra sob ataque** —
que é a pergunta útil antes de entrar na sala.

## Instalação

```
/plugin marketplace add alessioalionco/high-stakes
/plugin install high-stakes
```

É isso. **Zero dependências** — o motor usa só a biblioteca padrão do Python (3.11+).
Não existe `pip install` neste fluxo, de propósito: uma dependência faltando falharia
depois de você já ter escrito o brief e aprovado o custo.

Só falta a chave do provedor:

```bash
export OPENROUTER_API_KEY=...
```

## Uso

```
/high-stakes devo circular este deck para o board agora ou esperar o fechamento do trimestre?
```

O motor conduz o resto: refina o pedido com um brief pré-preenchido, propõe a composição
do board, mostra o custo estimado, e só dispara depois do seu GO.

## Como funciona

```
       o seu problema
             │
        Gate A  ── perguntas essenciais + materiais + agenda de pesquisa
             │
        Gate B  ── brief afiado + board proposto + custo → você dá GO
             │
             ▼
   painel adversarial CEGO
   personas × modelos de famílias diferentes, cada célula sem ver as outras
             │
             ▼
      refutação por item ── um modelo separado ataca o consenso do painel
             │
             ▼
   ┌─── três gates de código, todos exit 0 obrigatório ───┐
   │  render_gate     estrutura do dossiê + jargão        │
   │  qverify         toda citação é verbatim             │
   │  render_dossier  HTML single-file                    │
   └──────────────────────────────────────────────────────┘
             │
             ▼
      dossiê §0–§7
```

**Por que famílias diferentes de modelo:** dois modelos da mesma família erram junto. Um
painel que erra junto não é painel — é um conselheiro com sotaques.

**Por que cego:** conselheiro que vê a resposta do anterior converge para ela. A
convergência só vale como sinal se for independente.

**Por que refutar o próprio consenso:** unanimidade costuma ser eco do enunciado, não
sinal. O refutador existe para achar o caso em que o painel inteiro está errado junto.

**Sobre os conselheiros:** as lentes levam nomes de pessoas reais, mas são **simulações
por modelo de linguagem** — as pessoas não disseram nada disso. O motor obriga o dossiê a
declarar isso, e reprova quem não declarar: o artefato circula, e a atribuição
`— **Nome**` tem a mesma cara de uma citação de verdade.

**Por que verificar citação por código:** editar um dossiê distorce citação sem que
ninguém perceba. Ao verificar um dossiê pronto, 18 de 35 citações estavam sutilmente
alteradas — cortes, emendas, uma frase inteira acrescentada. Nenhuma foi intencional.

## Configuração

```bash
python3 -m high_stakes.config     # mostra o config efetivo e de onde cada coisa veio
```

Precedência: argumento explícito > variável de ambiente > `./.high-stakes.toml` >
`~/.high-stakes/config.toml` > default.

| Chave | Default | Governa |
|---|---|---|
| `runs_dir` | `./high-stakes-runs` | onde a decisão é gravada |
| `boards_dir` | `~/.high-stakes/boards` | o seu pool de lentes |
| `pin_path` | `~/.high-stakes/roster-pin.yaml` | quais modelos julgam |
| `cap_usd` | `15.0` | teto de gasto **por run** |
| `concurrency` | `8` | células simultâneas |
| `timeout_s` | `1200` | por chamada |

A chave de API **não** entra no config, de propósito — arquivo de config tende a ser
versionado, e chave em repositório é acidente esperando acontecer.

### O teto de gasto é real

O motor reserva o custo estimado **antes** de disparar e recusa a chamada se ela
estourar o teto. A contabilidade é por run e vale entre processos: dois terminais
atacando a mesma decisão não furam o teto, porque as reservas em voo são visíveis entre
eles. Falha de rede depois do disparo é cobrada de forma conservadora — um stream
derrubado pode ter sido cobrado do outro lado.

## Testes

Sem framework: cada suíte é um script executável que imprime `PASS` e sai diferente de
zero em falha.

```bash
for t in tests/test_*.py; do python3 -m "tests.$(basename "$t" .py)" || exit 1; done
```

## Estado

**219 testes em 11 suítes — todos os 12 módulos com rede própria.** O que está coberto: o
caminho do dinheiro (teto por run válido entre processos, cobrança conservadora em falha
pós-disparo), o dispatcher paralelo (célula que falha não some, id duplicado barrado antes
do gasto, resume travado por hash de input), o no-leak da pesquisa externa (bloqueio
verificado por espião que conta chamadas), a precedência de config, as agregações, os
gates de render, e um smoke que roda o produto como quem acabou de instalar.

A promessa de zero dependência é **verificada por AST** a cada run da suíte, não confiada:
se alguém adicionar um `import requests`, o teste falha e nomeia o módulo.

Veja `examples/sample-dossier.html` para o formato de saída e
`high_stakes/core/execution.md` para a lista do que este contrato descreve mas ainda não
está construído.

## Licença

Apache-2.0 — ver [LICENSE](LICENSE).
