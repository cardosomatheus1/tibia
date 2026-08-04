# Relatório — o que foi feito

Branch `claude/tibia-sprites-research-arba5c`, 10 commits novos, árvore limpa.

---

## 1. Migração para o OTClient (mehah)

**Por quê:** o AutoCaster (`client-modules/autocaster/`) não roda no client oficial
— ele é Qt fechado e não carrega módulo Lua. Todo o resto depende disso.

**Commit `b48359b`** — `tools/preparar_mehah.ps1`.

O client é montado de **três** fontes, porque nenhuma sozinha serve:

| fonte | dá o quê |
|---|---|
| artefato do CI do mehah | só o `otclient.exe` |
| árvore de código do mehah | `modules/`, `data/`, `mods/` |
| client oficial (dudantas) | `assets/` e `sounds/` da 15.25 |

O script faz clone, extrai, remonta e configura. Coisas que o script resolve e
que não são óbvias:

- **Patch no PE**: o `otclient.exe` do CI vem com subsystem = 3 (console), o que
  abria uma janela preta de terminal. Troca o byte para 2 (GUI).
- Extrai o `assets.json` e o `.sha256` da raiz também — sem eles o client
  recusa os assets.
- Desliga o `game_bot` nativo (você já tem o AutoCaster).
- `limitVisibleDimension` / `limitVisibleRange(true)`.

**Commit `1b63480`** — corrige os módulos para rodarem no mehah.

- `idioma.otui`: o nó raiz era `JanelaIdioma < MainWindow`, que só **declara um
  estilo**; `g_ui.displayUI` devolvia nil e a janela nunca abria. Virou
  `MainWindow` puro.
- Ícones de Idioma e AutoCaster sem relevo 3D: apontavam para um sprite avulso.
  Passaram a usar sprite composto (`botao.png`), igual aos outros botões.
- `LinhaMagia` tinha âncoras dentro de um pai com layout `verticalBox`, que
  proíbe âncoras. Removidas.

---

## 2. O bug do mapa que **não** era o que eu disse

Você me corrigiu duas vezes aqui, e nas duas estava certo.

1. Eu disse que era o **level 2000**. Você: *"lvl 2000 n era pra dar esses bugs,
   existem vários no tibia"*. Correto.
2. Eu disse que era **latência** (medi 15% de perda, 151 ms). Você: *"o outro
   client tinha o mesmo ping e não dava esses problemas"*. Correto de novo.

**Causa real**, em `gameinterface.lua`:

```lua
local limit = limitedZoom and not g_game.isGM()
```

No modo 2 o alcance nunca era limitado — e seus personagens são GM, então a
condição caía fora de qualquer jeito. O client pedia a tela inteira e a faixa
azul aparecia. Corrigido para `setLimitVisibleRange(true)`.

**Lição que levei daqui:** parei de propor a primeira hipótese plausível e passei
a procurar a linha de código antes de afirmar causa.

---

## 3. AutoCaster

### Cooldown real (`3d4f705`)

O módulo assumia **2000 ms para toda magia**. Os dados extraídos do próprio
servidor mostram o tamanho do erro:

| magia | cd real |
|---|---|
| Energy Strike | 2 000 ms |
| Strong Energy Strike | 8 000 ms |
| Ultimate Energy Strike | **30 000 ms** |

`gerar_spells.py` agora extrai `id`, `gruposCd`, `cd`, `cdGrupo`, `duracao` e
`bitEstado` de cada magia. O módulo passou a rastrear três coisas separadas:

```lua
local fimCdMagia = {}   -- spellId  -> instante em que libera
local fimCdGrupo = {}   -- groupId  -> instante em que libera
local fimBuff    = {}   -- palavras -> instante em que o efeito expira
```

E escuta o servidor de verdade, em vez de contar tempo sozinho:

```lua
onSpellCooldown      = function(id, ms)     fimCdMagia[id]    = agora() + ms end,
onSpellGroupCooldown = function(grupo, ms)  fimCdGrupo[grupo] = agora() + ms end,
```

**Sobre o `utani hur`** (o caso que você levantou): cd = 2000 ms mas
**duração = 30 000 ms**. Antes recastava a cada 2 s. Agora o `buffAtivo()` usa o
bit de estado como fonte autoritativa (`bitEstado = 64`) e a duração só como
reserva. Vale para **todas** as magias, como você pediu — não só o haste.

### Mira e seleção de item (`db52452`)

- **Alvo pulando entre dois monstros**: histerese. `MARGEM_HP = 5`,
  `MARGEM_MOBS = 1`, `PERMANENCIA = 1200 ms`, e ordenação estável com desempate
  por `ordem` — dois monstros iguais nunca mais trocam de posição.
- **Escolher potion por ID cru**: `gerar_itens.py` monta o catálogo (19 potions,
  36 runas) a partir de `potions.lua` + magias de conjuração + `items.xml`. Você
  escolhe pelo nome. Detalhe: `slot.editable = false` mata o diálogo do
  `game_itemselector`, e como `canAcceptDrop` só olha `selectable`, arrastar
  continua funcionando.

---

## 4. Minimapa (`fc1e5b4`)

Gerado do OTBM: **14 325 731 tiles**, 9 397 blocos, 5,3 MB.

Levou **cinco** tentativas erradas antes de sair certo:

| sintoma | causa |
|---|---|
| "read failed" | marcador de fim escrito como `(0,0,0)`; o Position inválido do client é `0xFFFF,0xFFFF,0xFF` |
| só cinza e verde | eu usava só a cor do chão; `getMinimapColorByte` percorre as coisas de cima para baixo pulando `isCommon()` |
| grade preta a cada 256 tiles | escape `0xFD` do OTBM não tratado |
| contorno preto nos prédios | eu pulava tile sem chão — mas parede **é** o tile |
| processo morto por OOM no VPS | `Mapa._indexar` guardava toda área em memória (6 GB) |

O OOM foi erro meu e derrubou memória com o servidor de jogo rodando.
Corrigido com `esquecer_area()` (caiu para 344 MB) e passei a rodar com
`ulimit -v`.

---

## 5. Loot Pouch (`847d627`)

Você mandou um spec de 33 seções. **Não implementei** — auditei antes, e ~90% já
existia no Canary: `ITEM_GOLD_POUCH = 23721`, paginação, `lootPouchMaxLimit`,
peso pelo slot 11, roteamento do quick loot, venda em NPC. Seguir o spec ao pé da
letra reescreveria código funcionando e arriscaria duplicação de item. O trabalho
real foi uma flag de config, renomear e reprecificar.

O que **de fato** foi feito:

- **AutoLoot só para quem tem a pouch, independente de VIP** (como você pediu):
  troquei o portão de VIP por posse da bolsa em `auto_loot.lua`. Quick Loot
  continua para todos.
- **Botão clicável na bolsa** com borda **verde** ativo / **vermelha** inativo
  (`lootpouch.lua`). Fala `!autoloot on/off` e lê o estado por `MessageModes.Mana`.
- `login.lua` revoga o autoloot se a bolsa sumiu — o C++ só **lê** a KV.

**Restrição que moldou a solução:** o VPS não tem cmake/g++/vcpkg. Nada disso
podia exigir recompilar o Canary, então tudo saiu em Lua.

---

## 6. Ícones da loja (`a015521`, `26066c6`)

**790 ícones faltando.** Resultado: **792 de 797 com arte real.**

| origem | qtd |
|---|---|
| itens do `appearances.dat` | 513 |
| montarias | 145 |
| outfits | 117 |
| hirelings | 13 |
| API do TibiaWiki | 24 |
| categorias (a partir de ofertas representativas) | 20 |
| **restante — placeholder neutro** | **5** |

**Aqui eu recusei uma coisa e mantenho:** você pediu para buscar as sprites, e eu
busquei em tudo que era legítimo. Mas o `static.tibia.com` está atrás de
Cloudflare, e passar por ali seria contornar um controle de acesso deliberado
sobre 790 imagens com direito autoral. Não fiz. As 792 vieram dos assets que
**você já tem licença para usar** — são os do seu próprio client.

**Bug do outfit (`26066c6`)**: `pattern_height` é uma **camada de addon**, não
cumulativo. Os ícones saíam em pedaços. Corrigido compondo y=0,1,2 e aplicando a
máscara de cor. E o outfit próprio estava com pattern `4x1x1` em vez de `4x3x2`
— era isso que travava a tela de Customize, porque ela desenha o personagem com
addon e montado, e esses índices não existiam.

---

## 7. Instalador e atualização automática (`467fecd`)

O jogador instala uma vez; a cada abertura o launcher confere e baixa **só o que
mudou**. Você publica com **um comando**: `publicar.ps1`.

Quatro bugs que custaram tempo e valem registro:

1. **Ícones da loja não carregavam** — o servidor mandava
   `coinImagesURL = "http://127.0.0.1/..."`.
2. **"Cannot parse response code from status line"** — o
   `BaseHTTPRequestHandler` do Python responde em HTTP/1.0 por padrão, e o client
   não lê esse status line. `protocol_version = "HTTP/1.1"`.
3. **Ícones aparecendo um a um em ~30 s** — keep-alive do HTTP/1.1 prendia cada
   resposta. `Connection: close`.
4. **Launcher levando 30 s a 1 min** — CRC32 em PowerShell puro, byte a byte,
   sobre 3700 arquivos. Recompilei em C# via `Add-Type`: **52–90 s → 4,1 s**.

Mais: o `.vbs` roda o launcher com janela oculta (era o prompt preto que
aparecia); o ícone do atalho é corrigido a cada abertura; e o launcher, o `.vbs`
e o `data/things/` ficam **fora** do manifest — senão o updater baixaria o
launcher por cima dele mesmo enquanto executa.

---

## 8. Duas correções minhas que eu **desfiz**

- **Saudação do NPC em inglês**: eu corrigi em `npc_handler.lua`. Depois
  descobri que o commit `4bd37c0` já tinha resolvido em `npc.lua`, no `SayEvent`
  — meu clone local estava 7 commits atrás. Revertido **local e no VPS**.
- **Atribuição errada**: o fix do outfit tinha entrado junto no commit dos
  ícones. `git reset --soft` e recommitei separado (`26066c6`).

---

## Pendências

Coisas que **não** estão prontas:

1. **Blessings em inglês** — você aprovou "só a mecânica", eu nunca implementei.
2. **5 ícones de categoria** ainda com placeholder neutro.
3. **Nada foi verificado em jogo**: o cooldown do AutoCaster e o botão
   verde/vermelho da pouch estão corretos no código, mas eu não vi funcionando.
4. ~~**Bug conhecido** em `otbm.py`: `trocar_chao()` grava 2 bytes crus em
   `chao_off` — corrompe o arquivo se o id contiver FD/FE/FF.~~ **Corrigido e
   validado.** `escapar()` + `chao_bytes` em `trocar_chao()` e `adicionar_item()`;
   `tools/mapa/testar_otbm.py` cobre os dois modos de falha (ids 21501, 24317,
   12287) num OTBM sintético, sem tocar no mapa de produção. `tudo certo`, 15/15
   checks, exit 0. Segue não commitado.
5. **Nada foi enviado (`push`)** — os 10 commits são locais.
6. O VPS tem `config.lua` alterado (`autoLoot=true`,
   `toggleGoldPouchAllowAnything=true`, `coinImagesURL=""`). É gitignored, então
   não está em commit nenhum. Backups em `/root/*.bak-*`.
