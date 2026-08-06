# Roadmap do OT — decisões da conversa (rascunho, não é o spec)

Anotado em 2026-08-06. A conversa de brainstorming acabou junto com o contexto
da sessão; isto guarda o que já foi decidido para retomar sem repetir.

## Decidido

**Crescimento por metas de jogadores online, não por calendário.** Começa com
~10 clients. Cada patamar de online justifica o próximo gasto de VPS,
estrutura e gente. O roadmap se organiza em fases por meta, não em datas.

**A ambição é escala e receita.** Não é servidor de amigos: o objetivo é muita
gente e ganhar dinheiro. Isso torna uptime, backup e suporte parte do roadmap,
não detalhe de operação.

**Monetização é de conveniência, nunca de poder.** Nada de vender item.

**A hunt instanciada NÃO fica atrás de paywall.** Foi a proposta inicial (1
semana grátis, depois só premium) e foi descartada: ela é o único diferencial
construído, e cobrar por ela é cobrar pela própria promessa do servidor. O
jogador que não paga -- que é a maioria -- passaria a ver um OT comum.

O que se vende, então, é o atrito em volta dela, não o acesso:

- mais slots de instância simultâneos (mais fila, não hunt melhor)
- cooldown menor entre entradas
- loot pouch
- premium account (depot, market, offline training, leilão de casa)
- cosmético: outfit, mount, título
- serviços de conta: mudar nome, slot extra de personagem

Regra que decide qualquer item novo da loja: **o não-pagante chega no mesmo
lugar, só que mais devagar.** Exp, loot e dano nunca entram.

## Dois temas que o roadmap tem de cobrir

**1. Novidade além da instância.** A hunt instanciada sozinha não sustenta o
servidor: é um diferencial, não um catálogo. Falta descobrir o que mais puxa
público. Ainda não explorado.

**2. Economia com dreno, não só torneira.** O problema não é quanto entra, é
que quase nada sai. Tibia Coin infla porque a oferta é contínua (loja, farm) e
os sumidouros são poucos e baratos. A referência que o usuário trouxe são os
jogos de NFT, que quebraram exatamente por isso: emitiam moeda sem queimar.

O princípio: **todo ganho recorrente precisa de um gasto recorrente do mesmo
tamanho**, e o gasto tem de destruir a moeda, não transferi-la entre jogadores
-- taxa de leilão não queima nada, só muda de dono.

Sumidouros que o Tibia já tem e podem ser calibrados: aluguel de casa
(recorrente, e já está semanal aqui), imbuements (consome e expira), blessings
(consome na morte), potions e runas, taxa de troca de nome. Falta desenhar os
específicos do nosso servidor.

Cuidado que precisa estar no spec: sumidouro caro demais afasta o jogador
casual, que é justamente o público que a promessa mira. Drenar não pode virar
pedágio.

### A instância é a maior torneira do servidor

Levantado pelo usuário, e não estava previsto. Tirar a disputa de respawn não
deixa o loot igual: **multiplica**. No mapa público, os melhores spots são
poucos e disputados -- é a escassez que segura a entrada de itens. Com 9 hunts
× 6 slots, cabem 54 grupos caçando ao mesmo tempo nos melhores lugares do
jogo, sem esperar, sem KS, sem dividir.

Ou seja: o diferencial do servidor é também a maior fonte de inflação dele. E
piora com o que já foi decidido -- instância grátis para todos, sem paywall.

A saída que fecha o círculo é a entrada da instância **consumir algo que
queima**. Não dinheiro real (isso é a monetização, decidida à parte), e não
taxa entre jogadores (não destrói nada): algo que some do jogo ao entrar.
Assim o sumidouro cresce exatamente na mesma proporção da torneira, sem
precisar calibrar dois números independentes -- quanto mais gente caça,
mais queima.

Fica em aberto o que é esse consumo, e a régua é a mesma de sempre: não pode
virar pedágio para quem joga 2 h por dia.

## Em aberto — a próxima pergunta

**Qual é a promessa do servidor?** Por que alguém sairia do servidor onde já
tem char e amigos para vir para este. Sem isso não dá para escolher o que
construir nem o que vender: "muita gente" é consequência de uma promessa
clara, não ponto de partida.

Candidatos levantados: sem disputa de respawn (é o que a hunt instanciada já
entrega); Tibia global fiel porém estável e sem bot; progressão acelerada;
conteúdo próprio.

## Tensão que precisa de resposta antes de virar spec

A hunt instanciada é hoje o único diferencial construído — e a proposta é
colocá-la atrás de premium depois de uma semana. Se ela for a promessa do
servidor, o jogador novo prova o diferencial e depois o perde: o que sobra é
um OT comum, e a comparação com os outros passa a ser feita sem ele. Se ela
NÃO for a promessa, então falta descobrir qual é.

Isto não decide nada sozinho -- pode ser que o certo seja mesmo cobrar por
ela. Mas a decisão tem de ser consciente, porque define o que o jogador que
não paga vê.

## Estado do que já existe (para não redescobrir)

- 9 hunts instanciadas em produção, com party, cooldown, 3 h de duração,
  fronteira com diálogo de saída e minimapa traduzido
- boss não nasce em instância (portão duplo, verificado em jogo)
- servidor em Open PvP de verdade, não Retro
- client próprio com janela de mapa ampliada, distribuído por updater
- mapeador de hunts com contorno automático (65 hunts de level 200+)

## Como retomar

Sessão nova, dizendo "continuar o roadmap do OT" e apontando este arquivo. O
próximo passo do processo é responder a pergunta da promessa, depois decompor
em subprojetos e só então escrever o spec de cada um.
