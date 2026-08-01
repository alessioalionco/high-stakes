# Meridian — migrar de preço por assento para híbrido no ciclo de renovação?

> **Exemplo sintético.** Empresa, números, conselheiros e citações são inventados para
> demonstrar o formato. Os conselheiros são **arquétipos fictícios** de propósito: um
> exemplo público não deve fabricar citações atribuídas a pessoas reais.

## Escopo

**Decisão:** a Meridian (gestão de contratos jurídicos, US$ 12M de receita recorrente,
240 clientes, retenção líquida de 108%) deve substituir o preço por assento por um modelo
híbrido — plataforma fixa mais consumo por documento processado por IA — já no ciclo de
renovação que começa em 90 dias?

**Não está em escopo:** o valor da tabela nova, a estratégia de canal, e a decisão de
construir versus comprar o motor de extração. O painel foi instruído a tratar esses três
como dados.

**Reversibilidade:** baixa dentro do ciclo. Contratos anuais assinados no modelo novo
prendem a empresa por 12 meses; voltar atrás no meio custa credibilidade com quem já
migrou.

**Sobre os conselheiros:** são **lentes simuladas por modelos de linguagem**. Não são as
pessoas reais, e nenhuma frase atribuída a eles neste dossiê foi dita por eles. O que a
verificação de quotes garante é fidelidade ao que o modelo escreveu naquela lente — nada
além disso.

**Board:** 4 lentes de cobertura mais uma anti-tese, cada uma rodada contra 3 modelos de
famílias distintas, sem que nenhuma célula visse as outras.

## §0 Resumo executivo

**A recomendação é migrar, mas não em 90 dias, e não para todos.** O painel convergiu
com força incomum em um ponto: o modelo por assento já está desalinhado da entrega de
valor, e esse desalinhamento piora a cada mês em que a IA processa mais documentos por
usuário. O que o painel não sustenta é o cronograma. Três das quatro lentes trataram o
prazo de 90 dias como o verdadeiro risco da decisão — não a mudança em si.

**O custo de errar é assimétrico, e a assimetria aponta contra a pressa.** Migrar
devagar custa alguns trimestres de margem que ficaria melhor. Migrar rápido e errado
custa renovações num ciclo em que 40% da base está em janela de renovação simultânea. O
painel foi unânime em que essas duas perdas não são da mesma ordem de grandeza, e que
tratá-las como equivalentes é o erro de enquadramento mais provável aqui.

**O ponto de maior divergência não é se, mas quem paga a conta da transição.** As lentes
se dividiram limpo entre proteger a margem no curto prazo e proteger a previsibilidade do
orçamento do comprador. Essa divergência é real e não se resolve por argumento — resolve
por um dado que a Meridian tem e não olhou: a dispersão de documentos processados por
cliente dentro de cada faixa de contrato. Se a dispersão for alta, o híbrido é urgente. Se
for baixa, ele é cosmético e o esforço deveria ir para outro lugar.

**Um risco apareceu numa lente só e sobreviveu à refutação.** O comprador de software
jurídico é avesso a variabilidade orçamentária de um jeito que não se explica por
economia — se explica por como o orçamento dele é aprovado internamente. Um modelo de
consumo pode ser racionalmente melhor para o cliente e ainda assim ser rejeitado, porque
quem assina não é quem usa. Nenhuma outra lente levantou isso, e a refutação não conseguiu
derrubá-lo.

**O que muda a recomendação:** um piso de consumo alto o bastante para que a fatura de
90% dos clientes fique dentro de uma faixa previsível transforma o híbrido de aposta em
não-evento comercial. Sem esse piso, a decisão vira um teste de tolerância a variância
num segmento que historicamente não tem nenhuma. Este é o item que o painel colocaria na
frente de tudo.

**Como ler este dossiê:** §1 traz onde as lentes concordaram e por quê o mecanismo do dano
é o mesmo; §2 traz as duas divergências, com os dois lados defendidos na voz de quem os
defendeu; §3 traz o que apareceu numa lente só; §4 traz cada conselheiro por inteiro.
Convergência aqui **não é prova** — modelos parecidos erram junto, e três lentes
concordando pode ser um único erro repetido três vezes.

## §1 Convergentes

### 1.1 O preço por assento já está desalinhado da entrega de valor

As quatro lentes chegaram ao mesmo diagnóstico por caminhos diferentes, o que é o tipo de
convergência que vale mais: não é a mesma cadeia de raciocínio repetida, são cadeias
independentes terminando no mesmo lugar. O mecanismo do dano é direto — o custo de servir
cresce com documentos processados, a receita cresce com cadeiras ocupadas, e as duas curvas
descolaram quando a extração automática passou a substituir trabalho humano em vez de
apoiá-lo.

> "Você está cobrando pela cadeira num produto que o cliente comprou justamente para
> precisar de menos gente na cadeira. Isso não é um problema de precificação, é uma
> contradição no modelo." — **A Operadora de Margem** (lente simulada · GPT-5.6 Sol)
O que dá peso a este item é que ele é verificável hoje, sem pesquisa nova. A Meridian tem
a telemetria de documentos processados e a base de contratos; cruzar as duas responde se o
descolamento é teórico ou já está na margem. Duas lentes apontaram que essa checagem
deveria preceder qualquer decisão, e que ela custa dias, não trimestres.

### 1.2 O prazo de 90 dias é o risco dominante, não a mudança

Três lentes trataram o cronograma como o verdadeiro objeto da decisão. O argumento comum:
uma mudança de modelo de preço não falha por estar errada, falha por ser comunicada mal, e
90 dias não dão tempo para descobrir que a comunicação está ruim antes de ela alcançar a
base inteira.

> "Mudança de preço não morre no spreadsheet. Morre na primeira ligação em que o cliente
> pergunta 'quanto eu vou pagar em março?' e o vendedor não sabe responder." — **O Advogado do Cliente** (lente simulada · Grok-4.5)
A concentração de renovações agrava o problema de um jeito específico: com 40% da base
renovando na mesma janela, não há grupo de controle natural. A empresa descobre que errou
depois de já ter errado com quase metade da receita, e sem um contrafactual para saber o
tamanho do erro. Uma lente chamou isso de "testar o paraquedas depois de pular".

### 1.3 Sem piso de consumo, o modelo transfere variância para quem menos a tolera

O consenso aqui foi menos sobre economia e mais sobre comportamento do comprador. Um
modelo puro de consumo é mais justo em média e pior na cauda — e o comprador jurídico
compra para não ter cauda.

> "Justo na média e imprevisível na ponta é exatamente o produto que este comprador não
> quer. Ele paga prêmio por previsibilidade; você está propondo devolver o prêmio e ficar
> com a variância." — **A Estrategista de Categoria** (lente simulada · GLM-5.2)
O piso resolve a maior parte disso sem desfazer o alinhamento de valor, e foi a única
mitigação que apareceu em mais de uma lente de forma independente. O desenho concreto —
onde colocar o piso, e se ele é por cliente ou por faixa — ficou em aberto, e é o tipo de
detalhe que decide se a mudança é não-evento ou crise.

## §2 Divergentes

### 2.1 Proteger margem agora ou previsibilidade do comprador

Esta é a divergência de fundo do dossiê, e ela não se dissolve com mais análise: as duas
posições partem de premissas diferentes sobre o que está mais escasso na Meridian hoje.

🐂 **Ensaio a favor de mover agora, priorizando margem.** Cada trimestre no modelo antigo
é margem que não volta, e o descolamento entre custo e receita acelera. A base atual foi
vendida com uma promessa de eficiência que está sendo cumprida — clientes estão usando
mais e pagando o mesmo. Adiar não é neutro: é escolher subsidiar o uso crescente com
margem própria, e fazer isso por mais tempo em nome de um conforto que o cliente nem pediu.

> "Cada trimestre que você adia é margem que você entrega de graça para um cliente que já
> está feliz. Conforto do comprador é uma escolha que alguém está pagando — no caso, você."
> — **A Operadora de Margem** (lente simulada · Kimi K3)
🐻 **Ensaio a favor de segurar, priorizando previsibilidade.** A retenção líquida de 108%
é o ativo mais frágil e mais valioso da empresa, e ela repousa em confiança acumulada.
Preço é o único ponto do relacionamento em que o cliente sente que perdeu controle. Mexer
nele numa janela de renovação concentrada, sem ter testado a comunicação, arrisca o ativo
inteiro para ganhar pontos de margem que a empresa pode capturar depois, com menos risco.

> "Margem você recupera no trimestre seguinte. Confiança de comprador jurídico você
> recupera em anos, se recuperar. Não são grandezas trocáveis." — **O Advogado do Cliente** (lente simulada · GPT-5.6 Sol)
**Por que divergem:** não é desacordo sobre os fatos — as duas lentes leram os mesmos
números. É desacordo sobre qual recurso é o gargalo. Uma vê caixa e margem como restrição
ativa; a outra vê confiança do cliente. Quem estiver certo sobre o gargalo está certo sobre
a decisão.

**Custo de errar por lado:** errar para o lado da margem custa renovações num ciclo
concentrado, com efeito composto sobre a retenção líquida e sobre a próxima captação.
Errar para o lado da previsibilidade custa dois a três trimestres de margem inferior e o
risco de a janela competitiva fechar. O primeiro erro é mais difícil de desfazer.

**O que resolve:** a dispersão de documentos processados por cliente dentro de cada faixa
de contrato. Alta dispersão significa que o modelo atual já está cobrando errado de gente
demais, e a urgência é real. Baixa dispersão significa que o híbrido reorganiza pouco e a
pressa não se justifica. O dado existe e não foi consultado.

### 2.2 Migrar a base inteira ou só o segmento de alto consumo — fork condicional

Esta divergência é condicional: ela só existe se a resposta ao item 2.1 for "mover". Se a
decisão for segurar, o recorte de segmento não se coloca. Por isso não há dois ensaios
defendidos aqui — há uma pré-condição e um gatilho.

**Pré-condição:** decisão de migrar tomada, com piso de consumo definido.

**Gatilho:** se a dispersão medida em 2.1 se concentrar no quartil superior de uso, o
recorte por segmento passa a dominar — migra-se quem já está fora da faixa, e o resto
permanece no modelo antigo até a renovação natural. Se a dispersão for uniforme, o recorte
por segmento cria dois modelos de preço convivendo sem ganho proporcional, e a migração
ampla fica melhor.

> "Dois modelos de preço convivendo é uma dívida operacional que ninguém coloca no
> spreadsheet e todo mundo paga no suporte." — **A Estrategista de Categoria** (lente simulada · Grok-4.5)
## §3 Únicas

### 3.1 Quem aprova o orçamento não é quem usa o produto

Apareceu numa lente só, e sobreviveu à refutação — o refutador tentou reduzi-la a
aversão genérica a risco e não conseguiu, porque o mecanismo proposto é estrutural, não
psicológico. No comprador jurídico corporativo, o orçamento costuma ser aprovado uma vez
ao ano por alguém que não usa o produto e cuja métrica de sucesso é não estourar a
previsão. Para essa pessoa, uma fatura variável não é um preço melhor — é um risco de
carreira.

**Por que importa:** porque inverte o sinal da análise econômica. Um modelo que é
racionalmente mais barato para a empresa cliente pode ser rejeitado pelo aprovador, e a
rejeição não aparece em nenhuma modelagem de valor. Se este mecanismo for real, o piso de
consumo deixa de ser uma mitigação e vira o produto: o que se vende é a previsibilidade,
com o consumo por trás dela.

**Testabilidade:** alta e barata. Cinco conversas com aprovadores de orçamento — não com
usuários — perguntando como uma fatura variável entraria no processo de aprovação deles.
Se três ou mais descreverem fricção estrutural, o mecanismo está confirmado e o desenho
muda. Custa uma semana.

### 3.2 O motor de extração pode virar refém do preço

Uma lente notou que amarrar receita a documentos processados cria um incentivo interno
perverso: a equipe de produto passa a ter razão para não melhorar a eficiência da extração,
porque eficiência maior significa menos documentos faturáveis para o mesmo trabalho do
cliente.

**Por que importa:** é um risco de médio prazo que não aparece no primeiro ano e é caro de
desfazer depois, porque exige remexer no preço de novo. Empresas que caíram nisso
descobriram tarde que o modelo de receita estava brigando com o roadmap.

**Testabilidade:** média. Não dá para observar antes de acontecer, mas dá para desenhar
contra: definir a unidade faturável em termos de valor entregue ao cliente (contrato
analisado) em vez de trabalho consumido (páginas processadas) desarma o incentivo na
origem. A escolha da unidade é reversível hoje e cara depois.

## §4 Pareceres

### 4.1 A Operadora de Margem

*"Conforto do comprador é uma escolha, e alguém está pagando por ela."*

A leitura desta lente é que a Meridian está subsidiando uso crescente com margem própria e
chamando isso de retenção. A retenção líquida de 108% parece saudável até se perguntar
quanto dela vem de expansão de assentos versus quanto vem de clientes usando muito mais
pelo mesmo preço. Se for majoritariamente o segundo, o número está medindo tolerância, não
valor capturado, e vai piorar sozinho conforme o produto melhora.

O parecer não trata o prazo de 90 dias como problema sério, e é aqui que ele diverge do
resto do painel. O argumento é que o custo de comunicação é fixo e não diminui com tempo —
adiar só adia o desconforto, enquanto a margem perdida é permanente.

**Perguntas:** Quanto da retenção líquida vem de expansão de assentos? · Qual a margem
bruta por cliente no decil superior de uso? · Em quantos meses o custo de inferência
ultrapassa a receita incremental no ritmo atual? · A tabela nova foi testada contra a base
instalada ou só contra clientes novos?

**Sugestões:** Medir a dispersão de uso antes de qualquer coisa · Definir o piso de
consumo pelo percentil 90 da base, não pela média · Separar o preço de plataforma do preço
de consumo na comunicação, mesmo que a fatura seja única.

**Strip:** margem 4/5 · urgência 4/5 · risco de execução 2/5.

**Em uma frase:** o modelo atual está errado e piora sozinho, então o único argumento
honesto para adiar é o risco de execução — que esta lente considera superestimado.

### 4.2 O Advogado do Cliente

*"Margem volta no trimestre seguinte; confiança volta em anos, se voltar."*

Esta lente concorda que o modelo precisa mudar e discorda frontalmente do cronograma. O
raciocínio central é sobre concentração de risco: com 40% da base renovando na mesma
janela, a Meridian perde a capacidade de aprender com os primeiros erros antes que eles
alcancem a maior parte da receita. Não é uma objeção à mudança, é uma objeção a fazê-la
sem grupo de controle.

A recomendação concreta é escalonar por janela de renovação em vez de por segmento —
começar pelos contratos que vencem mais tarde, aprender com eles, e chegar na janela
concentrada com a comunicação já testada. Custa dois trimestres e compra a informação que
o cronograma atual não permite ter.

**Perguntas:** Quantos clientes veriam a fatura subir mais de 20% no modelo novo? · O time
comercial consegue responder "quanto vou pagar em março" hoje? · Existe cláusula de teto
nos contratos atuais que impeça a migração? · Quem, na base, é referência para os outros?

**Sugestões:** Escalonar por janela de renovação, não por segmento · Oferecer teto de
fatura no primeiro ano para quem migrar cedo · Treinar o time comercial na conversa de
variância antes de anunciar, não depois.

**Strip:** risco de churn 4/5 · urgência 2/5 · risco de execução 4/5.

**Em uma frase:** a mudança está certa e o calendário está errado, e o calendário é o que
vai determinar o resultado.

### 4.3 A Estrategista de Categoria

*"O mercado vai ler essa mudança como sinal, não como tabela."*

O foco desta lente é em como a mudança é interpretada por quem não é cliente: concorrentes,
analistas e prospects. Migrar para consumo num momento em que a categoria inteira discute
precificação de IA posiciona a Meridian como quem cobra pelo que entrega — o que é
favorável. Mas fazê-lo às pressas e depois recuar posiciona como quem não sabe o que
está vendendo, o que é pior do que não ter mexido.

A lente também levanta a dívida operacional de manter dois modelos convivendo, que
costuma ser subestimada porque não aparece em nenhuma planilha e se manifesta no suporte,
no faturamento e na previsão de receita.

**Perguntas:** Como os dois concorrentes mais próximos precificam IA hoje? · A mudança
seria anunciada publicamente ou só na renovação? · Existe risco de um concorrente usar a
variância como argumento de venda? · Quanto tempo a empresa aguenta operar dois modelos?

**Sugestões:** Anunciar a mudança como previsibilidade com consumo por trás, não como
consumo com piso · Fechar a data de fim da convivência dos dois modelos antes de começar ·
Preparar a resposta ao argumento de "fatura imprevisível" antes que o concorrente o use.

**Strip:** posicionamento 4/5 · urgência 3/5 · risco de execução 3/5.

**Em uma frase:** a direção fortalece a posição da empresa na categoria, desde que a
execução não transforme a mudança em sinal de hesitação.

### 4.4 O Cético Financeiro — anti-tese

*"Ninguém perguntou se a mudança de preço resolve o problema que a empresa realmente tem."*

A anti-tese não defende o modelo atual. Ela questiona o enquadramento: o painel inteiro
aceitou que o problema é o alinhamento entre preço e valor, quando a evidência apresentada
também é compatível com um problema de custo unitário de inferência que a precificação não
resolve, apenas repassa. Se o custo de servir estiver crescendo mais rápido que qualquer
tabela consegue acompanhar, migrar para consumo compra tempo e adia a conversa difícil.

O segundo ponto é sobre a retenção líquida de 108%: o painel tratou o número como ativo a
proteger. A anti-tese observa que 108% num produto de IA com adoção crescente é um número
fraco, não forte — e que se ele estiver sendo sustentado por clientes que usam muito e
pagam pouco, a migração vai revelar isso de uma vez, e não como sucesso.

**Em uma frase:** a decisão de preço pode estar sendo usada para não tomar a decisão de
custo, e o dossiê inteiro seria diferente se o custo unitário de inferência estivesse na
mesa.

## §5 Notas por lente

As notas abaixo são **sinal fraco** e vão rotuladas como tal. O que importa nelas é o
espalhamento, não o nível: lentes diferentes tendem a pontuar de forma parecida mesmo
quando discordam no conteúdo, então um número alto não significa concordância. Onde o
espalhamento é grande, há divergência real por trás — e essa divergência já está descrita
em §2, que é onde ela deve ser lida.

| Lente | Direção | Urgência | Risco de execução |
|---|---|---|---|
| A Operadora de Margem | migrar | 4/5 | 2/5 |
| O Advogado do Cliente | migrar | 2/5 | 4/5 |
| A Estrategista de Categoria | migrar | 3/5 | 3/5 |
| O Cético Financeiro | reenquadrar | — | — |

O espalhamento em urgência (2 a 4) e em risco de execução (2 a 4) é o mapa da divergência
de §2.1, e é o único conteúdo desta tabela que merece peso.

## §6 Recomendação

### 6.1 A recomendação

Migrar, com piso de consumo, escalonado por janela de renovação, e não em 90 dias. A
direção é sustentada por convergência independente das quatro lentes; o cronograma não é
sustentado por nenhuma delas exceto uma.

### 6.2 O que precisa ser verdade

A recomendação depende de a dispersão de uso ser alta. Se a medição mostrar dispersão
baixa, a urgência desaparece e o esforço deveria ir para o custo unitário — que é o ponto
da anti-tese.

### 6.3 O que observar

A primeira coorte escalonada é o instrumento: se a conversa de variância travar nas
primeiras dez renovações, o problema é a comunicação e ele é corrigível. Se travar na
aprovação de orçamento do cliente, o problema é estrutural e o desenho precisa mudar.

### 6.4 Sugestões ranqueadas

**1. Medir a dispersão de documentos processados por cliente, dentro de cada faixa de
contrato, antes de qualquer decisão.** É o dado que resolve a divergência central do
dossiê e a empresa já o tem — está na telemetria de produto cruzada com a base de
contratos. O mecanismo: se o uso for muito disperso dentro de uma mesma faixa de preço, o
modelo atual já está cobrando errado de muita gente, e a urgência da migração é real e
mensurável. Se for uniforme, o híbrido reorganiza pouco e a pressa não se justifica. Dono:
produto e finanças em conjunto. Gate: nenhuma decisão de cronograma antes deste número
existir. Custa dias, não trimestres, e é a única sugestão desta lista que não pode ser
feita em paralelo com as outras — ela precede.

**2. Definir o piso de consumo pelo percentil 90 da base instalada, não pela média.** O
piso é o que transforma a mudança de aposta em não-evento comercial, e calibrá-lo pela
média é o erro que anula seu propósito: metade da base ficaria acima dele e veria variância
mesmo assim. Calibrado pelo percentil 90, nove em cada dez clientes têm fatura previsível e
a empresa ainda captura o excedente de quem consome muito. O mecanismo é psicológico e
orçamentário, não econômico: o que se está comprando com o piso é a ausência de conversa
difícil na renovação. Dono: finanças. Gate: o piso precisa estar definido antes de qualquer
comunicação ao cliente, porque a comunicação vende o piso, não o consumo.

**3. Escalonar por janela de renovação, começando pelos contratos que vencem mais tarde.**
A concentração de 40% da base numa única janela elimina o grupo de controle natural, e sem
grupo de controle a empresa descobre que errou depois de já ter errado com quase metade da
receita. Começar pelos vencimentos distantes cria a coorte de aprendizado que o cronograma
atual não permite: a comunicação é testada, ajustada, e só então alcança a janela
concentrada. O custo é dois trimestres de margem inferior; o retorno é a informação. Dono:
comercial. Gate: a janela concentrada não é tocada antes de dez renovações escalonadas
terem sido fechadas e analisadas.

**4. Entrevistar cinco aprovadores de orçamento — não usuários — sobre como uma fatura
variável entraria no processo de aprovação deles.** Este é o teste do risco de §3.1, que
apareceu numa lente só e sobreviveu à refutação. O mecanismo é estrutural: quem aprova
orçamento em comprador jurídico costuma ser avaliado por não estourar a previsão, e para
essa pessoa variabilidade é risco de carreira, não preço melhor. Se três ou mais
descreverem fricção estrutural no processo, o piso deixa de ser mitigação e vira o produto
— a comunicação inteira muda de eixo. Dono: comercial ou pesquisa. Gate: resultado na mesa
antes de fechar a mensagem de lançamento. Custa uma semana.

**5. Definir a unidade faturável em termos de valor entregue, não de trabalho consumido.**
Faturar por página processada cria um incentivo interno para não melhorar a eficiência da
extração, porque eficiência maior significa menos unidades faturáveis pelo mesmo valor
entregue ao cliente. Faturar por contrato analisado desarma isso na origem: o produto pode
ficar arbitrariamente mais eficiente sem que a receita caia. O risco é de médio prazo, não
aparece no primeiro ano, e é caro de desfazer porque exige mexer no preço outra vez. Dono:
produto. Gate: a escolha da unidade é reversível agora e cara depois — decidir antes do
lançamento, não durante.

### 6.5 O que este dossiê não resolve

O custo unitário de inferência, levantado pela anti-tese, ficou fora de escopo por
instrução e é o item com maior potencial de inverter a recomendação. Se ele estiver
crescendo mais rápido do que qualquer tabela acompanha, a decisão de preço está sendo
usada para adiar a decisão de custo. O painel não tinha os dados para julgar isso.

Também não resolve o valor da tabela nova — apenas a arquitetura do modelo. E não avalia
se a Meridian tem capacidade operacional de faturamento para suportar consumo, que é uma
pergunta de engenharia, não de estratégia.

### 6.6 Falsificadores

Cada item abaixo é uma previsão que pode ser checada, e que se falhar derruba parte deste
dossiê. A dispersão de uso medida em 6.4.1 será alta o bastante para justificar a migração.
Pelo menos três dos cinco aprovadores entrevistados descreverão fricção estrutural com
fatura variável. Nas dez primeiras renovações escalonadas, menos de dois clientes pedirão
para permanecer no modelo antigo. Se as duas primeiras falharem juntas, a recomendação
inteira deve ser reaberta, não ajustada.

## §7 Honestidade de método

**Descartados e por quê.** Três itens do painel não subiram para o corpo do dossiê. Um
deles — a sugestão de testar preço em prospects antes da base — foi descartado porque
prospects não têm o custo de troca que define o problema, então o teste não seria
informativo. Outro, sobre empacotar o consumo como crédito pré-pago, foi absorvido dentro
da sugestão do piso, que resolve o mesmo problema com menos mecânica. O terceiro era uma
repetição do item 1.1 em outras palavras, vinda de uma segunda lente.

**Onde este dossiê é fraco — a honestidade de método exige dizer isto antes que alguém pergunte.** A anti-tese não foi respondida, foi registrada — o painel não
tinha dados de custo unitário para julgá-la, e isso é uma lacuna real, não um detalhe. A
convergência de §1 vem de quatro lentes rodadas contra três modelos, o que reduz mas não
elimina o risco de erro correlacionado: modelos treinados de forma parecida podem errar
juntos, e três lentes concordando pode ser um único erro repetido. As notas de §5 são
sinal fraco e estão rotuladas como tal no próprio texto.

**A refutação e o que ela fez.** Cada item convergente e cada única passou por um passo de
refutação em modelo de família distinta, instruído a construir o caso contra. Esse passo
tem viés medido a favor de refutar — ele reprova mais do que deveria — então o resultado
foi usado como gerador de profundidade, não como juiz. O item de §3.1 é o único que
sobreviveu inteiro; o de §3.2 foi enfraquecido de "risco provável" para "risco de desenho",
e o texto reflete isso.

**Drill-down.** Cada citação deste dossiê foi verificada por código contra a resposta
original do conselheiro a quem é atribuída, e o texto integral de cada célula fica gravado
junto ao run — os itens acima podem ser abertos até a fonte. Nenhuma citação foi editada
para caber no texto; onde havia corte, ele está marcado com reticências.
