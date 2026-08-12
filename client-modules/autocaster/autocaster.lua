--[[ AutoCaster — semibot de assistencia no estilo RTCaster do RubinOT.

  Tres abas, como no original:
    Healing  -> Spell Healing, Potion Healing e Friend Healing (sio/uh em party)
    Tools    -> Auto Haste, Change Gold, Auto Eat Food, Anti Paralyze
    Caster   -> Spell Shooter e Rune Shooter, com mana%, nº de mobs e prioridade

  Automatiza EXECUCAO (curar, beber, atacar, dar sio). NAO automatiza
  NAVEGACAO: nao existe cavebot aqui, de proposito.

  So usa APIs de nucleo do OTClient => roda no OTClientV8 e no mehah.
]]

autocasterWindow = nil
local loopEvent, botao = nil, nil
local conexoes = nil  -- eventos de cooldown vindos do servidor
local abas, painel = {}, {}
local ui = {}
local cfg = nil       -- config do preset em uso
local salvar          -- declarada antes: o seletor de magias usa
local raiz = nil      -- { atual = "Default", presets = { Default = cfg } }

local TICK = 150
local PRIORIDADES = { "1st", "2nd", "3rd", "4th", "5th" }

-- ---------------------------------------------------------- config

local function linhaCura(on, texto, item, pct)
  return { on = on, texto = texto, item = item, pct = pct }
end
local function linhaShooter(on, texto, item, mana, mobs, prio)
  return { on = on, texto = texto, item = item, mana = mana, mobs = mobs, prio = prio }
end

local function padroes()
  return {
    ligado = false,
    -- Liga/desliga por categoria. As teclas de atalho mexem nestas chaves; as
    -- linhas individuais continuam mandando DENTRO de cada categoria, entao
    -- desligar aqui nao apaga a configuracao de ninguem -- so' suspende.
    chaves = { cura = true, magia = true, runa = true },
    -- Combinacao escolhida pelo jogador (ex.: "=", "'", "Ctrl+G"). "" = sem
    -- atalho. magiaRuna liga e desliga as duas categorias de uma vez, que e'
    -- o atalho que o RTCaster tem.
    teclas = { geral = "", cura = "", magia = "", runa = "", magiaRuna = "" },
    healing = {
      spell  = { linhaCura(true,  "exura gran", 0, 60),
                 linhaCura(false, "exura",      0, 80),
                 linhaCura(false, "",           0, 40) },
      potion = { linhaCura(false, "", 266, 50),    -- health potion
                 linhaCura(false, "", 268, 40) },  -- mana potion (usa mp%)
      amigo  = { linhaCura(false, "exura sio", 0, 70),
                 linhaCura(false, "",          3160, 50) },  -- uh rune
    },
    tools = {
      haste = linhaCura(false, "utani hur", 0, 0),
      changeGold = false, eatFood = false, antiParalyze = false,
    },
    target = {
      atacarAuto = false, perseguir = false,
      pararSeFraco = false, hpMinimo = 30,
      limitarMobs = false, maxMobs = 5,
      lista = { { on = false, nome = "", prio = 1, dist = 7 },
                { on = false, nome = "", prio = 2, dist = 7 },
                { on = false, nome = "", prio = 3, dist = 7 },
                { on = false, nome = "", prio = 4, dist = 7 } },
    },
    caster = {
      autoTarget = false,
      spell = { linhaShooter(false, "exori vis", 0, 30, 1, 1),
                linhaShooter(false, "exori gran", 0, 50, 3, 2),
                linhaShooter(false, "", 0, 20, 1, 3) },
      rune  = { linhaShooter(false, "", 3155, 0, 1, 1),   -- avalanche
                linhaShooter(false, "", 3191, 0, 1, 2) }, -- gfb
    },
  }
end

-- confere se o preset salvo tem todas as pecas que a interface espera
-- (evita quebrar quando a estrutura muda entre versoes do modulo)
local function configValida(c)
  if type(c) ~= "table" then return false end
  local h, t, ca = c.healing, c.tools, c.caster
  if type(h) ~= "table" or type(t) ~= "table" or type(ca) ~= "table" then return false end
  if type(h.spell) ~= "table" or #h.spell < 3 then return false end
  if type(h.potion) ~= "table" or #h.potion < 2 then return false end
  if type(h.amigo) ~= "table" or #h.amigo < 2 then return false end
  if type(t.haste) ~= "table" then return false end
  if type(ca.spell) ~= "table" or #ca.spell < 3 then return false end
  if type(c.target) ~= "table" or type(c.target.lista) ~= "table" or #c.target.lista < 4 then return false end
  if type(ca.rune) ~= "table" or #ca.rune < 2 then return false end
  return true
end

-- Campos acrescentados depois que gente ja tinha preset salvo. Preencher o que
-- falta e' melhor do que reprovar em configValida: reprovar joga fora TODA a
-- configuracao do jogador so' porque uma chave nova nao existia ainda.
local function migrarConfig(c)
  if type(c) ~= "table" then return end
  local p = padroes()
  if type(c.chaves) ~= "table" then c.chaves = p.chaves end
  if type(c.teclas) ~= "table" then c.teclas = p.teclas end
  for k, v in pairs(p.chaves) do
    if type(c.chaves[k]) ~= "boolean" then c.chaves[k] = v end
  end
  for k, v in pairs(p.teclas) do
    if type(c.teclas[k]) ~= "string" then c.teclas[k] = v end
  end
end

-- ------------------------------------------------------------ util

local function agora() return g_clock.millis() end
local function jogador() return g_game.getLocalPlayer() end

local function pctVida(c) return c and c:getHealthPercent() or 100 end

local function pctMana()
  local p = jogador()
  if not p then return 100 end
  local m = p:getMaxMana()
  if not m or m <= 0 then return 100 end
  return math.floor((p:getMana() / m) * 100)
end

local function monstrosPerto(alcance)
  local p = jogador()
  if not p then return {} end
  local lista = {}
  for _, c in ipairs(g_map.getSpectatorsInRange(p:getPosition(), false, alcance, alcance) or {}) do
    if c ~= p and c:isMonster() and not c:isDead() then table.insert(lista, c) end
  end
  return lista
end

local function maisProximo(lista)
  local p = jogador()
  if not p then return nil end
  local pos, melhor, dist = p:getPosition(), nil, 999
  for _, m in ipairs(lista) do
    local mp = m:getPosition()
    local d = math.max(math.abs(mp.x - pos.x), math.abs(mp.y - pos.y))
    if d < dist then melhor, dist = m, d end
  end
  return melhor
end

-- aliado da party com menos vida que o limite
local function amigoFerido(limite)
  local p = jogador()
  if not p then return nil end
  local melhor, menor = nil, limite
  for _, c in ipairs(g_map.getSpectatorsInRange(p:getPosition(), false, 7, 5) or {}) do
    if c ~= p and c:isPlayer() and not c:isDead() then
      local naParty = true
      if c.getShield then
        local s = c:getShield()
        naParty = (s ~= nil and s ~= 0)
      end
      local v = pctVida(c)
      if naParty and v < menor then melhor, menor = c, v end
    end
  end
  return melhor
end

local function paralisado()
  local p = jogador()
  if not p or not p.getStates then return false end
  local ok, st = pcall(function() return p:getStates() end)
  if not ok or not st then return false end
  return bit.band(st, PlayerStates.Paralyze) > 0
end

-- ------------------------------------------------------- execucao

local ultimo = {}     -- chave -> timestamp
local GCD = 1000

local function podeAgir(chave, cd)
  local t = agora()
  if (ultimo[chave] or 0) + (cd or GCD) > t then return false end
  ultimo[chave] = t
  return true
end

local function falar(texto) g_game.talk(texto) end

local function usarItem(id, alvo)
  if alvo then g_game.useInventoryItemWith(id, alvo)
  else g_game.useInventoryItem(id) end
end

-- ------------------------------------------- cooldown real e buff ativo
--
-- O servidor manda dois pacotes de cooldown: 0xA4 com o id de UMA magia e
-- 0xA5 com o id de um GRUPO. O client expoe os dois como onSpellCooldown e
-- onSpellGroupCooldown, e e' daqui que sai a disponibilidade de verdade.
--
-- Antes o modulo chutava 2000 ms para toda magia. Isso errava por muito:
-- exori max vis tem 30 s de cooldown. E o erro nao era so de tempo -- ao
-- achar que podia, ele mandava as palavras, o servidor recusava calado, e o
-- ciclo dava return como se tivesse agido. A magia da prioridade seguinte
-- nunca chegava a ser tentada.
--
-- Buff e' outra coisa: utani hur tem cooldown de 2 s mas DURA 30 s. Recastar
-- pelo cooldown gasta mana e nao adiciona nada. Por isso buff usa duracao,
-- e nao cooldown.

local fimCdMagia = {}   -- spellId -> instante em que libera
local fimCdGrupo = {}   -- groupId -> instante em que libera
local fimBuff    = {}   -- palavras -> instante em que o efeito expira

-- ao deslogar, nada do que estava contado vale mais
function limparCooldowns()
  for k in pairs(fimCdMagia) do fimCdMagia[k] = nil end
  for k in pairs(fimCdGrupo) do fimCdGrupo[k] = nil end
  for k in pairs(fimBuff) do fimBuff[k] = nil end
end

local function normalizar(t)
  return (tostring(t or ""):lower():gsub("^%s+", ""):gsub("%s+$", ""))
end

local porPalavras = nil
local function dadosDaMagia(palavras)
  local chave = normalizar(palavras)
  if chave == "" then return nil end
  if not porPalavras then
    porPalavras = {}
    for _, m in ipairs(SpellsServidor or {}) do
      porPalavras[normalizar(m.palavras)] = m
    end
  end
  return porPalavras[chave]
end

-- pronta AGORA: cooldown proprio, cooldown de cada grupo dela, mana e level.
-- Palavras que nao existem no datapack caem no cronometro antigo, para nao
-- travar quem digitou uma magia de outro servidor na mao.
local function magiaPronta(palavras)
  local d = dadosDaMagia(palavras)
  if not d then return podeAgir("livre:" .. normalizar(palavras), 2000) end

  local t = agora()
  if d.id > 0 and (fimCdMagia[d.id] or 0) > t then return false end
  for _, g in ipairs(d.gruposCd or {}) do
    if (fimCdGrupo[g] or 0) > t then return false end
  end

  local p = jogador()
  if p then
    if d.mana > 0 and p:getMana() < d.mana then return false end
    if d.level > 0 and p:getLevel() < d.level then return false end
  end
  return true
end

-- Marca o cooldown esperado ja no envio. O servidor confirma pelos pacotes e
-- corrige; isto so evita repetir a mesma magia nos 150 ms antes da resposta.
local function marcarCast(palavras)
  local d = dadosDaMagia(palavras)
  if not d then return end
  local t = agora()
  if d.id > 0 and d.cd > 0 then fimCdMagia[d.id] = t + d.cd end
  if d.cdGrupo > 0 then
    for _, g in ipairs(d.gruposCd or {}) do fimCdGrupo[g] = t + d.cdGrupo end
  end
  if d.duracao > 0 then fimBuff[normalizar(palavras)] = t + d.duracao end
end

-- Buff ainda de pe? Se a magia tem bit de estado, o bit manda -- ele percebe
-- quando o efeito cai antes da hora. Sem bit (utito tempo, utamo tempo), a
-- duracao do datapack e' a unica pista que existe.
local function buffAtivo(palavras)
  local d = dadosDaMagia(palavras)
  if not d then return false end

  if (d.bitEstado or 0) > 0 then
    local p = jogador()
    if not p or not p.getStates then return false end
    local ok, st = pcall(function() return p:getStates() end)
    if not ok or not st then return false end
    return bit.band(st, d.bitEstado) > 0
  end

  return (d.duracao or 0) > 0 and (fimBuff[normalizar(palavras)] or 0) > agora()
end

-- caminho unico de cast: checa, manda e marca
local function castar(palavras)
  if not magiaPronta(palavras) then return false end
  if not podeAgir("gcd", 250) then return false end   -- nunca duas no mesmo instante
  falar(palavras)
  marcarCast(palavras)
  return true
end

-- devolve texto do que foi feito, ou nil
local function passo()
  local p = jogador()
  if not p or p:isDead() then return nil end

  local hp, mp = pctVida(p), pctMana()
  local mobs = monstrosPerto(7)
  local alvo = g_game.getAttackingCreature() or maisProximo(mobs)

  -- A chave de cura cobre os tres blocos seguintes (magia, potion e amigo):
  -- e' isso que a tecla de atalho de "cura" liga e desliga.
  if cfg.chaves.cura then
    -- 1) cura em spell (prioridade maxima). A ordem das linhas e' a preferencia:
    -- se a de cima nao esta pronta de verdade, a de baixo e' tentada.
    for _, l in ipairs(cfg.healing.spell) do
      if l.on and l.texto ~= "" and hp < l.pct and castar(l.texto) then
        return l.texto .. " (hp " .. hp .. "%)"
      end
    end

    -- 2) potions: a primeira usa hp, a segunda usa mp
    for i, l in ipairs(cfg.healing.potion) do
      local valor = (i == 1) and hp or mp
      if l.on and l.item > 0 and valor < l.pct and podeAgir("hp" .. i, 900) then
        usarItem(l.item, p); return "potion " .. l.item .. " (" .. valor .. "%)"
      end
    end

    -- 3) cura de amigo (sio por spell, uh por runa)
    for i, l in ipairs(cfg.healing.amigo) do
      if l.on then
        local amigo = amigoFerido(l.pct)
        if amigo then
          -- o sio leva o nome no fim, entao nao passa pelo castar()
          if l.texto ~= "" and magiaPronta(l.texto) and podeAgir("gcd", 250) then
            falar(l.texto .. ' "' .. amigo:getName())
            marcarCast(l.texto)
            return l.texto .. " -> " .. amigo:getName()
          elseif l.texto == "" and l.item > 0 and podeAgir("am" .. i, 1000) then
            usarItem(l.item, amigo)
            return "runa " .. l.item .. " -> " .. amigo:getName()
          end
        end
      end
    end
  end

  -- 4) tools
  -- Haste (e qualquer buff posto nessa linha) vai por DURACAO, nao por
  -- cooldown: utani hur libera em 2 s e dura 30 s. Recastar a cada cooldown
  -- so queimaria mana. buffAtivo usa o bit de estado quando existe -- assim
  -- tambem pega o caso do buff cair antes do tempo.
  local h = cfg.tools.haste
  if h.on and h.texto ~= "" and not buffAtivo(h.texto) and castar(h.texto) then
    return "buff " .. h.texto
  end
  if cfg.tools.antiParalyze and paralisado() then
    local hasteTexto = (cfg.tools.haste.texto ~= "" and cfg.tools.haste.texto) or "utani hur"
    if castar(hasteTexto) then return "anti-paralyze" end
  end

  -- 5) shooter, em ordem de preferencia
  local fila = {}
  if cfg.chaves.magia then
    for i, l in ipairs(cfg.caster.spell) do
      if l.on and l.texto ~= "" then
        table.insert(fila, { l = l, k = "cs" .. i, runa = false, ordem = #fila })
      end
    end
  end
  if cfg.chaves.runa then
    for i, l in ipairs(cfg.caster.rune) do
      if l.on and l.item > 0 then
        table.insert(fila, { l = l, k = "cr" .. i, runa = true, ordem = #fila })
      end
    end
  end
  -- table.sort do Lua NAO e' estavel: com prioridades iguais a ordem saia
  -- arbitraria e mudava entre ciclos. O indice original desempata.
  table.sort(fila, function(a, b)
    local pa, pb = a.l.prio or 9, b.l.prio or 9
    if pa ~= pb then return pa < pb end
    return a.ordem < b.ordem
  end)

  -- Percorre a fila inteira: a primeira que estiver REALMENTE pronta dispara.
  -- E' isso que faz a preferencia cair para a proxima quando a de cima esta em
  -- cooldown, em vez de gastar o ciclo numa magia que o servidor vai recusar.
  for _, e in ipairs(fila) do
    local l = e.l
    if #mobs >= (l.mobs or 1) and mp >= (l.mana or 0) then
      if e.runa then
        if alvo and podeAgir(e.k, 2000) then
          usarItem(l.item, alvo); return "runa " .. l.item .. " -> " .. alvo:getName()
        end
      elseif castar(l.texto) then
        return l.texto
      end
    end
  end

  return nil
end


-- escolhe o melhor alvo: respeita a lista de monstros (se houver alguma
-- linha ligada), depois prioridade e por fim distancia.
-- regras ativas (linha ligada e com nome preenchido)
local function regrasAlvo()
  local regras = {}
  for _, r in ipairs((cfg.target or {}).lista or {}) do
    if r.on and r.nome and r.nome ~= "" then table.insert(regras, r) end
  end
  return regras
end

-- Nota do monstro: devolve prioridade e distancia, ou nil se ele nao serve
-- (fora da lista, ou longe demais para a regra que casou).
local function avaliarAlvo(m, pos, regras)
  if not m or m:isDead() then return nil end
  local mp = m:getPosition()
  if not mp then return nil end
  local d = math.max(math.abs(mp.x - pos.x), math.abs(mp.y - pos.y))

  if #regras == 0 then
    return (d <= 7) and 5 or nil, d   -- sem lista: qualquer monstro serve
  end

  local nome = m:getName():lower()
  local prio, alcance = nil, 7
  for _, r in ipairs(regras) do
    if nome:find(r.nome:lower(), 1, true) then
      if not prio or (r.prio or 5) < prio then
        prio, alcance = r.prio or 5, r.dist or 7
      end
    end
  end
  if prio and d <= alcance then return prio, d end
  return nil
end

local function escolherAlvo(mobs)
  local p = jogador()
  if not p then return nil end
  local pos, regras = p:getPosition(), regrasAlvo()

  local melhor, melhorPrio, melhorDist = nil, 99, 99
  for _, m in ipairs(mobs) do
    local prio, d = avaliarAlvo(m, pos, regras)
    if prio and (prio < melhorPrio or (prio == melhorPrio and d < melhorDist)) then
      melhor, melhorPrio, melhorDist = m, prio, d
    end
  end
  return melhor, melhorPrio, melhorDist
end

-- Mira com histerese.
--
-- Antes, as condicoes de seguranca chamavam cancelAttack() sempre que o valor
-- estava do lado errado do limite. Como o ciclo roda a cada 150 ms e tanto o hp
-- quanto a contagem de mobs oscilam em combate, qualquer valor perto do limite
-- virava cancela-ataca-cancela: o alvo pulava e a barra de ataque piscava.
--
-- Agora o limite de PARAR e o de VOLTAR sao diferentes (banda morta), e o alvo
-- escolhido tem um tempo minimo de permanencia antes de poder ser trocado --
-- e mesmo depois, so troca por um de prioridade melhor.
local MARGEM_HP   = 5      -- pontos percentuais de banda morta
local MARGEM_MOBS = 1      -- mobs de banda morta
local PERMANENCIA = 1200   -- ms que o alvo atual e' mantido

local pausaHp, pausaMobs = false, false
local alvoDesde = 0

local function cuidarDoAlvo(mobs, hp)
  local t = cfg.target
  if not t or not t.atacarAuto then return end

  -- para em hpMinimo, so volta em hpMinimo + MARGEM_HP
  if t.pararSeFraco then
    local lim = t.hpMinimo or 0
    if hp < lim then pausaHp = true
    elseif hp >= lim + MARGEM_HP then pausaHp = false end
  else
    pausaHp = false
  end

  -- para acima de maxMobs, so volta em maxMobs - MARGEM_MOBS
  if t.limitarMobs then
    local lim = t.maxMobs or 99
    if #mobs > lim then pausaMobs = true
    elseif #mobs <= lim - MARGEM_MOBS then pausaMobs = false end
  else
    pausaMobs = false
  end

  if pausaHp or pausaMobs then
    if g_game.getAttackingCreature() then g_game.cancelAttack() end
    alvoDesde = 0
    return
  end

  local atual = g_game.getAttackingCreature()
  if atual and (atual:isDead() or not atual:getPosition()) then atual = nil end

  if atual then
    if agora() - alvoDesde < PERMANENCIA then return end

    -- passou o tempo minimo: so vale trocar por prioridade estritamente melhor
    local p = jogador()
    if not p then return end
    local pos, regras = p:getPosition(), regrasAlvo()
    local prioAtual = avaliarAlvo(atual, pos, regras)
    local novo, prioNovo = escolherAlvo(mobs)

    if novo and novo ~= atual and prioNovo and (not prioAtual or prioNovo < prioAtual) then
      g_game.attack(novo)
      alvoDesde = agora()
    elseif not prioAtual then
      -- o alvo atual saiu do alcance ou da lista
      if novo then g_game.attack(novo); alvoDesde = agora()
      else g_game.cancelAttack(); alvoDesde = 0 end
    end
    return
  end

  local novo = escolherAlvo(mobs)
  if novo then
    g_game.attack(novo)
    alvoDesde = agora()
    if t.perseguir and g_game.getChaseMode() ~= ChaseOpponent then
      g_game.setChaseMode(ChaseOpponent)
    end
  end
end

-- ------------------------------------------------- teclas de atalho
-- O jogador escolhe a combinacao; nada fica fixo no codigo. Guardamos o que
-- foi ligado para conseguir desligar depois -- se rebindar sem soltar o
-- anterior, a tecla velha continua respondendo alem da nova.

local teclasAtivas = {}
local atualizarChavesNaTela   -- definido junto com a interface

local function aviso(texto)
  local tm = modules.game_textmessage
  if tm and tm.displayStatusMessage then tm.displayStatusMessage(texto) end
end

local function estado(v) return v and "ligado" or "desligado" end

-- cada acao devolve o texto que aparece na tela
local ACOES = {
  geral = function()
    cfg.ligado = not cfg.ligado
    return "AutoCaster " .. estado(cfg.ligado)
  end,
  cura = function()
    cfg.chaves.cura = not cfg.chaves.cura
    return "Cura " .. estado(cfg.chaves.cura)
  end,
  magia = function()
    cfg.chaves.magia = not cfg.chaves.magia
    return "Magia " .. estado(cfg.chaves.magia)
  end,
  runa = function()
    cfg.chaves.runa = not cfg.chaves.runa
    return "Runa " .. estado(cfg.chaves.runa)
  end,
  -- as duas juntas, como no RTCaster. Se estiverem divergentes, o primeiro
  -- toque LIGA as duas -- e' o que se espera de um atalho unico.
  magiaRuna = function()
    local novo = not (cfg.chaves.magia and cfg.chaves.runa)
    cfg.chaves.magia, cfg.chaves.runa = novo, novo
    return "Magia + runa " .. estado(novo)
  end,
}

local function soltarTeclas()
  for desc, _ in pairs(teclasAtivas) do
    g_keyboard.unbindKeyDown(desc)
  end
  teclasAtivas = {}
end

local function prenderTeclas()
  soltarTeclas()
  for acao, desc in pairs(cfg.teclas or {}) do
    local fn = ACOES[acao]
    -- a mesma combinacao em duas acoes ligaria as duas de uma vez; a primeira
    -- registrada fica, a segunda e' ignorada
    if fn and desc ~= "" and not teclasAtivas[desc] then
      teclasAtivas[desc] = true
      g_keyboard.bindKeyDown(desc, function()
        aviso(fn())
        if atualizarChavesNaTela then atualizarChavesNaTela() end
        salvar()
      end)
    end
  end
end

local function ciclo()
  if not cfg.ligado or not g_game.isOnline() then return end

  local mobsAgora = monstrosPerto(7)
  local hpAgora = pctVida(jogador())

  -- aba Target: escolhe o alvo pela lista/prioridade
  cuidarDoAlvo(mobsAgora, hpAgora)

  -- Auto Target simples da aba Caster: so entra em acao quando a aba Target
  -- esta desligada. Os dois juntos disputariam a mira a cada 150 ms, que e'
  -- exatamente o efeito de ter dois bots ligados ao mesmo tempo.
  if cfg.caster.autoTarget and not (cfg.target and cfg.target.atacarAuto)
     and not g_game.getAttackingCreature() then
    local m = maisProximo(mobsAgora)
    if m then g_game.attack(m) end
  end

  local feito = passo()
  if feito and ui.status then
    ui.status:setText(feito .. "   [hp " .. pctVida(jogador()) .. "% mp " .. pctMana() .. "%]")
  end
end


-- ============ seletor visual de magias ============
-- Usa a base do proprio client (SpellInfo) e o sprite sheet de icones,
-- os mesmos que aparecem na hotkey.

local PERFIL = "Default"

-- O SpellInfo que vem no OTClient e' uma tabela fixa e antiga: nao tem as
-- vocacoes novas (Monk) nem as magias adicionadas depois. Por isso a lista
-- de verdade vem do proprio servidor, gerada por gerar_spells.py em
-- spells_servidor.lua. O SpellInfo continua servindo so para os ICONES.

-- clientid da vocacao (data/XML/vocations.xml do Canary) -> nome
local VOC_NOME = {
  [0] = "none",
  [1] = "knight",   [2] = "paladin",      [3] = "sorcerer",
  [4] = "druid",    [5] = "monk",
  [11] = "elite knight", [12] = "royal paladin",
  [13] = "master sorcerer", [14] = "elder druid", [15] = "exalted monk",
}

-- promovida -> base (uma promovida tambem usa o que a base usa)
local VOC_BASE = {
  ["elite knight"] = "knight",     ["royal paladin"] = "paladin",
  ["master sorcerer"] = "sorcerer", ["elder druid"] = "druid",
  ["exalted monk"] = "monk",
}

local function nomeDaVocacao()
  local p = jogador()
  local id = p and p.getVocation and p:getVocation() or nil
  if not id then return nil end
  return VOC_NOME[id]
end

local function serveParaVocacao(vocs, minha)
  if not vocs or #vocs == 0 then return true end
  if not minha or minha == "none" then return true end   -- GM ve tudo
  local base = VOC_BASE[minha]
  for _, v in ipairs(vocs) do
    if v == minha or (base and v == base) then return true end
  end
  return false
end

-- grupo 1 = ataque, 2 = cura, 3 = suporte
-- filtra pela vocacao e pelo level do personagem
local function magiasPorGrupo(grupo)
  local lista = {}
  local p = jogador()
  local minha = nomeDaVocacao()
  local lvl = p and p.getLevel and p:getLevel() or 9999

  if SpellsServidor then
    for _, m in ipairs(SpellsServidor) do
      if m.grupo == grupo and serveParaVocacao(m.vocacoes, minha)
         and (m.level or 0) <= lvl then
        table.insert(lista, { nome = m.nome, info = { words = m.palavras,
                              mana = m.mana, level = m.level } })
      end
    end
  else
    -- sem a lista do servidor, cai na tabela do client
    local base = SpellInfo and SpellInfo[PERFIL]
    if base then
      for nome, info in pairs(base) do
        if info.group and info.group[grupo] and info.words then
          table.insert(lista, { nome = nome, info = info })
        end
      end
    end
  end

  table.sort(lista, function(a, b)
    if (a.info.level or 0) ~= (b.info.level or 0) then
      return (a.info.level or 0) < (b.info.level or 0)
    end
    return a.nome < b.nome
  end)
  return lista
end

-- O icone vem do SpellInfo do client, casado pelas palavras da magia.
-- Os dois clients guardam o indice de um jeito diferente:
--   otclient (mehah, 15.x): info.clientId aponta direto para o sheet
--   OTClientV8 (10.x):      info.icon e' um nome, resolvido em SpellIcons
-- Tentamos os dois, entao o mesmo modulo serve para ambos.
local function indiceDoIcone(info)
  local id = tonumber(info.clientId)
  if id then return id end
  id = tonumber(info.icon)
  if id then return id end
  if SpellIcons and info.icon and SpellIcons[info.icon] then
    return SpellIcons[info.icon][1]
  end
  return nil
end

local function iconePorPalavras(palavras)
  local base = SpellInfo and SpellInfo[PERFIL]
  if not base or not palavras or palavras == "" then return nil end
  for _, info in pairs(base) do
    if info.words == palavras then return indiceDoIcone(info) end
  end
  return nil
end

local function idDoIcone(info)
  return iconePorPalavras(info.words)
end

-- desenha o icone da magia num widget (mesma arte da hotkey)
local function pintarIcone(w, palavras)
  if not w then return end
  local id = iconePorPalavras(palavras)
  if id and Spells and Spells.getImageClip and SpelllistSettings then
    w:setImageSource(SpelllistSettings[PERFIL].iconFile)
    w:setImageClip(Spells.getImageClip(id, PERFIL))
  else
    w:setImageSource("")   -- magia nova, sem icone na tabela do client
  end
end

local janelaSeletor = nil

-- abre a lista de magias do grupo pedido; chama aoEscolher(palavras)
local function abrirSeletor(grupo, aoEscolher)
  if janelaSeletor then janelaSeletor:destroy() janelaSeletor = nil end
  janelaSeletor = g_ui.createWidget("SeletorMagia", rootWidget)
  local titulos = { [1] = tr("Magias de ataque"), [2] = tr("Magias de cura"), [3] = tr("Magias de suporte") }
  local nomeVoc = nomeDaVocacao() or tr("sem vocacao")
  janelaSeletor:setText((titulos[grupo] or tr("Magias")) .. "  -  " .. nomeVoc)

  local lista = janelaSeletor:getChildById("lista")
  local todas = magiasPorGrupo(grupo)

  local function montar(filtro)
    lista:destroyChildren()
    for _, m in ipairs(todas) do
      local rotulo = m.nome .. "  (" .. m.info.words .. ")"
      if filtro == "" or rotulo:lower():find(filtro:lower(), 1, true) then
        local w = g_ui.createWidget("LinhaMagia", lista)
        w:setText(rotulo .. "\n     mana " .. (m.info.mana or 0) .. "   lvl " .. (m.info.level or 0))
        local id = idDoIcone(m.info)
        if id and Spells and Spells.getImageClip then
          w:setImageSource(SpelllistSettings[PERFIL].iconFile)
          w:setImageClip(Spells.getImageClip(id, PERFIL))
          w:setImageSize(tosize("32 32"))
          w:setImageRect(torect("4 2 32 32"))
        end
        w.onDoubleClick = function()
          aoEscolher(m.info.words)
          janelaSeletor:destroy(); janelaSeletor = nil
        end
        w.onClick = w.onDoubleClick
      end
    end
  end

  montar("")
  janelaSeletor:getChildById("filtro").onTextChange = function(_, t) montar(t) end
  janelaSeletor:getChildById("btCancelar").onClick = function()
    janelaSeletor:destroy(); janelaSeletor = nil
  end
end

-- ============ seletor de item (potion / runa) ============
--
-- O slot de item usava o seletor generico do client: pedia o **id numerico** e
-- aceitava qualquer coisa. Dava para arrastar uma espada para o slot de potion,
-- e o motor tentava beber a espada em silencio.
--
-- Aqui a lista e' fechada e vem do datapack (gerar_itens.py). Cada tipo de slot
-- so mostra o que faz sentido nele: a linha de hp so ve potion de vida, a de mp
-- so de mana, o rune shooter so runas.

-- tipo: "hp", "mp" ou "runa"
local function itensPermitidos(tipo)
  local fonte = ItensServidor or {}
  local lista = {}

  if tipo == "runa" then
    for _, r in ipairs(fonte.runas or {}) do
      table.insert(lista, { id = r.id, nome = r.nome, extra = r.magia or "" })
    end
    return lista
  end

  for _, p in ipairs(fonte.potions or {}) do
    -- "ambos" (spirit potion) serve nos dois slots; "outro" nao cura, fica fora
    if p.tipo == tipo or p.tipo == "ambos" then
      local extra = (p.level or 0) > 0 and ("level " .. p.level) or ""
      table.insert(lista, { id = p.id, nome = p.nome, extra = extra })
    end
  end
  return lista
end

local function itemPermitido(id, tipo)
  if not id or id <= 0 then return true end   -- slot vazio e' valido
  for _, it in ipairs(itensPermitidos(tipo)) do
    if it.id == id then return true end
  end
  return false
end

local janelaItem = nil

local function abrirSeletorItem(tipo, aoEscolher)
  if janelaItem then janelaItem:destroy() janelaItem = nil end
  janelaItem = g_ui.createWidget("SeletorItem", rootWidget)

  janelaItem:setText((tipo == "runa" and tr("Escolher runa"))
    or (tipo == "mp" and tr("Escolher potion de mana"))
    or tr("Escolher potion de vida"))

  local lista = janelaItem:getChildById("lista")
  local todos = itensPermitidos(tipo)

  local function montar(filtro)
    lista:destroyChildren()
    for _, it in ipairs(todos) do
      if filtro == "" or it.nome:lower():find(filtro:lower(), 1, true) then
        local w = g_ui.createWidget("LinhaItem", lista)
        w:getChildById("sprite"):setItemId(it.id)
        local rotulo = it.nome
        if it.extra ~= "" then rotulo = rotulo .. "\n     " .. it.extra end
        w:setText(rotulo)
        w.onClick = function()
          aoEscolher(it.id)
          janelaItem:destroy(); janelaItem = nil
        end
      end
    end
  end

  montar("")
  janelaItem:getChildById("filtro").onTextChange = function(_, t) montar(t) end
  janelaItem:getChildById("btCancelar").onClick = function()
    janelaItem:destroy(); janelaItem = nil
  end
end

-- ------------------------------------------------------------- UI

salvar = function()
  raiz.presets[raiz.atual] = cfg
  g_settings.setNode("autocaster", raiz)
  g_settings.save()
end

local function nomesPresets()
  local lista = {}
  for nome, _ in pairs(raiz.presets) do table.insert(lista, nome) end
  table.sort(lista)
  return lista
end

-- liga uma LinhaCura da interface a uma tabela de config
-- Prende o slot a uma lista fechada de itens.
--   tipo: "hp", "mp" ou "runa"
-- editable = false desliga o dialogo de "Item ID" do mod game_itemselector
-- (UIItem:onClick so o abre quando selectable E editable). O arrastar continua
-- valendo, porque canAcceptDrop olha selectable, nao editable -- mas agora o
-- que for arrastado e' conferido contra a lista.
local function ligarSlotItem(slot, dado, tipo)
  if not slot then return end
  slot.editable = false
  slot:setItemId(dado.item or 0)

  slot.onClick = function()
    abrirSeletorItem(tipo, function(id)
      dado.item = id
      slot:setItemId(id)
      salvar()
    end)
  end

  slot.onItemChange = function(widget)
    local id = widget:getItemId()
    if not itemPermitido(id, tipo) then
      widget:setItemId(dado.item or 0)   -- devolve o que era: item errado
      return
    end
    dado.item = id
    salvar()
  end
end

local function ligarLinhaCura(w, dado, usaSlot, grupoMagia, tipoItem)
  if not w or not dado then return end
  -- icone da magia: clique abre o seletor visual
  if w.magia then
    pintarIcone(w.magia, dado.texto)
    if grupoMagia then
      w.slot:setVisible(false)
      w.magia.onClick = function()
        abrirSeletor(grupoMagia, function(palavras)
          dado.texto = palavras
          w.texto:setText(palavras)
          pintarIcone(w.magia, palavras)
          salvar()
        end)
      end
    else
      w.magia:setVisible(false)
    end
  end

  w.on:setChecked(dado.on)
  w.on.onCheckChange = function(_, v) dado.on = v salvar() end

  w.texto:setText(dado.texto or "")
  w.texto.onTextChange = function(_, t) dado.texto = t pintarIcone(w.magia, t) salvar() end

  w.pct:setValue(dado.pct or 50)
  w.pct.onValueChange = function(_, v) dado.pct = v salvar() end

  if usaSlot ~= false then
    if tipoItem then
      ligarSlotItem(w.slot, dado, tipoItem)
    else
      w.slot:setItemId(dado.item or 0)
      w.slot.onItemChange = function(widget) dado.item = widget:getItemId() salvar() end
    end
  end
end

local function ligarLinhaAlvo(w, dado)
  if not w or not dado then return end
  w.on:setChecked(dado.on)
  w.on.onCheckChange = function(_, v) dado.on = v salvar() end

  w.nome:setText(dado.nome or "")
  w.nome.onTextChange = function(_, t) dado.nome = t salvar() end

  for i, nome in ipairs(PRIORIDADES) do w.prio:addOption(nome, i) end
  w.prio:setCurrentOptionByData(dado.prio or 1)
  w.prio.onOptionChange = function(_, _, data) dado.prio = data salvar() end

  w.dist:setValue(dado.dist or 7)
  w.dist.onValueChange = function(_, v) dado.dist = v salvar() end
end

local function ligarLinhaShooter(w, dado, grupoMagia, tipoItem)
  if not w or not dado then return end
  if w.magia then
    pintarIcone(w.magia, dado.texto)
    if grupoMagia then
      w.slot:setVisible(false)
      w.magia.onClick = function()
        abrirSeletor(grupoMagia, function(palavras)
          dado.texto = palavras
          w.texto:setText(palavras)
          pintarIcone(w.magia, palavras)
          salvar()
        end)
      end
    else
      w.magia:setVisible(false)
    end
  end

  w.on:setChecked(dado.on)
  w.on.onCheckChange = function(_, v) dado.on = v salvar() end

  w.texto:setText(dado.texto or "")
  w.texto.onTextChange = function(_, t) dado.texto = t pintarIcone(w.magia, t) salvar() end

  if tipoItem then
    ligarSlotItem(w.slot, dado, tipoItem)
  else
    w.slot:setItemId(dado.item or 0)
    w.slot.onItemChange = function(widget) dado.item = widget:getItemId() salvar() end
  end

  w.mana:setValue(dado.mana or 0)
  w.mana.onValueChange = function(_, v) dado.mana = v salvar() end

  w.mobs:setValue(dado.mobs or 1)
  w.mobs.onValueChange = function(_, v) dado.mobs = v salvar() end

  for i, nome in ipairs(PRIORIDADES) do w.prio:addOption(nome, i) end
  w.prio:setCurrentOptionByData(dado.prio or 1)
  w.prio.onOptionChange = function(_, _, data) dado.prio = data salvar() end
end

local function vincular()
  -- Healing
  ligarLinhaCura(painel.healing:recursiveGetChildById("spell1"), cfg.healing.spell[1], true, 2)
  ligarLinhaCura(painel.healing:recursiveGetChildById("spell2"), cfg.healing.spell[2], true, 2)
  ligarLinhaCura(painel.healing:recursiveGetChildById("spell3"), cfg.healing.spell[3], true, 2)
  -- a primeira linha de potion usa hp%, a segunda mp% (ver passo())
  ligarLinhaCura(painel.healing:recursiveGetChildById("pot1"),   cfg.healing.potion[1], nil, nil, "hp")
  ligarLinhaCura(painel.healing:recursiveGetChildById("pot2"),   cfg.healing.potion[2], nil, nil, "mp")
  ligarLinhaCura(painel.healing:recursiveGetChildById("amigo1"), cfg.healing.amigo[1], true, 2)
  ligarLinhaCura(painel.healing:recursiveGetChildById("amigo2"), cfg.healing.amigo[2], nil, nil, "runa")

  -- Tools
  ligarLinhaCura(painel.tools:recursiveGetChildById("haste"), cfg.tools.haste, true, 3)
  local cg = painel.tools:recursiveGetChildById("changeGold")
  cg:setChecked(cfg.tools.changeGold)
  cg.onCheckChange = function(_, v) cfg.tools.changeGold = v salvar() end
  local ef = painel.tools:recursiveGetChildById("eatFood")
  ef:setChecked(cfg.tools.eatFood)
  ef.onCheckChange = function(_, v) cfg.tools.eatFood = v salvar() end
  local ap = painel.tools:recursiveGetChildById("antiParalyze")
  ap:setChecked(cfg.tools.antiParalyze)
  ap.onCheckChange = function(_, v) cfg.tools.antiParalyze = v salvar() end

  -- Teclas de atalho
  local LINHAS_TECLA = {
    { id = "tGeral",     acao = "geral",     rotulo = tr("Liga/desliga") },
    { id = "tCura",      acao = "cura",      rotulo = tr("Cura") },
    { id = "tMagia",     acao = "magia",     rotulo = tr("Magia") },
    { id = "tRuna",      acao = "runa",      rotulo = tr("Runa") },
    { id = "tMagiaRuna", acao = "magiaRuna", rotulo = tr("Magia + runa") },
  }

  for _, def in ipairs(LINHAS_TECLA) do
    local linha = painel.tools:recursiveGetChildById(def.id)
    if linha then
      local bt = linha:getChildById("bt")
      linha:getChildById("rotulo"):setText(def.rotulo)

      local function mostrar()
        local d = cfg.teclas[def.acao] or ""
        bt:setText(d ~= "" and d or tr("sem atalho"))
      end
      mostrar()

      -- Captura: o proximo toque vira a combinacao. Esc limpa e sai. Enquanto
      -- captura, o botao segura o foco do teclado -- por isso onKeyDown devolve
      -- true, para o toque nao vazar para o jogo (e sair andando, por exemplo).
      bt.onClick = function()
        bt:setText(tr("aperte a tecla..."))
        bt:focus()
        bt.onKeyDown = function(_, keyCode, mods)
          local desc = determineKeyComboDesc(keyCode, mods)
          bt.onKeyDown = nil
          if desc == "Escape" then
            cfg.teclas[def.acao] = ""
          else
            -- a mesma tecla em duas acoes so' dispararia a primeira; solta a outra
            for outra, d in pairs(cfg.teclas) do
              if outra ~= def.acao and d == desc then cfg.teclas[outra] = "" end
            end
            cfg.teclas[def.acao] = desc
          end
          salvar()
          prenderTeclas()
          for _, d2 in ipairs(LINHAS_TECLA) do
            local l2 = painel.tools:recursiveGetChildById(d2.id)
            if l2 then
              local b2, dd = l2:getChildById("bt"), cfg.teclas[d2.acao] or ""
              b2:setText(dd ~= "" and dd or tr("sem atalho"))
            end
          end
          return true
        end
      end

      linha:getChildById("limpar").onClick = function()
        cfg.teclas[def.acao] = ""
        bt.onKeyDown = nil
        mostrar()
        salvar()
        prenderTeclas()
      end
    end
  end

  -- Caster
  ligarLinhaShooter(painel.caster:recursiveGetChildById("sh1"), cfg.caster.spell[1], 1)
  ligarLinhaShooter(painel.caster:recursiveGetChildById("sh2"), cfg.caster.spell[2], 1)
  ligarLinhaShooter(painel.caster:recursiveGetChildById("sh3"), cfg.caster.spell[3], 1)
  ligarLinhaShooter(painel.caster:recursiveGetChildById("rn1"), cfg.caster.rune[1], nil, "runa")
  ligarLinhaShooter(painel.caster:recursiveGetChildById("rn2"), cfg.caster.rune[2], nil, "runa")
  local at = painel.caster:recursiveGetChildById("autoTarget")
  at:setChecked(cfg.caster.autoTarget)
  at.onCheckChange = function(_, v) cfg.caster.autoTarget = v salvar() end

  -- Target
  local pt, t = painel.target, cfg.target
  for i = 1, 4 do
    ligarLinhaAlvo(pt:recursiveGetChildById("alvo" .. i), t.lista[i])
  end

  local function marcar(id, campo)
    local w = pt:recursiveGetChildById(id)
    w:setChecked(t[campo])
    w.onCheckChange = function(_, v) t[campo] = v salvar() end
  end
  marcar("atacarAuto", "atacarAuto")
  marcar("perseguir", "perseguir")
  marcar("pararSeFraco", "pararSeFraco")
  marcar("limitarMobs", "limitarMobs")

  local function girar(id, campo, padrao)
    local w = pt:recursiveGetChildById(id)
    w:setValue(t[campo] or padrao)
    w.onValueChange = function(_, v) t[campo] = v salvar() end
  end
  girar("hpMinimo", "hpMinimo", 30)
  girar("maxMobs", "maxMobs", 5)

  -- preenche a primeira linha livre com o monstro que estou atacando
  pt:recursiveGetChildById("btDoAlvo").onClick = function()
    local alvo = g_game.getAttackingCreature()
    if not alvo then return end
    for i = 1, 4 do
      if not t.lista[i].nome or t.lista[i].nome == "" then
        t.lista[i].nome = alvo:getName()
        t.lista[i].on = true
        salvar()
        vincular()
        return
      end
    end
  end
end

function init()
  raiz = g_settings.getNode("autocaster")
  if not raiz or not raiz.presets or not raiz.presets[raiz.atual or ""] then
    raiz = { atual = "Default", presets = { Default = padroes() } }
  end
  cfg = raiz.presets[raiz.atual]
  if not configValida(cfg) then
    cfg = padroes(); raiz.presets[raiz.atual] = cfg
  end
  -- presets salvos por versoes anteriores nao tinham chaves/teclas
  migrarConfig(cfg)

  autocasterWindow = g_ui.displayUI("autocaster")
  autocasterWindow:hide()

  local barra = autocasterWindow:getChildById("abas")
  barra:setContentWidget(autocasterWindow:getChildById("conteudoAbas"))

  painel.healing = g_ui.createWidget("PainelHealing")
  painel.tools   = g_ui.createWidget("PainelTools")
  painel.caster  = g_ui.createWidget("PainelCaster")
  painel.target  = g_ui.createWidget("PainelTarget")

  -- Sem icone de proposito: o UITabBar mede a aba pela largura do texto e so
  -- depois aplica o icone por mergeStyle, sem recalcular -- texto e icone
  -- disputavam o mesmo espaco e a aba saia visualmente quebrada.
  barra:addTab(tr("Healing"), painel.healing)
  barra:addTab(tr("Tools"),   painel.tools)
  barra:addTab(tr("Caster"),  painel.caster)
  barra:addTab(tr("Target"),  painel.target)

  vincular()

  -- rodape
  ui.status = autocasterWindow:recursiveGetChildById("status")
  ui.statusTexto = autocasterWindow:recursiveGetChildById("statusTexto")
  local lig = autocasterWindow:recursiveGetChildById("ligado")
  lig:setChecked(cfg.ligado)
  local function pintar(v)
    ui.statusTexto:setText(v and "Enabled" or "Disabled")
    ui.statusTexto:setColor(v and "#66ff66" or "#ff6666")
  end
  pintar(cfg.ligado)
  lig.onCheckChange = function(_, v) cfg.ligado = v pintar(v) salvar() end

  -- a tecla de atalho mexe no cfg direto; a janela precisa acompanhar quando
  -- estiver aberta, senao o checkbox mostra o contrario do que esta valendo
  atualizarChavesNaTela = function()
    if not autocasterWindow then return end
    lig:setChecked(cfg.ligado)
    pintar(cfg.ligado)
  end

  -- ---- presets ----
  ui.combo = autocasterWindow:recursiveGetChildById("comboPreset")
  local function recarregarCombo()
    ui.combo:clearOptions()
    for _, nome in ipairs(nomesPresets()) do ui.combo:addOption(nome) end
    ui.combo:setCurrentOption(raiz.atual, true)
  end
  recarregarCombo()
  ui.combo.onOptionChange = function(_, nome)
    if nome == raiz.atual then return end
    raiz.presets[raiz.atual] = cfg      -- guarda o que estava editando
    raiz.atual = nome
    cfg = raiz.presets[nome]
    vincular()                          -- reaponta todos os widgets
    lig:setChecked(cfg.ligado); pintar(cfg.ligado)
    g_settings.setNode("autocaster", raiz); g_settings.save()
  end

  autocasterWindow:recursiveGetChildById("btNovo").onClick = function()
    local n, base = 1, "Preset"
    while raiz.presets[base .. n] do n = n + 1 end
    local nome = base .. n
    raiz.presets[nome] = padroes()
    raiz.presets[raiz.atual] = cfg
    raiz.atual = nome
    cfg = raiz.presets[nome]
    vincular()
    lig:setChecked(cfg.ligado); pintar(cfg.ligado)
    recarregarCombo()
    g_settings.setNode("autocaster", raiz); g_settings.save()
  end

  autocasterWindow:recursiveGetChildById("btRemover").onClick = function()
    if #nomesPresets() <= 1 then return end   -- nunca deixa sem nenhum
    raiz.presets[raiz.atual] = nil
    raiz.atual = nomesPresets()[1]
    cfg = raiz.presets[raiz.atual]
    vincular()
    lig:setChecked(cfg.ligado); pintar(cfg.ligado)
    recarregarCombo()
    g_settings.setNode("autocaster", raiz); g_settings.save()
  end

  autocasterWindow:recursiveGetChildById("btFechar").onClick = toggle

  if modules.client_topmenu then
    -- Sprite de BOTAO (fundo 3D + icone, com os dois estados lado a lado),
    -- nao so o icone: o mainpanel usa setImageSource, entao um icone solto
    -- fica "chapado" sem o relevo dos botoes nativos. O PNG vai junto no modulo.
    botao = modules.client_topmenu.addRightGameToggleButton(
      "autocasterButton", tr("AutoCaster") .. " (Ctrl+Shift+A)",
      "/autocaster/botao", toggle, false, 8)
  end

  g_keyboard.bindKeyDown("Ctrl+Shift+A", toggle)
  prenderTeclas()

  -- Cooldown de verdade: o servidor avisa por estes dois eventos (pacotes
  -- 0xA4 e 0xA5). E' o que permite saber que exori max vis tem 30 s, e o que
  -- faz o Momentum -- que corta 2 s de todos os cooldowns -- ser respeitado
  -- automaticamente, porque ele reenvia os cooldowns novos.
  conexoes = {
    onSpellCooldown = function(id, ms)
      fimCdMagia[id] = agora() + (ms or 0)
    end,
    onSpellGroupCooldown = function(grupo, ms)
      fimCdGrupo[grupo] = agora() + (ms or 0)
    end,
    onGameEnd = function() limparCooldowns() end,
  }
  connect(g_game, conexoes)

  loopEvent = cycleEvent(ciclo, TICK)
end

function terminate()
  if loopEvent then loopEvent:cancel() loopEvent = nil end
  if conexoes then disconnect(g_game, conexoes) conexoes = nil end
  g_keyboard.unbindKeyDown("Ctrl+Shift+A")
  soltarTeclas()
  if botao then botao:destroy() botao = nil end
  if autocasterWindow then autocasterWindow:destroy() autocasterWindow = nil end
end

function toggle()
  if not autocasterWindow then return end
  if autocasterWindow:isVisible() then
    autocasterWindow:hide()
  else
    autocasterWindow:show()
    autocasterWindow:raise()
    autocasterWindow:focus()
  end
end
