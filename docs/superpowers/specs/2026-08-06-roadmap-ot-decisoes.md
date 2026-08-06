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

**Monetização é de conveniência, nunca de poder.** Nada de vender item. O que
se vende:

- loot pouch
- premium account
- acesso à hunt instanciada (1 semana grátis, depois só premium)

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
