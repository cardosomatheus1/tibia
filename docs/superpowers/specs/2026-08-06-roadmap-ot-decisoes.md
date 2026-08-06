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

## Decomposição em subprojetos

Organizado por meta de jogadores online, como decidido. Cada subprojeto ganha
seu próprio spec quando chegar a vez -- isto é o mapa, não a planta.

Três trilhas correm em paralelo, e a ordem dentro de cada uma importa mais que
a ordem entre elas:

- **Promessa** — o que faz alguém escolher este servidor
- **Higiene** — o que faz alguém não ir embora
- **Economia** — o que faz o servidor durar mais de seis meses

### Fase 0 — antes de convidar alguém de fora (hoje, ~10 online)

Higiene, e é tudo dívida já existente:

1. **Backup automático e testado.** Banco e mapa, diário, com restauração
   provada. Hoje não existe -- e uma perda de dados neste ponto encerra o
   projeto. É o único item que sozinho justifica adiar o convite.
2. **Testar as 8 hunts que subiram e nunca foram jogadas.** Entrada, saída
   pela borda, monstros, retorno. Só Lower Roshamuul foi.
3. **Monitoramento com alerta.** Saber que o servidor caiu antes do jogador
   avisar. Uptime e disco.

Promessa:

4. **Bônus de party por vocação** (+20/35/70/100%). Premia jogar junto, que é
   o oposto de disputar -- alinha com a promessa e o RubinOT já valida.

### Fase 1 — divulgação pequena (meta: 30–50 online)

Promessa:

5. **Mais hunts instanciadas.** Há 65 contornadas automaticamente esperando
   revisão. O gargalo é revisar, não gerar.
6. **Slots sob demanda em vez de pré-alocados.** Hoje são 6 por hunt, 54 no
   total, e os recortes entram na memória no boot estejam em uso ou não --
   3,6 M de tiles residentes com o servidor vazio. É por isso que são 6 e não
   50: cada slot custa memória 24 h por dia.

   Carregando o recorte na entrada e descarregando no fim, o teto deixa de ser
   um número escolhido e passa a ser a memória no pico. Pelos logs, os 54
   carregam em ~2 s (≈40 ms cada), então a entrada não fica perceptivelmente
   mais lenta.

   Isto importa mais do que parece: "acabaram os slots" é a espera de respawn
   voltando pela porta dos fundos, que é exatamente o que a instância existe
   para eliminar. Com 6 slots e uma hunt na moda, acontece.

   **Medido em 2026-08-06, e o número decide a questão:** dobrar de 6 para 12
   slots nas 9 hunts levou o servidor de 2004 MB para 2799 MB de RSS. São
   ~13 MB por slot. Extrapolando para as 65 hunts já contornadas, a 12 slots
   cada, dá ~5,7 GB só de instâncias numa VPS de 8 GB -- e nem a 6 slots fecha
   (~2,9 GB). Pré-alocar não escala: é requisito, não otimização.

   **O que falta tecnicamente.** `Game.loadMapChunk(path, position, remove)`
   tem `remove` na assinatura, mas a implementação ignora -- só lê path e
   position (game_functions.cpp:302). Não existe descarregar.

   O caminho existe: `Map::setTile(x, y, z, tile)` guarda um
   `shared_ptr<Tile>` num array fixo do Floor (mapsector.hpp:25). Zerar libera
   o Tile e os itens dentro dele, que são o grosso da memória; o array do
   Floor continua alocado, mas é pequeno perto do conteúdo.

   Falta então uma `Game.unloadMapChunk(position, largura, altura, andares)`
   que percorra a região e zere. Riscos a tratar no spec: criatura ainda
   segurando referência ao tile, topologia de navegação
   (`markNavigationTopologyChanged`) e caches de spectator. É mexer no núcleo
   do mapa, que é a área mais arriscada do servidor -- pede spec próprio e
   teste de 100 ciclos como o da Etapa 6.

   Enquanto não for sob demanda, o paliativo é mostrar no obelisco quantos
   slots estão livres -- não resolve, só evita a viagem perdida.

Higiene:

7. **Site e gerenciamento de conta.** Criar conta, recuperar senha, ver
   personagens. Sem isto não há como alguém de fora entrar.
8. **Regras escritas e canal de suporte.** Discord serve. O que é banível,
   quem responde, em quanto tempo.

Economia:

9. **Sumidouro atrelado à instância.** O item aberto acima. Tem de existir
   ANTES de a base crescer -- introduzir sumidouro depois é tirar coisa da
   mão de quem já tem, e isso gera revolta.

### Fase 2 — público de verdade (meta: 100–200 online)

10. **Loja de conveniência.** Só depois de haver gente suficiente para
    justificar o trabalho e o risco fiscal. Regra já decidida: o não-pagante
    chega no mesmo lugar, só que mais devagar.
11. **Anti-bot.** Antes disso o problema não existe em escala; depois, define
    se a economia sobrevive.
12. **Novidade além da instância.** O item 1 dos temas em aberto. Fica aqui
    porque precisa da promessa definida primeiro -- construir novidade sem
    saber o que o servidor é dá conteúdo solto.

### Fase 3 — durar (meta: 300+)

13. Escala de VPS, política de wipe/temporada, eventos recorrentes,
    infraestrutura de suporte. Não detalhado: é longe demais para desenhar
    agora com honestidade.

### O que NÃO entra

Rates absurdas, PvP pesado e conteúdo próprio grande foram descartados como
prioridade: nenhum serve a promessa de "jogue o tempo que tem, sem disputar".
Podem voltar como bônus, nunca como eixo.

## Como retomar

Sessão nova, dizendo "continuar o roadmap do OT" e apontando este arquivo. O
próximo passo do processo é responder a pergunta da promessa, depois decompor
em subprojetos e só então escrever o spec de cada um.
