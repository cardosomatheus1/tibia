# SPEC — Sistema de Hunt Instanciada (revisão 2.0)
## Piloto: Ciclopes de Thais

**Código do recurso:** `INST-HUNT-001`
**Versão:** `2.0` — revisada contra o codebase real
**Base:** `spec_hunt_instanciada_ciclopes_thais.md` v1.0
**Plataforma:** Canary 15.x — **Lua e dados apenas, zero C++**

---

# 0. O que mudou da v1 para a v2, e por quê

A v1 foi escrita sem consultar o código. A auditoria encontrou que **~70% da
mecânica já existe** em bibliotecas testadas (60 bosses em produção) e que 5
requisitos da v1 resolvem problemas que não existem neste servidor.

## 0.1 Restrição que governa tudo

> **O VPS de produção não tem cmake/g++/vcpkg.** Recompilar o Canary é
> inviável. Tudo precisa sair em Lua e dados.

A boa notícia: a auditoria confirmou que **nada da spec exige C++**.

## 0.2 Removido (resolvia problema inexistente)

| v1 pedia | Por que saiu |
|---|---|
| 6 cópias físicas do OTBM | `Game.loadMapChunk(path, pos)` aplica offset nos tiles (`src/io/iomap.cpp:154`). É 1 arquivo, N chamadas. |
| Reserva atômica, "bloquear pool", mutex | Lua do Canary é **estritamente single-threaded**. Prova: `static ScriptEnvironment scriptEnv[16]` com `++scriptEnvIndex` sem atomic nem mutex (`src/lua/functions/lua_functions_loader.hpp:500,355`). `if slot.free then slot.free = false end` já é atômico. |
| 5 tabelas SQL | Zero tabelas necessárias. KV é o padrão do código novo (98 KV vs 54 storage no core ativo). O cooldown de boss já faz exatamente isso (`data/libs/functions/player.lua:596`). |
| Limpeza "100 tiles por ciclo" | `Zone:getItems()` e `Zone:removeMonsters()` são caches vivos mantidos por `Tile::addThing/removeThing`. Custo O(entidades), sem varrer tile. |
| Mapear porta, escada, buraco, corda, teleport um a um | Chokepoint único e **vetável**: `zoneBeforeCreatureLeave` (`src/game/game.cpp:12395`). Todo movimento de tile passa por `Map::moveCreature`, inclusive teleport. |

## 0.3 Corrigido (v1 estava tecnicamente errada)

1. `member:isOnline()` **não existe em Lua** — só uso interno em C++, sem
   `registerMethod`. O pseudocódigo da v1 §27 quebraria em runtime.
2. **ModalWindow morre quando o jogador anda** (`src/creatures/players/player.cpp:12173`)
   e a resposta é descartada em silêncio. Isso inviabiliza o ready check de 15 s
   da v1 §9.5 como desenhado. Redesenhado na §9 desta versão.
3. **`monster:setSpawnPosition()` vaza permanentemente** — nada remove entradas
   de `spawnMonsterList` exceto reload de mapa. Inutilizável para instância.
4. **Sem `SpawnMonster` não há leash** — `isInSpawnRange()` retorna `true`
   incondicionalmente (`src/creatures/monsters/monster.cpp:3321`). Monstro
   passeia pra fora da instância.
5. **Zonas não são destruíveis** — não existe `Zone:remove()` nem `removeZone`.
   Obriga pool fixo de zonas pré-nomeadas.
6. **Towns e waypoints não recebem offset** (`src/io/iomap.cpp:263`) — carregar o
   mesmo chunk N vezes sobrescreve o mesmo town id com posição não deslocada.
7. **Spawns XML não recebem offset** (`src/creatures/monsters/spawns/spawn_monster.cpp:47`).
8. **Cooldown por conta** não é o padrão do repo (que é por GUID de personagem),
   mas é viável: `player:getAccountId()` existe (`src/lua/functions/creatures/player/player_functions.cpp:132`).
9. **Logout dentro da instância** não era tratado (v1 §19 só cobria reconexão).
10. `db.query` **não retorna `affectedRows`** e é **síncrono** (trava o game
    loop). O padrão `UPDATE ... WHERE status='free'` para reservar slot é
    impossível — e desnecessário, dado o single-thread.

## 0.4 A premissa central ficou em aberto

A v1 exige "não carregar OTBM durante o clique". Mas **este servidor já carrega
chunks OTBM em runtime, em produção**: o Soul War troca `ebb-flow.otbm` (322 KB)
em tempo real, e há 15 call sites desse padrão em `data-otservbr-global/scripts/`.

→ Ver **§4, Portão de decisão**. Meça antes de construir o pool.

---

# 1. Objetivo

Permitir que o jogador escolha entre entrar na hunt pública dos Ciclopes de
Thais ou em uma cópia privada da mesma hunt, sozinho ou com a party inteira.

Ao sair, retorna ao mapa global perto do seletor. Jogadores PK ou em combate PvP
não veem nem acessam a opção privada.

---

# 2. Princípios

- a hunt pública permanece inalterada;
- a instância tem os mesmos monstros, loot, exp e respawn da pública;
- a instância não pode ser usada como fuga de PvP;
- o servidor é a autoridade sobre elegibilidade, slot, destino e duração;
- uma party ocupa um slot só;
- membros distantes não são teleportados;
- a composição autorizada é congelada no início;
- **estado de slot vive em memória Lua** — reconstruído no boot, nunca
  persistido (§16);
- **nada exige recompilar o servidor.**

---

# 3. Arquitetura

## 3.1 Geometria: 1 arquivo, N offsets

Um único `thais_cyclops_instance.otbm` é carregado N vezes em coordenadas
diferentes, via offset.

```lua
Game.loadMapChunk("world/custom/thais_cyclops_instance.otbm", Position(5000, 5000, 7))
Game.loadMapChunk("world/custom/thais_cyclops_instance.otbm", Position(5500, 5000, 7))
-- ... N vezes
```

`IOMap::parseTileArea` soma o `position` a cada tile lido
(`src/io/iomap.cpp:154-156`). Um arquivo, N posições.

### Por que coordenadas distantes não custam nada

O mapa é **sparse**: `std::unordered_map<uint32_t, MapSector> mapSectors`
(`src/map/mapcache.hpp:187`), setores de 16×16, e dentro de cada um só existe
`Floor` para os `z` usados. Além disso os tiles são **materializados
preguiçosamente** — `setBasicTile` só grava um ponteiro; o `Tile` real nasce em
`getOrCreateTileFromCache` quando alguém chama `getTile`. Região carregada e
nunca visitada custa quase nada.

O `width`/`height` do cabeçalho OTBM **não limita nada** — é usado só num
`reserve()` de hash map (`src/map/mapcache.cpp:187`). O limite real é o tipo de
`Position`: `uint16_t x,y` / `uint8_t z`, com `MAP_MAX_LAYERS = 16`.

Custo estimado por cópia de 200×200: **~3,3 MB** (3 andares) a **~8,5 MB**
(8 andares). **O caro não é o mapa, são os monstros instanciados.**

### Escolha da faixa de coordenadas — RESOLVIDO na Etapa 0

⚠️ **A faixa X 5000-6200 / Y 5000-5200 proposta na v1 está OCUPADA.** Colide com
o nó de área `(4864, 4864, 7)`, que cobre x 4864-5119 / y 4864-5119.

Os XMLs oficiais (monster, npc, house, custom) diziam que a região estava vazia —
**só o OTBM real mostrou a geometria**. Verificado com
`tools/mapa/scan_ocupacao.py` contra o `otservbr.otbm` de produção (176 MB,
1171 nós de área).

**Faixa adotada: origem em `(36864, 36864, 7)`.**

| | |
|---|---|
| Maior coordenada usada pelo mapa oficial | x 34304, y 34048 |
| Teto do tipo `Position` (`uint16`) | 65535 |
| Folga até a geometria mais próxima | **3841 tiles** |
| Slots de 256×256 que cabem depois do mapa oficial | 3660 |

Escolhida **depois do fim do mapa oficial**, não num vão interno: um vão pode ser
preenchido por atualização futura do datapack; além do fim, não.

O `width`/`height` do cabeçalho (35143×34812) **não limita nada** — é usado só
num `reserve()` de hash map (`src/map/mapcache.cpp:187`), sem bounds-check em
`getTile`/`setBasicTile`. Passar dele é seguro.

**Revalidar** com `scan_ocupacao.py` sempre que o datapack do mapa for atualizado.

## 3.2 Trade-off: `loadMapChunk` vs `world/custom/`

| | `world/custom/` | `Game.loadMapChunk` |
|---|---|---|
| Offset | **não aceita** — exigiria N OTBMs com coordenadas pré-assadas | **aceita** |
| Carrega | terreno + houses + spawns + npcs + zones | **só terreno** |
| Limite | 50 arquivos | nenhum |
| Retorno | síncrono no boot | **assíncrono, sem confirmação de sucesso** |

**Decisão: `Game.loadMapChunk`.** Terreno-só é suficiente porque esta spec já
quer spawns por Lua (§7) e proíbe houses (§6.3). Zones são criadas por Lua (§5).

⚠️ O 3º parâmetro `remove` da assinatura **é aceito e silenciosamente ignorado**
(`src/lua/functions/core/game/game_functions.cpp:302`). Não existe descarregar
chunk.

## 3.2.1 Fidelidade de coordenada — resolvida no client

O problema que o offset cria: o jogador fica fisicamente em `36864+`, longe de
Thais. Sem tratamento, o minimapa dele mostra uma região nova e desconhecida.

**Não há solução server-side.** `sendAddCreature` manda `player->getPosition()`
cru (`src/server/network/protocol/protocolgame.cpp:1098`) e **não existe
mensagem de minimapa vinda do servidor** — o único hit em todo o
`protocolgame.cpp` é `MinimapMarker`, da cyclopedia. Mentir a posição exigiria
traduzir toda posição que entra e sai da camada de protocolo, em C++.

**Solução: traduzir na exibição, no OTClient.** O client distribuído é o
OTClient (mehah), cujo minimapa é módulo Lua. O hook é
`modules/game_minimap/minimap.lua:18-40`:

```lua
local pos = player:getPosition()
if not minimapWidget.fullMapView then
    minimapWidget:setCameraPosition(pos)   -- <- posicao crua
end
minimapWidget:setCrossPosition(pos)        -- <- posicao crua
virtualFloor = pos.z
```

Basta traduzir `pos` antes dessas duas chamadas:

```lua
local function paraExibicao(pos)
    local slot = slotQueContem(pos)          -- nil fora da faixa de instancia
    if not slot then return pos end
    return {
        x = pos.x - slot.origem.x + HUNT_ORIGEM.x,
        y = pos.y - slot.origem.y + HUNT_ORIGEM.y,
        z = pos.z,                           -- z e' o mesmo (5-9)
    }
end
```

**Ganho colateral:** com a coordenada traduzida, o widget lê o `minimap.otmm`
que **já existe** e mostra o minimapa **real de Thais** com tudo em volta. Não
é preciso gerar dado de minimapa para a região da instância.

Resultado:

| Camada | O que acontece |
|---|---|
| Servidor | N instâncias paralelas em 36864+ |
| Minimapa | jogador aparece em Thais, cercado do mapa real |
| Viewport do jogo | terreno real da hunt + margem (§6.1.1) |

⚠️ Limites, a validar na implementação:

- `fullMapView` não passa por `setCameraPosition` — abrir o mapa cheio precisa
  de tratamento próprio, e arrastar opera em coordenada real;
- é **só exibição**: comando de GM, `exiva` e outros módulos que mostrem
  coordenada continuam vendo a real;
- vale **só no OTClient**. No client oficial (Qt, sem Lua) não há como.

⚠️ Hook **confirmado por leitura** do módulo instalado, **não testado**.

## 3.3 O que "criar uma instância" significa

- alocar um slot já carregado;
- criar um `runId`;
- vincular jogador ou party;
- criar os monstros da execução;
- salvar as posições de retorno;
- ativar os eventos daquele `runId`.

## 3.4 O que não será feito

- adicionar `instanceId` a `Position`;
- alterar o protocolo de mapa do cliente;
- exigir cliente customizado;
- criar uma instância por membro da party;
- **tocar em qualquer arquivo `.cpp`/`.hpp`.**

---

# 4. Portão de decisão — meça antes de construir o pool

O pool pré-carregado existe para evitar carregar OTBM durante o clique. Mas o
servidor **já faz isso em produção** (Soul War, 322 KB).

**Antes da Etapa 2 da implementação:**

1. Recorte o chunk da hunt.
2. Suba com `logLevel = "debug"`.
3. Chame `Game.loadMapChunk` e leia a linha que o `IOMap::loadMap` já emite:
   `"Map Loaded {} ({}x{}) in {} milliseconds"` (`src/io/iomap.cpp:90`).

| Tempo medido | Decisão |
|---|---|
| **< ~15 ms** | Pool pode virar carga sob demanda — **desde que reutilize as mesmas N coordenadas** (§4.1). Elimina o preload no boot, não os slots. |
| **> ~15 ms** | Mantenha o pool pré-carregado desta spec. |

## 4.1 A regra que governa a escala

> **O que precisa ser limitado é o número de regiões de coordenada distintas já
> usadas — não o número de execuções.**

Isto **não é negociável**, porque:

1. **Não existe unload.** `mapSectors.erase` não aparece em lugar nenhum do
   código; `MapCache` não tem remoção de setor nem de floor. `Map::clean()`
   (`src/map/map.cpp:1389`) só remove itens *cleanable*, não geometria. O 3º
   parâmetro `remove` de `loadMapChunk` é aceito e **silenciosamente ignorado**.
2. **Zonas não são destruíveis** (§8.4).

Consequência direta: **carregar sob demanda em coordenada nova a cada execução
faz o footprint crescer sem limite, para sempre.** Uma região por run, nunca
liberada.

A única forma correta de "sob demanda" é **sobrescrever as mesmas coordenadas**
para resetar — que é exatamente o que o Soul War faz com as variantes do
`ebb-flow`.

## 4.2 Teto de escala

Espaço de coordenada **não** é o limite: cabem 3660 slots de 256×256 depois do
mapa oficial (§3.1). Memória é, e é linear:

| Slots | Geometria, 3 andares | Geometria, 8 andares |
|---|---|---|
| 6 | 20 MB | 51 MB |
| 100 | 330 MB | 850 MB |
| 3660 | 11,8 GB | 30,4 GB |

O VPS de produção tem **7,9 GB e nenhum swap**. Geometria pura toleraria ~100
instâncias.

⚠️ **Mas geometria não é o custo dominante — monstros são.** Cada instância
carrega a contagem de monstros da hunt, e:

- monstros materializam `Tile` + `Item` reais (~700 B–1 KB por tile ocupado),
  além do objeto `Monster`;
- `Game::updateForgeableMonsters` (`src/game/game.cpp:12066`) varre **todos** os
  monstros do mundo, sem filtro de região;
- os slots globais de `forgeInfluencedLimit`/`forgeFiendishLimit` do servidor
  inteiro são diluídos entre todas as instâncias.

**Medir na Etapa 0** (§21): custo de RSS por instância com os monstros vivos.
Sem esse número, qualquer pool acima de ~20 slots é chute.

**Para o piloto: 6 slots.** É folgado em qualquer cenário e não compromete a
decisão de escala.

⚠️ `loadMapChunk` entra via `g_dispatcher().addEvent` na lane `WorldCommit`,
bloqueando o tick durante o parse. No boot é irrelevante; em runtime é o número
que importa.

**Registre o resultado da medição nesta seção antes de prosseguir.**

---

# 5. Mapa de reuso — o que NÃO escrever

Escrever do zero seria reimplementar, pior, código que roda em 60 bosses.

| Necessidade | Já existe | Arquivo |
|---|---|---|
| Trava de ocupação | estado **derivado** de `zone:countPlayers(IgnoredByMonsters) > 0` — imune a dessincronia | `data/libs/functions/boss_lever.lua:170` |
| Pool de salas por offset | 10 salas derivadas por aritmética | `data-otservbr-global/lib/quests/svargrond_arena.lua:26-116` |
| Teleporte de grupo por tiles | `Lever:checkPositions/checkConditions/teleportPlayers` | `data/libs/functions/lever.lua:112-179` |
| Limpar loot largado | único código do repo que faz isso, com whitelist | `svargrond_arena.lua:207-246` |
| Remover monstros em massa | `Zone:removeMonsters()` — cache vivo, O(monstros) | `src/game/zones/zone.cpp` |
| Expulsar jogadores | `Zone:setRemoveDestination(pos)` + `removePlayers()`, com fallback pro temple | `zone.cpp:193-201,131-142` |
| Prender monstro na área | `Zone:trapMonsters()` | `data/libs/systems/zones.lua:189` |
| Eventos de zona | `ZoneEvent` com before/after enter/leave | `data/libs/systems/zones.lua:101-177` |
| Cooldown persistente | `Player:getBossCooldown/setBossCooldown` — padrão KV | `data/libs/functions/player.lua:596-617` |
| Party completa | `Participants(player, sharedExp)` | `data/libs/functions/party.lua:121` |
| Eventos canceláveis em massa | `Encounter:addEvent` + `cancelEvents` | `data/libs/systems/encounters.lua` |
| ModalWindow | helper + dispatcher prontos | `data/libs/functions/modal_window_helper.lua` |

## 5.1 Armadilhas de reuso

⚠️ **Não use a lib `Encounter` para spawnar os monstros da hunt.** Ela chama
`monster:setRewardBoss()` em **todo** monstro que cria
(`data/libs/systems/encounters.lua:217`) — o loot normal vai embora. Use a
máquina de eventos dela, não o `spawnMonsters`.

⚠️ **Não use `monsterStorage`** (`data/libs/functions/monster.lua:1-44`) — tabela
global indexada por creature id, nunca limpa na morte, e **ids são reciclados**.
Um monstro novo lê o estado de um morto.

⚠️ **Não copie o ModalWindow de `data/libs/systems/hireling.lua:677-708`** — tem
3 bugs. Copie de `data/scripts/talkactions/gm/teleport_to_player.lua:37-55`.

---

# 6. Mapa da instância

## 6.1 Template — limites medidos na Etapa 0

`data-otservbr-global/world/custom/thais_cyclops_instance.otbm`

**Recorte de origem, medido no mapa de produção:**

```text
x 32400 - 32536   (137 tiles)
y 32032 - 32120   ( 89 tiles)
z     5 -     9   (  5 andares)
```

Distribuição vertical dos ciclopes (99 no total), de
`tools/mapa/achar_hunt.py` + contagem por andar:

| z | ciclopes | outros | densidade | |
|---|---|---|---|---|
| 5 | 3 | 21 | 12% | andar superior |
| 6 | 12 | 7 | 63% | andar superior |
| 7 | 17 | 24 | 41% | solo |
| **8** | **51** | 16 | **76%** | **núcleo** |
| 9 | 16 | 37 | 30% | andar inferior |
| 10+ | 0 | — | — | fora da hunt |

A hunt **não é só o andar comum**: vai de 2 andares acima do solo a 1 abaixo.
Incluir z=5 a z=9 inteiros, com as escadas que os ligam.

Tipos: 86 `Cyclops`, 7 `Cyclops Smith`, 6 `Cyclops Drone`.

**Carga de terreno medida:** 38.379 tiles, 17.912 itens, 611 tipos distintos.

Deve conter: área completa da hunt, os 5 andares, paredes, pisos, escadas,
buracos, objetos fixos, área de entrada, saída controlada, margem (§6.1.1).

## 6.1.1 Margem de terreno — quanto, e por quê

O jogador não pode ver vazio na borda da instância. O client enxerga **8 tiles
em X e 6 em Y**; o servidor envia **11** em cada eixo
(`MAP_MAX_VIEW_PORT_X/Y`, `src/map/map_const.hpp:12-15`).

**Margem mínima absoluta: 11 tiles.** Abaixo disso aparece vazio.

| Margem | Recorte | KB/cópia | 6 slots |
|---|---|---|---|
| 0 | 137×89 | 1712 | 10 MB |
| 16 | 169×121 | 2790 | 16 MB |
| **32** | **201×153** | **4121** | **24 MB** |
| 64 | 265×217 | 7545 | 44 MB |

**Adotado: 16 tiles** — `x 32384-32552 / y 32016-32136`, 169×121, **16 MB nos 6
slots**. A margem de 32 foi rejeitada: traz um teleport OTBM para o mapa global
e um unique id (medido, ver abaixo).

A margem é **cópia do terreno real** em volta da hunt, não cenário inventado.
Combinada com a tradução de coordenada (§3.2.1), o jogador vê o lugar certo no
viewport e no minimapa.

### Custo da margem em contaminação (medido)

| Margem | Teleport OTBM | Action ID | Unique ID | Depot | Portas |
|---|---|---|---|---|---|
| 0 (`137×89`) | 0 | 0 | 0 | 0 | 8 |
| **16** (`169×121`) | **0** | **1** | **0** | **1** | **22** |
| 32 (`201×153`) | **1** ⚠️ | 2 | 1 | 1 | 35 |

A margem de 32 inclui um teleport em `(32566,32120,8) → (32569,32110,7)`:
**buraco de fuga direto para o mapa global**, furando o `InstanceManager`.

### Lista de exclusão obrigatória para a margem 16

| O quê | Onde | Por quê |
|---|---|---|
| **Teleport de quest, `aid 48063`** | `(32520,32020,8)` | **Heart of Destruction** — `scripts/quests/heart_of_destruction/movements_teleport.lua:5` manda para `Position(32448,32389,10)`. **Fuga para o mapa global.** |
| Depot `id 8` | `(32398,32043,8)` | daria acesso ao depot de dentro da instância |
| 22 portas de casa | `x 32392-32403`, `y 32145` | casas não são carregadas (`loadHouses=false`), a porta ficaria órfã |

⚠️ **O `aid 48063` não aparece como teleport na varredura de tiles.** Ele é um
*movement em Lua indexado por action id* — mecanismo diferente do `TELE_DEST`
do OTBM. Por isso o `perigos_recorte.py` passou a cruzar todo action id
encontrado com os scripts do datapack. **Sempre leia essa seção da saída**;
achar `ACTION IDs: 0` é o único resultado que dispensa a checagem.

⚠️ Ao mudar o recorte, **rode `perigos_recorte.py` de novo**. Cada margem tem
sua própria contaminação.

## 6.2 O que remover do OTBM da instância

### O que NÃO é problema (medido, não suposto)

`Game.loadMapChunk` carrega **só terreno** — `loadHouses/Monsters/Npcs/Zones`
vêm todos `false` (`src/game/game.cpp:1097`). Logo, **não** são duplicados:

- os 316 monstros do XML global dentro do recorte (só 99 são ciclopes);
- os NPCs do XML global (há 4 na vizinhança, incluindo `Lugri`, de quest);
- as casas do `otservbr-house.xml`.

Spawns vêm do Lua (§7), então você controla exatamente o que nasce.

### O que É problema — varredura do OTBM real

Resultado de `tools/mapa/perigos_recorte.py` sobre `x 32400-32536 /
y 32032-32120 / z 5-9` no mapa de produção:

| Perigo | Encontrado | Ação |
|---|---|---|
| `TELE_DEST` (teleports) | **0** | — |
| `ACTION_ID` | **0** | — |
| `UNIQUE_ID` | **0** | — |
| `DEPOT_ID` | **0** | — |
| `HOUSEDOORID` | **8** | **apagar** |

As 8 portas de casa estão no canto noroeste (`x 32400-32403`,
`y 32035-32044`). **Não há ciclope nesse canto**, mas há ciclope em `x=32400`,
então aparar o recorte em x perderia spawn. **Apague os 8 itens de porta no
editor** em vez de encolher a área.

Recorte limpo em todo o resto: nenhum teleport que mandaria o jogador de volta
às coordenadas globais, nenhum action id que dispararia script global, nenhum
unique id a duplicar.

⚠️ **Sem towns e sem waypoints.** `parseTowns` e `parseWaypoints`
(`src/io/iomap.cpp:263-310`) são chamados **sem o offset** e gravam nos mapas
globais. Carregar o mesmo chunk N vezes sobrescreve o mesmo town id N vezes com
a posição errada. Não são detectáveis pelo scanner de tiles — **confira no
editor ao salvar o chunk**.

Também proibido (v1 §15.3, mantido): chests de quest, recompensas únicas,
teleports de missão permanentes, storages de quest, houses, mecanismos que
alterem o mundo global.

**Revalide** com `perigos_recorte.py` depois de recortar, apontando para o
`.otbm` do chunk.

## 6.3 Piso da instância — DECIDIDO: sem `NOLOGOUT`

**O piso da instância NÃO leva `TILESTATE_NOLOGOUT`.**

A tentação era marcar (`src/io/iomap.cpp:176`, checado em `player.cpp:6860`):
dado puro, zero código, e o jogador simplesmente não desloga lá dentro.

O custo mata a ideia:

```cpp
// src/game/game.cpp:12074
if (monster->canBeForgeMonster() && !monsterTile->hasFlag(TILESTATE_NOLOGOUT)) {
    forgeableMonsters.emplace_back(monster->getID());
}
```

Tile com `NOLOGOUT` **sai do pool de forge** — sem influenced, sem fiendish,
sem dust nem slivers na instância. Isso quebra frontalmente a paridade exigida
pela §7.4 e pelos critérios de aceite (§22), e esvazia a proposta do recurso:
uma instância estritamente pior que a hunt pública não tem por que existir.

### Por que não custa código abrir mão dele

O handler de login que resgata jogador preso **já é obrigatório** pela §14.4
(instância órfã depois de restart). O mesmo handler cobre o logout voluntário —
e a regra é **incondicional** (§14.1): quem loga dentro de um slot nasce fora.

```lua
-- instance_login.lua
if InstancePool.getSlotByPosition(player:getPosition()) then
    player:teleportTo(template.globalReturn)   -- sem excecao
end
```

Ou seja: `NOLOGOUT` não economizaria uma linha — só cobraria o forge.

### E o risco de fuga de PvP?

Não existe. A entrada já é barrada por skull e PvP lock em três etapas (§10),
então quem está lá dentro estava elegível ao entrar. Deslogar não remove
battle sign nem devolve o jogador a lugar nenhum vantajoso: ao voltar, ou
reentra na própria execução dentro do prazo de tolerância (§14.2), ou é
mandado para o retorno global.

## 6.4 Coordenadas relativas

Todos os pontos são relativos à origem do template.

```lua
templateOrigin  = Position(100, 100, 7)   -- origem do arquivo OTBM
slotOrigin      = Position(5000, 5000, 7) -- origem da cópia N
-- posição real = slotOrigin + (ponto - templateOrigin)
```

---

# 7. Spawns

## 7.1 Respawn em Lua — obrigatório

⚠️ **Não use `monster:setSpawnPosition()`**
(`src/lua/functions/creatures/monster/monster_functions.cpp:433`). Ela cria um
`SpawnMonster` real e faz `emplace_back` na lista **global** — e **nada no código
remove entradas dessa lista** exceto `SpawnsMonster::clear()` no reload de mapa.
Cada instância vazaria N entradas permanentes. (Também tem radius e direção
hardcoded.)

Implemente o respawn em Lua, replicando as regras de
`SpawnMonster::checkSpawnMonster`:

- um `addEvent` por spawn point, guardando o handle para `stopEvent` no teardown;
- respawnar só quando o monstro morre ou some;
- respeitar o `spawntime` do spawn público equivalente;
- não nascer em cima de player se o monstro for `isBlockable`.

⚠️ O `addEvent` tem **piso de 100 ms** forçado
(`src/lua/functions/core/global_functions.cpp:702`).

## 7.2 Criação

```lua
local monster = Game.createMonster(name, realPos, true, true)
```

Assinatura: `Game.createMonster(name, pos[, extended[, force[, master]]])`
(`src/lua/functions/core/game/game_functions.cpp:569`).

⚠️ **Nunca passe o 5º argumento.** `master` faz `setMaster(master, true)` — o
monstro vira summon e **perde bestiary, task e bosstiary**.

## 7.3 Leash

Sem `SpawnMonster` associado, `Monster::isInSpawnRange()` retorna `true`
incondicionalmente (`src/creatures/monsters/monster.cpp:3321`) — o monstro nunca
é puxado de volta.

**Obrigatório:** `slotZone:trapMonsters()` (`data/libs/systems/zones.lua:189`).

## 7.4 Paridade com a hunt pública — confirmada

Bestiary, charms, loot e experiência são **agnósticos à origem do monstro**.
`Player::onKilledMonster` (`src/creatures/players/player.cpp:6571`) tem apenas
duas guardas:

```cpp
if (monster->hasBeenSummoned()) { return false; }
if (!monster->getSoulPit()) { addHuntingTaskKill; addBestiaryKill; addBosstiaryKill; }
```

Nada consulta `getSpawnMonster()` nem `masterPos`. `addBestiaryKill`
(`src/io/iobestiary.cpp:383`) só olha `raceid`; charms
(`iobestiary.cpp:412`) idem. Não existe flag `fromSpawn` no Canary.

### As 4 armadilhas que quebram a paridade

| Armadilha | Efeito |
|---|---|
| 5º arg `master` em `createMonster` | vira summon → zero bestiary |
| lib `Encounter` (`setRewardBoss()`) | loot normal desaparece |
| `Monster:soulPit(true)` | `setDropLoot(false)` + bypassa bestiary |
| piso com `TILESTATE_NOLOGOUT` | sai do pool de forge (§6.3) |

⚠️ Não crie MonsterType por instância. `Game.createMonsterType` nasce com
`raceid = 0` — **mataria o bestiary** — e o registro é permanente, sem
unregister.

---

# 8. Pool de slots

## 8.1 Configuração

```lua
preloadedSlots   = 6   -- cópias carregadas no boot
maximumActiveSlots = 6
```

Sem `initialWarmSlots`/`minimumWarmSlots`: como não há preparo caro (spawn é Lua,
sob demanda), a distinção COLD/WARM da v1 não paga o próprio custo.

## 8.2 Estados

```text
FREE      -- sem execução, pronto
ACTIVE    -- execução em andamento
CLEANING  -- encerrando, entidades sendo removidas
FAULTED   -- erro, slot isolado
```

Fluxo: `FREE → ACTIVE → CLEANING → FREE`.

O estado `GRACE` da v1 **não existe mais**: desconexão é saída definitiva
(§14.2), então não há execução "preservada esperando alguém voltar".

## 8.3 Alocação — sem cerimônia de atomicidade

Lua é single-threaded (§0.2). Nada preempta entre duas linhas; `addEvent` só roda
depois que o script atual retorna.

```lua
local function allocateSlot(template)
    for _, slot in ipairs(template.slots) do
        if slot.state == "FREE" then
            slot.state = "ACTIVE"   -- atômico por construção
            return slot
        end
    end
    return nil
end
```

Se ainda quiser defesa em profundidade, derive a ocupação em vez de confiar na
flag — é o que o `BossLever` faz (`boss_lever.lua:170`):

```lua
slot.zone:countPlayers(IgnoredByMonsters) == 0
```

## 8.4 Zonas — pool fixo, nomes estáveis

⚠️ **Zonas não são destruíveis.** Não existe `Zone:remove()` em Lua nem
`removeZone` em C++ — `Zone::addZone` insere num `static phmap` por nome e só
`clearZones()` global (no reload) limpa.

```lua
-- CERTO: pool fixo, criado uma vez no register()
Zone("hunt.thais_cyclops.slot." .. i)

-- ERRADO: vaza uma zona por execução, para sempre
Zone("run_" .. runId)
```

Reciclagem: `subtractArea` (faz `unindexPosition`) + `addArea` no reuso.

⚠️ `Zone:addArea` itera **toda** posição do retângulo e depois `refresh()`
re-itera tudo. Para 60×60×3 ≈ 10.800 posições é aceitável uma vez no boot,
proibitivo a cada execução. **Crie as áreas no startup, não por run.**

⚠️ `Zone:refresh()` **não restaura os tiles ao estado do OTBM** — só reconstrói o
índice tile↔zona (`src/game/zones/zone.cpp:323`). Não é "reset de instância".

---

# 9. Entrada

## 9.1 Seletor

Objeto interativo antes da entrada da hunt, com actionId exclusivo.

```text
Action ID: 65001   -- livre no namespace de actionid
Nome interno: thais_cyclops_instance_selector
```

(Verificado: 65001/65002 aparecem no repo apenas como storageId, clientid de casa
e id de oferta da store — **namespaces distintos, sem conflito**.)

A janela **não** abre ao pisar num tile.

## 9.2 Consentimento por presença, não por ModalWindow

⚠️ **Andar invalida todas as ModalWindows abertas do jogador**
(`src/creatures/players/player.cpp:12173-12183`) e a resposta é descartada **em
silêncio**. O ready check de 15 s da v1 §9.5 morreria com qualquer passo de
qualquer membro, sem mensagem.

**Redesenho: presença física é o consentimento** — o padrão nativo do codebase
(`Lever`, usado em 60 bosses).

```lua
playerPositions = {
    { pos = Position(x1, y1, z), teleport = entry1, effect = CONST_ME_TELEPORT },
    -- ... até maximumInstanceMembers
}
```

Fluxo:

1. cada membro pisa num dos tiles marcados diante do seletor;
2. o líder usa o seletor;
3. `Lever:checkPositions()` (`lever.lua:112-140`) lê quem está em cima;
4. quem está no tile entra; quem não está, não entra.

Isso elimina o ready check, o timeout de 15 s, os estados
`PENDING/ACCEPTED/DECLINED/EXPIRED` e a tabela `hunt_instance_members` — e é
imune ao bug da janela.

**ModalWindow fica só para a escolha pública/privada do líder**, que é uma
interação única com o jogador parado no seletor.

## 9.3 Janela do líder

```lua
local window = ModalWindow({ title = "Ciclopes de Thais",
                             message = "Como deseja entrar nesta área?" })
window:addChoice("Mundo Aberto", function(player, button, choice)
    if button.name ~= "Select" then return true end
    -- ...
end)
```

⚠️ `buttonId`/`choiceId` **não são validados em C++**
(`src/game/game.cpp:11108-11139` só checa `hasModalWindowOpen`). Cheque
`button.name` explicitamente. Máximo de 255 buttons/choices.

A opção privada só é inserida se: for líder ou solo, elegível (§10), e houver
slot livre. **O servidor revalida mesmo que a opção não tenha sido enviada.**

## 9.4 Mensagens

| Situação | Texto |
|---|---|
| Não-líder pedindo privada | `Somente o líder da sua party pode iniciar uma instância privada.` |
| PK / PvP | `Somente a entrada no mundo aberto está disponível no momento.` |
| Pool cheio | `As áreas privadas estão ocupadas no momento.` |
| Aviso de limpeza | `Itens deixados no chão serão removidos quando a instância for encerrada.` |

## 9.5 Party

```lua
minimumPartyMembers    = 2
maximumInstanceMembers = 5   -- teto real = #playerPositions
requireAllPartyMembers = true
requireSameFloor       = true
```

Todos os membros online da party devem estar nos tiles. Party válida: todos
entram. Party inválida: ninguém entra.

⚠️ **Não use `member:isOnline()`** — não existe em Lua. Um `Player` obtido de
`party:getMembers()` já está online por construção; se precisar revalidar, use
`Player(guid)` e teste `nil`.

## 9.6 Snapshot

Após a entrada, congela a lista de autorizados:

```lua
run.members = { [playerGuid] = true, ... }
```

Novos membros da party não entram, expulsar não libera vaga, ninguém substitui
participante, e a execução não depende da composição atual da party.

## 9.7 Teleporte

```text
validar todos → alocar slot → criar runId → salvar retorno de todos
              → teleportar todos → ativar execução
```

Se qualquer teleporte falhar: devolve os já transportados, aborta a execução,
libera o slot para `CLEANING`, **não aplica cooldown**, e avisa a party.

---

# 10. Elegibilidade — PK e PvP

```lua
restrictedSkulls   = { SKULL_WHITE, SKULL_RED, SKULL_BLACK }
blockDuringPvpLock = true
```

Bloqueiam a opção privada: white/red/black skull, PvP lock ativo, PZ lock por
combate PvP, ataque PvP iniciado após a abertura da janela.

**Validação em três etapas** (mantida da v1 — é o que impede o abuso):

1. ao abrir o seletor;
2. ao usar o seletor (líder);
3. imediatamente antes do teleporte.

Se qualquer integrante estiver impedido, **a party inteira é bloqueada**. Liste
os impedidos ao líder:

```text
Membros impedidos:
• Knight Test — white skull
• Sorcerer Test — PvP lock
```

A instância não pode servir de fuga de PK, remoção de battle sign, proteção
contra perseguição, ou transporte remoto de membros.

---

# 11. Saída

## 11.1 Chokepoint único

⚠️ **Não mapeie porta, escada, buraco, corda e teleport um a um.**

`Map::moveCreature` (`src/map/map.cpp:700`) é atravessado por *toda* mudança de
tile — incluindo `Game::internalTeleport`, que termina nele
(`src/game/game.cpp:3572`). Ele dispara `zoneBeforeCreatureLeave`, cujo retorno é
**vetável**: `false` bloqueia a saída (`src/game/game.cpp:12395`).

Wrapper Lua pronto: `ZoneEvent` (`data/libs/systems/zones.lua:101-177`).

```lua
local ev = ZoneEvent(slotZone)
function ev.beforeLeave(zone, creature) --[[ interceptar ]] end
function ev.afterLeave(zone, creature)  --[[ contabilizar ]] end
ev:register()
```

Saídas que não são movimento têm hook *after* (não vetável, mas suficiente para
contabilizar): morte (`src/creatures/creature.cpp:865`) e logout/remoção
(`src/game/game.cpp:1585`).

⚠️ `beforeCreatureZoneChange(..., force = true)` ignora o veto — alguns caminhos
internos usam.

## 11.2 Retorno

```lua
globalReturnPosition = Position(x, y, z)
globalReturnRadius   = 2
emergencyReturn      = Position(x, y, z)
```

Posição de retorno é **por jogador**, salva na entrada. `Zone:setRemoveDestination`
é por zona (com fallback pro temple do town, `zone.cpp:131-142`) — serve de rede
de segurança, não substitui o retorno individual.

Se o tile estiver bloqueado: procurar tile caminhável próximo, evitando fields,
parede, tile sem chão e outro jogador; senão, posição de emergência.

## 11.3 Regras

- cada membro sai individualmente; os demais permanecem;
- **quem sai não retorna à mesma execução**;
- saída do líder **não** encerra a execução;
- party desfeita **não** expulsa ninguém — os autorizados permanecem;
- a execução termina quando o último sai.

Confirmação antes de sair:

```text
Ao sair, você não poderá retornar a esta instância. Deseja continuar?
```

---

# 12. Duração e cooldown

```lua
maximumDurationMinutes = 120
emptyGraceMinutes      = 3    -- atraso antes do teardown, NAO janela de volta
reentryCooldownMinutes = 5
```

(`disconnectGraceMinutes` saiu: desconexão é saída definitiva, §14.2.)

Avisos aos 15, 5 e 1 minuto restantes. Ao expirar: encerra, devolve todos, limpa
o slot.

Cooldown por **`accountId + templateId`**, aplicado em **toda** saída — porta,
morte, logout e queda de conexão (§14.2). `player:getAccountId()` existe
(`src/lua/functions/creatures/player/player_functions.cpp:132`).

> Nota: o padrão do repo (`Player:getBossCooldown`) é por **GUID de personagem**.
> Cooldown por conta é intencionalmente diferente — impede trocar de personagem
> para resetar o respawn inicial. É código novo, não reuso.

A entrada pública nunca fica em cooldown.

---

# 13. Limpeza

## 13.1 Sequência

1. bloquear novas entradas;
2. slot → `CLEANING`;
3. cancelar os `addEvent` de respawn (`stopEvent` nos handles guardados);
4. cancelar eventos do `runId`;
5. `slotZone:removeMonsters()`;
6. remover itens temporários (§13.2);
7. restaurar portas e objetos interativos;
8. limpar referências;
9. slot → `FREE`.

## 13.2 Itens — use o cache, não varredura

⚠️ A v1 pedia "100 tiles por ciclo". Desnecessário.

`Zone:getItems()` devolve um cache vivo de weak_ptr mantido incrementalmente por
`Tile::addThing`/`removeThing` (`src/items/tile.cpp:1983,2004,556`) — ou seja,
**já rastreia loot e corpos dropados em runtime**. Custo O(itens), não O(tiles).

`Zone:removeMonsters()` idem, sobre o cache de criaturas
(`src/items/tile.cpp:1989,2010`).

Remover: corpos, loot no chão, backpacks, moedas, parcels, magic fields, runas,
summons, criaturas, objetos temporários. **Objetos fixos do template não.**

Para whitelist de itens não-removíveis, copie o loop de
`SvargrondArena.resetPit` (`svargrond_arena.lua:207-246`) — único precedente do
repo.

## 13.3 Tag de instância

⚠️ **Não existe storage por criatura.** Sem `Creature:setStorageValue`, sem
`Monster:kv` — `kv()` só existe em `Player`.

**Preferido: derivar da posição.**

```lua
local zone = Zone.getByPosition(monster:getPosition())
```

Elimina a necessidade de `runId` nos monstros por completo.

Se precisar de tag explícita: tabela Lua indexada por `monster:getId()`, com
limpeza num CreatureEvent `onDeath`/`onRemove` registrado na criação. **Nunca**
use o `monsterStorage` da lib (§5.1).

---

# 14. Logout, morte e restart

## 14.1 Logout — quem sai, sai

Sem `NOLOGOUT` (§6.3), o jogador **pode** deslogar dentro da instância. A regra
é **incondicional e sem exceção**:

> **Deslogou dentro, nasce fora. Não existe reconectar para dentro.**

- **na saída**: `afterLeave` da zona, alimentado pelo hook de remoção
  (`src/game/game.cpp:1585`), tira o jogador da execução na hora;
- **na volta**: `instance_login.lua` (§6.3) teleporta para o retorno global se
  a posição de login cair dentro de qualquer slot.

Um único teste, sem estado intermediário, cobre logout voluntário, queda de
conexão, crash de cliente e instância órfã por restart.

## 14.2 Desconexão — remoção imediata

Desconectar é **saída definitiva**, igual a usar a porta:

- o membro sai da execução no ato;
- **os demais continuam** — a execução não é encerrada (§11.3);
- ele **não volta** para aquela execução;
- **o cooldown é aplicado** (ver abaixo).

Quando o último membro sai ou cai, a execução encerra e o slot vai para
`CLEANING` após `emptyGraceMinutes` — o intervalo existe só para não fazer
teardown a cada oscilação, não para permitir reentrada.

### ⚠️ O cooldown TEM de valer na desconexão

Se cair fora não gastasse cooldown, a desconexão viraria **o caminho do
exploit** que o cooldown existe para fechar (§12.3): entrar, matar o respawn da
entrada, derrubar o cliente, entrar de novo num slot limpo, repetir.

Por isso o cooldown por conta é aplicado em **toda** saída — porta, morte,
logout e queda de conexão.

**Preço aceito conscientemente:** uma queda de internet de 30 segundos custa a
execução e mais `reentryCooldownMinutes` de espera. É o preço de fechar o
exploit sem introduzir máquina de estado de reconexão. A entrada pública
continua livre nesse período.

### O que isso removeu da v1

`disconnectGraceMinutes`, o estado `GRACE`, `eligible_for_reconnect` e toda a
lógica de reentrada saíram. Menos estado, menos caminho para bug.

## 14.3 Morte

Morte funciona normalmente. Só o morto deixa a instância, não pode retornar,
recebe cooldown. O corpse permanece até a limpeza. A execução termina quando não
houver participantes ativos.

## 14.4 Restart

Execuções **não** são restauradas. No startup:

1. carregar as N cópias por `loadMapChunk` (§3.1);
2. criar as N zonas e suas áreas (§8.4);
3. todos os slots nascem `FREE`;
4. jogadores cuja posição de login caia dentro de uma área de instância são
   movidos para o retorno global.

O passo 4 é o que impede jogador preso em instância órfã. Use
`Zone.getByPosition` no `onLogin`.

---

# 15. Segurança

O cliente pode enviar apenas: `public`, `private`, `cancel`.

O cliente **não** define: slot, runId, lista de membros, posição, elegibilidade,
cooldown, skull, duração, multiplicador, recompensa, estado do slot.

Toda validação ocorre no servidor. O único gate nativo do ModalWindow é
`hasModalWindowOpen` + token one-shot — **`buttonId` e `choiceId` não são
validados em C++** (§9.3).

---

# 16. Persistência — zero tabelas obrigatórias

## 16.1 Onde cada coisa vive

| Dado | Onde | Por quê |
|---|---|---|
| Template (coordenadas, limites, textos) | arquivo Lua de config | é o padrão dos 60 BossLevers |
| Estado dos slots | **tabela Lua em memória** | efêmero; reconstruído no boot (§14.4) |
| Execução em andamento (`run`) | memória; KV só se precisar sobreviver a restart | §14.4 diz que não sobrevive |
| Membros autorizados | campo dentro do `run`, em memória | |
| **Cooldown** | **`player:kv()`** | precedente direto: cooldown de boss |
| Posição de retorno | `run.members[guid].returnPos`, em memória | run não sobrevive a restart |

## 16.2 KV

```lua
local kv = player:kv():scoped("hunt-instance"):scoped(template.slug)
kv:set("cooldown", os.time() + template.reentryCooldownMinutes * 60)
```

`player:kv()` = `g_kv().scoped("player"):scoped(GUID)` → **por personagem**. Para
cooldown por conta (§12), use o escopo global:

```lua
KV.scoped("hunt-instance"):scoped(template.slug):scoped(tostring(player:getAccountId()))
```

Persiste em `kv_store(key_name varchar(191) PK, timestamp bigint, value longblob)`
(`schema.sql:861`), valor protobuf — suporta arrays e maps aninhados.
`kv.keys(prefix)` enumera por prefixo.

⚠️ **KV não é write-through.** Só vai pro disco no save global
(`SaveManager::saveAll` → `kv.saveAll()`, `src/game/scheduling/save_manager.cpp:211`)
ou quando o LRU despeja a chave. Crash entre saves perde escritas. Para cooldown
de hunt isso é aceitável — é exatamente o que o jogo já faz com cooldown de boss.

## 16.3 SQL — opcional, só para histórico

Se quiser relatório/BI, **uma** tabela append-only.

⚠️ O caminho da v1 (`database/migrations/add_hunt_instances.sql`) **não existe**.
O padrão real é `data-otservbr-global/migrations/<N>.lua`, driver em
`src/database/databasemanager.cpp:88`, versão em `server_config.db_version`.
Modelo a copiar: `migrations/58.lua` (`db.tableExists` como guard + `db.query`).

Próximo slot livre: **59**. ⚠️ O contador é compartilhado com o upstream Canary —
se o upstream lançar o 59, colide. **Numere bem acima (ex.: `900.lua`)** para
reservar faixa própria.

⚠️ Escreva com **`db.asyncQuery`**. `db.query` é síncrono e trava o game loop
(`src/database/database.cpp:251`). E não existe `affectedRows` nem API de
transação em Lua — não emule com `db.query("BEGIN")`: a conexão é única e
compartilhada com o thread pool de `DatabaseTasks`.

---

# 17. Estrutura de código

```text
data-otservbr-global/scripts/custom/hunt_instances/
├── config.lua                    -- HuntInstances.thaisCyclops
├── instance_pool.lua             -- slots, zonas, alocação
├── instance_manager.lua          -- runs, entrada, saída, teleporte
├── instance_eligibility.lua      -- skull, PvP lock, cooldown
├── instance_spawns.lua           -- respawn em Lua (§7.1)
├── instance_cleaner.lua          -- teardown (§13)
├── instance_zone_events.lua      -- ZoneEvent: beforeLeave/afterLeave
├── thais_cyclops_selector.lua    -- action 65001 + ModalWindow
├── instance_login.lua            -- resgate de jogador em instância órfã
├── instance_death.lua
└── instance_startup.lua          -- loadMapChunk × N + criação das zonas

data-otservbr-global/world/custom/
└── thais_cyclops_instance.otbm   -- 1 arquivo, sem towns/waypoints
```

(`data-otservbr-global/scripts/custom/` já existe, com 4 arquivos — convenção
válida e com precedente.)

Sem `instance_database.lua` (§16), sem `instance_ready_check.lua` (§9.2).

---

# 18. Interfaces

```lua
InstanceEligibility.canViewPrivateOption(player)
InstanceEligibility.canEnterPrivateInstance(player)
InstanceEligibility.isRestrictedSkull(player)
InstanceEligibility.hasPvpLock(player)
InstanceEligibility.hasCooldown(player, templateSlug)   -- por accountId
InstanceEligibility.validateEntry(leader, template)     -- solo ou party

InstancePool.allocate(template)          -- primeiro FREE, ou nil
InstancePool.release(slot, reason)
InstancePool.getAvailableCount(template)
InstancePool.getSlotByPosition(position) -- via Zone.getByPosition

InstanceManager.createRun(template, slot, participants)
InstanceManager.enterRun(player, run)
InstanceManager.exitRun(player, reason)
InstanceManager.abortRun(run, reason)
InstanceManager.getPlayerRun(player)     -- via posição, não lookup

InstanceSpawns.start(run)                -- agenda os addEvent
InstanceSpawns.stop(run)                 -- stopEvent em todos os handles

InstanceCleaner.clean(slot)
InstanceCleaner.removeMonsters(slot)     -- zone:removeMonsters()
InstanceCleaner.removeTemporaryItems(slot) -- zone:getItems()
```

---

# 19. Configuração

```lua
HuntInstances = {
    thaisCyclops = {
        slug    = "thais_cyclops",
        enabled = true,

        selectorActionId = 65001,
        exitActionId     = 65002,

        -- geometria (faixa validada na Etapa 0, folga de 3841 tiles)
        templatePath   = "world/custom/thais_cyclops_instance.otbm",
        templateOrigin = Position(0, 0, 0),   -- preencher após o recorte
        slotOrigins = {
            Position(36864, 36864, 7),
            Position(37376, 36864, 7),
            Position(37888, 36864, 7),
            Position(38400, 36864, 7),
            Position(38912, 36864, 7),
            Position(39424, 36864, 7),
        },
        areaSize = { width = 256, height = 256, floors = 3 },

        -- mundo global
        globalEntry     = Position(0, 0, 0),
        globalReturn    = Position(0, 0, 0),
        emergencyReturn = Position(0, 0, 0),
        globalReturnRadius = 2,

        -- tiles de consentimento (§9.2)
        playerPositions = {
            { pos = Position(0,0,0), teleport = Position(0,0,0), effect = CONST_ME_TELEPORT },
            -- ... 5 no total
        },

        -- pool
        maximumSlots = 6,

        -- tempo
        maximumDurationMinutes = 120,
        emptyGraceMinutes      = 3,   -- atraso de teardown, nao janela de volta
        reentryCooldownMinutes = 5,

        -- party
        allowSolo              = true,
        allowParty             = true,
        minimumPartyMembers    = 2,
        maximumInstanceMembers = 5,
        requireAllPartyMembers = true,
        requireSameFloor       = true,

        -- regras
        allowLateEntry                = false,
        allowReentryAfterVoluntaryExit = false,
        keepRunAfterLeaderExit        = true,
        keepRunAfterPartyDisband      = true,

        restrictedSkulls   = { SKULL_WHITE, SKULL_RED, SKULL_BLACK },
        blockDuringPvpLock = true,
        removeDroppedItemsOnCleanup = true,

        -- paridade com a pública: sem multiplicadores
        privateExperienceMultiplier = 1.0,
        privateLootMultiplier       = 1.0,
        privateSpawnMultiplier      = 1.0,

        spawns = {
            -- { monster = "Cyclops", relative = {x=21,y=34,z=0}, respawnMs = 60000 },
        },
    }
}
```

Removidos da v1: `initialWarmSlots`, `minimumWarmSlots` (§8.1),
`partyReadyCheckSeconds` (§9.2), `partyStagingRadius` (substituído pelos tiles).

---

# 20. Cenários de teste

Mantidos da v1: entrada pública; privada solo; white/red/black skull; PvP após
abrir a janela; party válida; membro distante; membro PK; teleporte parcial;
saída normal; saída individual; saída do líder; party desfeita; morte;
capacidade máxima; limpeza; restart; 100 ciclos.

Removidos: ready check recusado/expirado (§9.2 eliminou o mecanismo);
concorrência com duas requisições simultâneas (§8.3 — single-threaded torna o
cenário impossível); **reconexão para dentro e grace expirada** (§14.2 — não
existe mais reentrada).

Substituídos por:

| # | Cenário | Critério |
|---|---|---|
| L1 | Deslogar dentro e voltar | **nasce no retorno global**, fora da instância |
| L2 | Deslogar dentro, voltar, tentar entrar de novo | barrado pelo cooldown |
| L3 | Um membro cai, os outros seguem | execução continua; ele não volta a ela |
| L4 | Último membro cai | execução encerra e o slot é limpo |
| L5 | Matar spawn da entrada e derrubar o cliente | **cooldown aplicado** — o exploit não passa |

## Novos — cobrem as armadilhas descobertas

| # | Cenário | Critério |
|---|---|---|
| N1 | Matar 50 ciclopes na instância | contador de bestiary sobe igual ao da hunt pública |
| N2 | Matar ciclope na instância com charm ativo | charm dispara |
| N3 | Comparar loot de 100 kills instância vs pública | distribuição equivalente |
| N4 | Monstro perseguindo jogador até a borda | não sai da zona (`trapMonsters`) |
| N5 | 100 ciclos entrar/matar/sair | `spawnMonsterList` não cresce; nenhuma zona nova criada |
| N6 | Jogador tenta deslogar dentro | bloqueado (NOLOGOUT) ou tratado por script |
| N7 | Jogador anda durante a ModalWindow do líder | não trava o fluxo (§9.2 já evita para os membros) |
| N8 | Restart com jogador dentro | volta ao global no login (§14.4) |
| N9 | Sair por porta, escada, buraco, corda e teleport | todas passam pelo `beforeLeave` |
| N10 | Trocar de personagem para burlar cooldown | bloqueado (cooldown por accountId) |

---

# 21. Ordem de implementação

## Etapa 0 — Medição (bloqueia tudo)

- [x] **validar faixa de coordenadas no `otservbr.otbm` real** — `x 5000-6200`
      da v1 está OCUPADA (colide com a área `4864,4864,7`); adotado
      `(36864, 36864, 7)` com 3841 tiles de folga.
      Ferramenta: `tools/mapa/scan_ocupacao.py` (§3.1).
- [x] **localizar os limites reais da hunt** — `x 32400-32536 / y 32032-32120 /
      z 5-9`, 137×89×5, 99 ciclopes, núcleo em z=8.
      Ferramenta: `tools/mapa/achar_hunt.py` (§6.1).
- [x] **auditar o recorte contra duplicação** — recorte base limpo (0 teleports,
      0 action ids, 0 unique ids, 0 depots; 8 portas). Ferramenta:
      `tools/mapa/perigos_recorte.py` (§6.2).
- [x] **definir a margem de terreno** — 16 tiles (`x 32384-32552 /
      y 32016-32136`). A de 32 foi rejeitada por trazer teleport para o mapa
      global (§6.1.1).
- [x] **resolver fidelidade de coordenada** — tradução no minimapa do OTClient,
      hook confirmado em `modules/game_minimap/minimap.lua:18-40` (§3.2.1).
- [x] **recortar o chunk** — feito por script, não no Remere's:
      `tools/mapa/recortar.py`, validado por `tools/mapa/testar_recortar.py`
      (12/12 checks) e auditado com `perigos_recorte.py` sobre o arquivo gerado.

      ```text
      thais_cyclops_instance.otbm   572 KB
      169 x 121, andares 5-9,  56.876 tiles,  25.776 itens,  710 tipos
      coordenadas REBASEADAS para origem 0 em x/y; z absoluto
      auditoria do arquivo gerado: 0 teleport, 0 action id, 0 unique id,
                                   0 depot, 0 porta de casa
      ```

      ⚠️ **Rebase é obrigatório, não estética.** O carregador faz
      `x = base_x + tileCoordsX + pos.x`. Com coordenada absoluta (32384) mais
      offset (36864) daria 69248 — **estouro do `uint16`**, mapa corrompido em
      silêncio. Carregue sempre com `pos.z = 0`, pois o z já é absoluto.

      ⚠️ **Três coisas que o Canary exige e não são óbvias** (custaram 3
      restarts para descobrir, porque `Map::load` engole o `e.what()` e só loga
      `"missing or corrupted"`, `src/map/map.cpp:153`):

      1. o `MAP_DATA` precisa de **pelo menos um atributo** (`DESCRIPTION`);
      2. precisa dos nós **`TOWNS` e `WAYPOINTS`, ainda que vazios** — o
         `parseTowns`/`parseWaypoints` roda logo após o tile area. Vazio não
         sobrescreve nada global, então não conflita com a §6.2;
      3. `OTBM_TILE_ZONE` (19) é filho de **tile**, e item pode ter **itens
         aninhados** (container). Ignorar qualquer um dos dois desalinha o
         parser e o recorte sai corrompido em silêncio.

      Referência de formato conhecido-bom para comparar:
      `world/world_changes/fury_gates/carlin.otbm` (2 KB).

      ⚠️ 9.424 tiles de casa tiveram o vínculo removido (viram tile comum).
      É praticamente toda a margem oeste — ali existe um bairro residencial.
      Decidir se compensa manter (cenário real, §6.1.1) ou aparar a margem
      oeste para economizar ~16% do chunk.
- [x] **provar que o chunk carrega** — 6 cópias carregadas e verificadas em
      jogo (`Tile(pos):getGround()` respondeu em **6/6** slots, chão id 101).
- [x] **medir custo de memória das 6 cópias** — ver abaixo.
- [x] **decidir NOLOGOUT vs forge** — decidido: **sem NOLOGOUT**, para
      preservar influenced/fiendish. Não custa código, porque o handler de
      login já é exigido pela §14.4. Justificativa completa na §6.3.
- [ ] **medir RSS com os monstros vivos** — só possível depois da Etapa 3
      (spawns em Lua). Geometria já se provou irrelevante; monstros são o
      custo real (§4.2). **Não bloqueia as Etapas 1-2.**

---

## Etapa 0 — ENCERRADA

Tudo que bloqueava está resolvido. O único item restante (RSS com monstros)
depende da Etapa 3 existir e não impede seguir.

### Custo medido — geometria é irrelevante

| Boot | RSS após ~1 min |
|---|---|
| cargas falharam (nenhuma instância) | 1.425.508 KB |
| **6 cópias carregadas** | 1.423.412 KB |

**Diferença dentro do ruído.** A estimativa teórica de 2790 KB/cópia estava
conservadora por mais de uma ordem de grandeza, porque `setBasicTile` só grava
um ponteiro num cache deduplicado e os tipos de item já existem no mapa
principal (`MapCache`, `src/map/mapcache.cpp:65-177`).

**Consequência para a §4.2:** o teto do pool **não é a geometria**. Pode-se
manter os 6 slots do piloto com folga enorme, e a decisão de escalar depende
só do custo de monstros.

⚠️ **O tempo de `loadMapChunk` não é mensurável neste binário.** A linha
`"Map Loaded ... in {} milliseconds"` é `g_logger().debug`
(`src/io/iomap.cpp:90`), e o `config.lua.dist` avisa: *"Debug and trace logs
are only available if compiled in debug mode"*. O binário de produção é
release. Observação indireta: as 6 cargas terminaram entre o pedido e a
verificação seguinte, em menos de ~150 ms no total.

## Etapa 1 — Mapa

- limpar o OTBM: sem towns, sem waypoints, sem houses, sem quest chests (§6.2);
- definir origem do template e as N origens de slot;
- desenhar tiles de entrada, saída e os `playerPositions`.

## Etapa 2 — Pool

- `instance_startup.lua`: `loadMapChunk` × N + criar N zonas com `addArea`;
- estados de slot em memória, alocação da §8.3;
- `trapMonsters` em cada zona.

## Etapa 3 — Spawns

- respawn em Lua com `addEvent`/`stopEvent` (§7.1);
- validar paridade: bestiary, charms, loot (cenários N1-N3).

## Etapa 4 — Entrada

- seletor com actionId 65001 + ModalWindow do líder (§9.3);
- consentimento por tiles via `Lever` (§9.2);
- elegibilidade em três etapas (§10).

## Etapa 5 — Execução e saída

- `runId`, snapshot de membros, posições de retorno;
- `ZoneEvent.beforeLeave` como chokepoint (§11.1);
- duração, avisos, cooldown por conta.

## Etapa 6 — Limpeza e recuperação

- teardown da §13;
- login/logout/morte/restart (§14);
- cenário N5 (100 ciclos, sem vazamento).

---

# 22. Critérios de aceite

Mantidos da v1, mais:

- **nenhum arquivo `.cpp`/`.hpp` modificado**;
- bestiary, charms e loot equivalentes à hunt pública (N1-N3);
- `spawnMonsterList` não cresce após 100 ciclos (N5);
- nenhuma zona criada fora do pool fixo;
- monstros não saem da área da instância (N4);
- todas as saídas passam pelo `beforeLeave` (N9);
- cooldown resiste a troca de personagem (N10);
- restart não deixa jogador preso (N8).

---

# 23. Depois do piloto — de hunt única a catálogo

Esta seção **não faz parte do piloto**. Registra as decisões de arquitetura
para quando houver mais de uma hunt, para que o piloto não seja construído de
um jeito que atrapalhe.

Vale a ordem: **terminar Ciclopes de Thais à mão, ver quais informações foram
de fato necessárias, e só então generalizar.** Generalizar antes de ter um caso
completo é inventar requisito.

## 23.1 Motor genérico, hunt como dado

O código de instância não pode conhecer "Ciclopes de Thais". Reservar slot,
validar PK e party, teleportar, spawnar, limpar, devolver ao global, aplicar
cooldown e recuperar de restart são genéricos.

Cada hunt vira um pacote:

```text
data-otservbr-global/hunts/thais_cyclops/
├── manifest.lua        -- config declarativa
├── map.otbm            -- recorte, coordenadas rebaseadas
├── spawns.lua          -- posicoes RELATIVAS + respawn
└── compatibilidade.lua -- relatorio do scanner
```

⚠️ **Manifesto em Lua, não YAML.** O Lua do Canary não tem parser de YAML —
seria dependência nova para ganhar nada. O idioma do próprio codebase já é
tabela Lua declarativa: é assim que o `BossLever` configura 60 bosses
(`data/libs/functions/boss_lever.lua`). YAML serve do lado do ferramental em
Python; no runtime, não.

## 23.2 Área de hunt é multi-retângulo, não bounding box

**Medido, não suposto:** a bounding box da hunt dos ciclopes arrastou junto
**9.424 tiles de casa** — um bairro residencial, ~16% do recorte — porque a
hunt não é retangular.

Cada hunt precisa aceitar **vários retângulos por andar**:

```lua
zonasPublicas = {
    [7] = { {de = {x=..., y=...}, ate = {x=..., y=...}} },
    [8] = { {de = ...}, {de = ...} },   -- cave em L, areas desconexas
}
```

## 23.3 O que NÃO limita a escala — medição

A intuição de que "seis cópias de cada hunt explodem o mapa" **está errada
neste servidor**:

| | |
|---|---|
| RSS com zero instâncias | 1.425.508 KB |
| RSS com 6 cópias carregadas | 1.423.412 KB |
| Slots de 256×256 que cabem após o mapa oficial | 3.660 |

Geometria é esparsa, deduplicada e materializada preguiçosamente (§4.2).
**Slot vazio é praticamente grátis.**

O que **de fato** limita:

1. **Monstros.** São permanentes e `Game::updateForgeableMonsters`
   (`src/game/game.cpp:12066`) varre todos, sem filtro de região.
2. **Ausência de unload** — toda região carregada fica até o processo morrer.

→ **Consequência para a política de pool:** o tier (`HOT`/`NORMAL`/`COLD`) deve
governar **quantos slots têm monstro vivo**, não quantos têm geometria. Se o
slot só spawnar durante execução ativa, slot ocioso não pesa e a política de
geometria vira desnecessária.

## 23.4 Um arquivo por hunt, sem atlas

Uma proposta intermediária sugeria gerar um `instance_atlas.otbm` único com
todos os slots de todas as hunts. **Rejeitado.**

`Game.loadMapChunk(path, offset)` carrega **o mesmo arquivo em N posições** —
verificado no piloto: 6 slots carregados de um único arquivo de 572 KB
(§21, Etapa 0). Um atlas único obrigaria a regerar e recarregar tudo a cada
mudança em qualquer hunt, e reintroduziria justamente o risco de sobreposição
que ele pretendia evitar.

**Um `map.otbm` por hunt + N chamadas com offset.** Sem build step.

## 23.5 Scanner de dependências — a peça mais valiosa

Mapear geometria não basta. O piloto provou por quê:

> O `aid 48063` dentro da margem é um teleport da quest Heart of Destruction
> (`scripts/quests/heart_of_destruction/movements_teleport.lua:5`) que manda
> para `Position(32448, 32389, 10)` — o mapa global. A varredura de tiles
> reportava **"0 teleports"**, porque ele não é um `TELE_DEST` do OTBM: é um
> *movement em Lua indexado por action id*.

Ou seja, o scanner **precisa cruzar os action/unique ids achados no mapa contra
os scripts do datapack** — não basta procurar coordenadas literais. Já
implementado em `tools/mapa/perigos_recorte.py`.

Deve procurar, dentro da área: coordenadas absolutas em scripts, `uniqueId`,
`actionId`, teleports, quest chests, NPCs, bosses, alavancas, portas, storages
e raids.

## 23.6 Classificação

| Categoria | Característica | Tratamento |
|---|---|---|
| `SIMPLE` | monstros, escadas, saídas comuns | instanciável direto |
| `ADAPTED` | portas, alavancas, teleports locais | adaptador pequeno |
| `COMPLEX` | quest, NPC, boss, estado persistente | revisão caso a caso |
| `GLOBAL_ONLY` | world boss, cidade, casa, evento | **não instanciar** |

Instanciar tudo não é meta. Parte do mundo deve continuar pública para
preservar encontro entre jogadores, competição e economia.

## 23.7 Ferramental — já existe metade

As ferramentas do piloto **já são o embrião do mapper**, porque recebem mapa e
região arbitrários. Não precisam ser reescritas; falta um manifesto por cima.

| Ferramenta | Papel no catálogo |
|---|---|
| `achar_hunt.py` | agrupa spawns em 3D → hunts candidatas |
| `scan_ocupacao.py` | acha faixa livre para os slots |
| `checar_recorte.py` | inventário do que há na área |
| `perigos_recorte.py` | scanner de compatibilidade (§23.5) |
| `recortar.py` | gera o `map.otbm` com coordenadas rebaseadas |
| `validar_otbm.py` | confere que o recorte carrega |
| `achar_posicoes.py` | escolhe tiles seguros de entrada |

Falta: detecção de região caminhável (flood fill) e revisão visual.

⚠️ **Flood fill precisa de âncora**, senão uma cave ligada ao exterior engole
meio mapa. Os **389 ids de `floorchange`/`teleport`** que o `achar_posicoes.py`
já extrai do `items.xml` dão a fronteira natural; o resto o operador marca.

⚠️ **Revisão visual: começar por PNG estático.** O `gerar_minimapa.py` já
produz `previa_minimapa.png`. Um overlay dos retângulos candidatos entrega
quase toda a revisão por uma fração do custo de uma interface web. Só construir
web se o estático provar ser insuficiente.

## 23.8 Slots por demanda, medidos

Registrar por hunt: solicitações de instância, recusas por lotação, pico
simultâneo, duração média. Depois de alguns dias, o número de slots sai do dado
em vez do palpite — e, pela §23.3, o que se dimensiona é **monstro vivo**, não
geometria.
