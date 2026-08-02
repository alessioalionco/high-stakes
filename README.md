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

### O que ele NÃO é, medido e não estimado

Na única vez em que a saída foi comparada com o mundo real, o motor previu um **júri** — a
sala checando premissas e cobrando números. A reunião foi um **coach**: as pessoas
ajudaram a melhorar a proposta em vez de atacá-la. O dossiê estava certo sobre *onde o
material era frágil* e errado sobre *como a sala se comportaria*.

Daí o nome. É stress-test, não oráculo. Use para achar o buraco antes que alguém ache;
não use para prever a reação de ninguém.

**n=2.** Duas decisões reais até aqui, medidas por quem construiu o motor. Isso não é
amostra, é anedota — e quem calibra confiança em cima de dois casos, dois deles do autor,
está fazendo exatamente o erro que este motor existe para pegar.

### Antes de instalar: isto serve pra você?

Serve se você tem, ao mesmo tempo:

- uma decisão que **vai para fora** e é cara de refazer (um deck de board, um
  posicionamento, uma narrativa de fundraise) — para o resto, é caro demais;
- **Claude Code** e Python 3.11+;
- uma chave da **OpenRouter** com saldo, e disposição de gastar por decisão (o custo real
  do seu caso aparece no preflight, antes de qualquer disparo pago — não confie numa
  faixa fixa, inclusive porque a estimativa pode subestimar);
- **disposição de mandar o seu material para vários provedores de modelo e de busca.**
  Não há filtro de conteúdo na saída (ver "O que sai daqui", mais abaixo). Se esse
  material não pode sair da sua máquina, pare aqui — esta ferramenta não é para o seu
  caso, e nenhuma configuração muda isso.

## Instalação

```
/plugin marketplace add alessioalionco/high-stakes
/plugin install high-stakes@high-stakes
```

O `@high-stakes` do segundo comando é o nome do marketplace, não repetição: o primeiro
comando registra o catálogo, o segundo instala o plugin dele.

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
bin/high-stakes config     # mostra o config efetivo e de onde cada coisa veio
```

Os comandos vão pelo `bin/high-stakes`, que resolve a raiz do pacote a partir da própria
localização — funciona de qualquer diretório, sem instalação e sem `PYTHONPATH`.

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

### O teto de gasto, e onde ele NÃO segura

O motor reserva o custo estimado **antes** de disparar e recusa a chamada se ela
estourar o teto. A contabilidade é por run e vale entre processos: o gasto acumula no
mesmo ledger, então dois terminais atacando a mesma decisão não gastam o teto cada um, e
as reservas em voo são visíveis entre eles. Falha de rede depois do disparo é cobrada de
forma conservadora — um stream derrubado pode ter sido cobrado do outro lado.

**É best-effort, não garantia**, e a diferença importa quando é o seu cartão:

- a reserva usa uma **estimativa**. Se o custo real vier acima dela, quem interrompe o run
  é a reconciliação — **depois** de a chamada ter sido paga;
- o teto vale por instância contra o gasto acumulado. Se você abrir um segundo processo
  pedindo um teto maior, ele respeita o teto **dele**, não o do primeiro — isso é decisão
  do operador, e o motor avisa quando os dois discordam em vez de escolher por você.

Trate como o cinto que impede o acidente comum (laço que dispara mil células), não como
uma trava que torna impossível gastar a mais.

## Testes

Sem framework: cada suíte é um script executável que imprime `PASS` e sai diferente de
zero em falha.

```bash
for t in tests/test_*.py; do python3 -m "tests.$(basename "$t" .py)" || exit 1; done
```

## Estado

**304 testes em 11 suítes — todos os 12 módulos com rede própria.** O que está coberto: o
caminho do dinheiro (teto por run, cobrança conservadora em falha pós-disparo, número
não-finito vindo do provedor não desliga o teto), o dispatcher paralelo (célula que falha
não some, id duplicado barrado antes do gasto, resume travado por hash de input,
isolamento entre juízes), a contenção do material reusado (não lê fora do diretório do
run, nem por symlink), a verificação de citação (quote fabricada ao lado de uma real não
passa), a blocklist de domínio na resposta, a precedência de config, as agregações, os
gates de render, e um smoke que roda o produto como quem acabou de instalar.

Suíte verde mede o que o autor pensou em testar, então as guardas críticas passam por
**teste de mutação**: quebra-se a guarda de propósito e confere-se que alguma suíte fica
vermelha. Guarda que sobrevive à própria remoção não estava testada — foi assim que cinco
delas (duas no caminho do dinheiro, três no gate de render) foram descobertas sem teste,
depois de meses parecendo cobertas.

### O que sai daqui, e o que NÃO filtra isso

Rodar este motor significa mandar o seu material para provedores de modelo e de busca —
está no critério de elegibilidade, e é a premissa, não um efeito colateral. **Não existe
filtro de conteúdo na saída.** Existiu: uma denylist de termos que recusava a query. Foi
removida de propósito. Ela protegia o dado do dono contra o dono — quem escreve a query,
quem é dono do material e quem escolhe os provedores são a mesma pessoa —, e o que ela
produzia na prática era recusa falsa em query legítima.

No lugar dela fica o **Gate B**: antes de qualquer disparo pago, o motor mostra o que vai
sair e espera o seu OK. Um humano com a lista na frente decide melhor que uma heurística
de substring, e é honesto sobre quem está decidindo.

A promessa de zero dependência é **verificada por AST** a cada run da suíte, não confiada:
se alguém adicionar um `import requests`, o teste falha e nomeia o módulo.

Veja `examples/sample-dossier.html` para o formato de saída.

### O que o contrato descreve e ainda NÃO existe

O motor é descrito por contratos em `high_stakes/core/`, e nem tudo que está descrito lá
está construído. A lista fica em **`core/execution.md`**, na tabela do fim, com o que fazer
enquanto cada coisa não existe — vale ler antes de confiar em algum comportamento
específico. Hoje inclui, entre outros: roteamento para provedor sem retenção de dados,
verificação automática de que uma fonte citada sustenta o claim, aborto quando sobram menos
de 3 famílias de modelo vivas, e imposição do brand-blinding na visão de julgamento.

Nada nessa lista deve ser apresentado — por este README, pelo contrato, ou por um dossiê —
como se funcionasse.

## Licença

Apache-2.0 — ver [LICENSE](LICENSE).
