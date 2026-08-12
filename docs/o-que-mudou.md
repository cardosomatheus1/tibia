# O que este servidor tem de diferente

Registro do que foi construído sobre o Canary v3.6.1 entre **1 e 12 de agosto
de 2026** — 256 commits. Escrito a partir do histórico do git e dos números
medidos no próprio repositório, não de memória.

Serve para responder rápido: *o que aqui é nosso, e o que veio pronto?*

---

## Panorama

| | |
|---|---|
| Commits próprios | 256 |
| Período | 01–12/08/2026 |
| C++ escrito por nós | ~280 linhas |
| C++ sincronizado do Canary oficial | 10.589 linhas |
| Sistema de hunt instanciada | ~6.250 linhas de Lua |
| Falas de NPC traduzidas | 12.428 (100%) |
| Ferramentas próprias | ~11.400 linhas |

A proporção entre as duas linhas de C++ é o fato mais importante deste
documento: **quase tudo foi feito em Lua, dados e ferramentas.** Isso não é
acidente — é a restrição que a spec da instância fixou logo no começo
(*"nada exige recompilar o servidor"*), porque o VPS não tem cmake nem vcpkg.
As ~280 linhas de C++ que existem são exceções deliberadas, cada uma com
motivo registrado.

---

## A base

O commit inicial importou o **Canary v3.6.1** inteiro, e o commit seguinte
sincronizou a branch `main` do Canary para suportar o **client 15.25**. Esses
10.589 linhas de C++ **não são trabalho nosso** — são upstream. Vale registrar
para ninguém confundir volume de diff com volume de autoria.

O que é C++ nosso, item por item:

| Mudança | Linhas | Por quê |
|---|---|---|
| Open PvP deixa de agir como Retro Open PvP | 74 | O modo estava herdando regras de servidor retrô |
| `Game.unloadMapChunk` | 73 | Devolver memória de um slot de instância ao sair |
| Morte responsabiliza até 5 atacantes | 57 | Era 1 só; injusto em PvP aberto |
| Janela de mapa maior | 52 | O client corria na frente dos dados |
| Dano de field: janela de 5 s | 10 | Regra de retrô vazando para Open PvP |
| Documentação do PZ block de 15 min | 14 | Registra por que **não** encurtar |

---

## Hunt instanciada

A maior frente do projeto. Permite entrar numa **cópia privada** de uma hunt —
sozinho ou com a party inteira — em vez de disputar a pública.

### Princípios que governam o desenho

- a hunt pública permanece inalterada;
- a instância tem os mesmos monstros, loot, exp e respawn da pública;
- a instância **não pode virar fuga de PvP** — quem está em combate ou com PK
  não vê a opção;
- o servidor é a autoridade sobre elegibilidade, slot, destino e duração;
- uma party ocupa um slot só, e membros distantes não são teleportados;
- estado de slot vive **em memória Lua** — reconstruído no boot, nunca
  persistido;
- não fica atrás de paywall.

### Arquitetura

**Um arquivo, N offsets.** Cada hunt tem um recorte `.otbm` com coordenadas
rebaseadas para a origem 0. O mesmo arquivo é carregado em vários *slots*,
cada um numa origem diferente do mapa (`36864, 36864` em diante) — uma faixa
validada como vazia, com folga de 3.841 tiles até o fim do mapa oficial.

O rebaseamento não é detalhe: coordenada absoluta somada ao offset estouraria
o `uint16` e **corromperia o mapa em silêncio**.

**Carga sob demanda.** Pré-alocar slots foi medido e não escala — o mapa entra
quando o jogador entra e sai da memória quando ele sai. Foi para isso que o
`Game.unloadMapChunk` precisou existir em C++. Descobriu-se depois que a área
das *zonas* também pesava e teve de entrar sob demanda junto.

### As 9 hunts

Ciclopes de Thais (piloto), Asura Palace, Falcon Bastion, Brain Grounds
Jakundaf, Haunted Nexus (Ripper/Arac), Gazer PH Haunted Nexus Temple, Lower
Roshamuul, Upper Roshamuul, The Extension Site Mota.

Seis slots cada. Todos os números — largura, altura, andares, entradas — foram
**medidos no mapa de produção** com as ferramentas de `tools/mapa`, não
estimados. Cada entrada foi verificada: tem chão, sem item bloqueante, não é
tile de mudança de andar, e fica a 4+ tiles de qualquer spawn.

A chegada é a **boca da caverna**, não o meio da hunt.

### Ciclo de vida

Entrada por seletor posicional com consentimento por presença (não
`ModalWindow`). Fronteira que impede ver o fim do mapa. Diálogo de saída,
saída manual, resgate de instância órfã, morte tira o jogador da execução,
reentrada enquanto o grupo estiver dentro, duração de 3 h com avisos e
encerramento por tempo. Boss não nasce em instância.

### Ferramenta de mapeamento

`tools/mapa` (~7.480 linhas) é a maior ferramenta do projeto: leitor/editor de
OTBM, visualizador HTML com sprites de monstro, varinha que contorna a área da
hunt em vez de um retângulo, busca de hunts pelo nome no bestiário ou pela
região, painel de revisão, e um instalador que leva tudo.

---

## Tradução PT-BR

Sistema de **idioma por jogador** — cada um escolhe, e o servidor traduz na
saída do NPC.

| | |
|---|---|
| NPCs | 748 de 19 cidades, **100%** |
| Falas | 12.428 |
| Dicionário | 3,1 MB, 17.745 entradas |
| Quest log (estático) | 1.042 de 1.900 — **54,8%** |
| Quest log (dinâmico) | 0 de 98 |

Todas as cidades fechadas em 100%: Rookgaard, Thais, Edron, Carlin, Darashia,
Liberty Bay, Svargrond, Port Hope, Yalahar, Ab'Dendriel, Venore, Kazordoon,
Krailos, Ankrahmun, Dawnport, Issavi, Farmine, Gray Beach, e os avulsos.

**A cauda é longa** — traduzir 20% não resolvia: chegar a 80% das falas
*ditas* exigia 4.735 frases (64% do catálogo). Por isso a estratégia foi por
cidade, uma de cada vez, fechando cada uma antes de seguir.

Duas armadilhas que custaram caro e ficam registradas:

- **Encoding.** O protocolo do Tibia usa **CP1252**, não UTF-8. Os arquivos de
  dicionário tiveram de ser reconvertidos ou os acentos viravam mojibake.
- **Ordem de substituição.** A saudação tinha de ser traduzida **antes** de
  trocar `|PLAYERNAME|` — invertido, a chave nunca batia no dicionário.

---

## Client próprio

O client oficial (dudantas) é um binário Qt fechado, sem sistema de módulos —
nenhum semibot pode ser adicionado a ele. Por isso o client distribuído é um
**fork do otclient (mehah)**, que é aberto e fala 15.25.

### Módulos escritos por nós

- **AutoCaster** — semibot de assistência no estilo RTCaster: cura por magia e
  potion, cura de aliado, utilidades (haste, anti-paralyze), e abas de Target e
  Caster. Usa o cooldown real do servidor, mira com histerese. Deliberadamente
  **não** tem cavebot: assistência sim, jogar sozinho não.
- **Idioma** — bandeirinha para trocar o idioma dos NPCs.
- **Loot Pouch** — AutoLoot como benefício da bolsa, com botão no client.

### Distribuição

Instalador Inno Setup + launcher próprio. A cada abertura o launcher compara
CRC32 contra um manifest e baixa **só o que mudou**; o servidor do updater roda
no VPS como serviço systemd na porta 8090.

O updater **não** distribui `data/things/`, `data/sounds/` (170+ MB de assets,
vão no instalador uma vez) nem o `minimap.otmm` (o client reescreve conforme o
jogador explora, então o checksum diverge para todo mundo).

---

## Regras e economia

**Exp escalonada**, no estilo RubinOT — cai de 50× no início até 1,2× no
fim:

| Level | Multiplicador |
|---|---|
| 1–8 | 50× |
| 9–50 | 80× |
| 51–100 | 60× |
| 101–200 | 40–30× |
| 201–500 | 15–10× |
| 501–1000 | 7–3× |
| 1001–1400 | 2–1,5× |
| 1401+ | 1,2× |

Loot 2,5×. Skill e magic também escalonados. Casa, frag e dreno de economia
ajustados junto.

---

## Conteúdo próprio

- **Pipeline de sprites** para o client 15.x, com outfit próprio ("Mago de
  Fogo") — incluindo a correção do pattern 4×3×2 que os outfits oficiais usam.
- **Ícones da loja** gerados a partir dos assets do próprio client.
- **Minimapa completo** (`.otmm`) gerado a partir do OTBM.
- **3 contas de teste** (gabriel, andre, matheus), cada uma com 5 personagens
  level 2000 — um por vocação, incluindo Monk — com equipamento tier 7, magias
  da vocação, mochila, dinheiro, charms e acessos de quest.

---

## Ferramentas

| Ferramenta | Linhas | O que faz |
|---|---|---|
| `tools/mapa` | 7.480 | Ler, editar, visualizar e recortar OTBM |
| `tools/sprites` | 1.245 | Outfits e efeitos próprios |
| `tools/traducao` | 890 | Extrair, medir e importar traduções |
| `tools/updater` | 807 | Manifest, servidor e launcher de atualização |
| `tools/loja` | 640 | Ícones da loja |
| `tools/protocol` | 183 | Testes de handshake 15.25 |
| `tools/installer` | 173 | Empacotamento do client |

---

## Infraestrutura

Servidor de jogo em VPS (Contabo), com o Canary nativo por systemd, webservice
de login e o updater do client. Banco MariaDB.

**O CI do `main` está vermelho** — mas não é bug de código. O portão de
formatação roda `stylua` sobre o repositório inteiro e pede reformatação de
~5.400 arquivos do datapack; reformatar tudo para conseguir um binário seria
uma mudança enorme e arriscada num datapack em produção. O contorno é o
workflow `build-manual.yml`, que chama o mesmo build reutilizável e pula só a
formatação. O binário sai no artefato `canary-linux-release`.

---

## Pendências conhecidas

- **Quest log**: 54,8% do texto estático traduzido, 0 de 98 descrições
  dinâmicas.
- **Monk no client oficial**: a vocação é conteúdo customizado (ids 9/10, que
  não existem no Canary padrão). O client oficial não sabe o que fazer com
  ela; no fork do mehah funciona.
- **"Quadrado azul"** na troca de andar dentro da instância: causa
  identificada (o client descarta a janela ampliada), instrumentação aponta
  dado faltando — não fechado.
- **Deploy é manual**: as mudanças vão para o GitHub, e alguém precisa
  atualizar o VPS.
