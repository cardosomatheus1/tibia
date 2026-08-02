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

local function temHaste()
  local p = jogador()
  if not p or not p.getStates then return false end
  local ok, st = pcall(function() return p:getStates() end)
  if not ok or not st then return false end
  return bit.band(st, PlayerStates.Haste) > 0
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

-- devolve texto do que foi feito, ou nil
local function passo()
  local p = jogador()
  if not p or p:isDead() then return nil end

  local hp, mp = pctVida(p), pctMana()
  local mobs = monstrosPerto(7)
  local alvo = g_game.getAttackingCreature() or maisProximo(mobs)

  -- 1) cura em spell (prioridade maxima)
  for i, l in ipairs(cfg.healing.spell) do
    if l.on and l.texto ~= "" and hp < l.pct and podeAgir("hs" .. i) then
      falar(l.texto); return l.texto .. " (hp " .. hp .. "%)"
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
      if amigo and podeAgir("am" .. i) then
        if l.texto ~= "" then
          falar(l.texto .. ' "' .. amigo:getName())
          return l.texto .. " -> " .. amigo:getName()
        elseif l.item > 0 then
          usarItem(l.item, amigo)
          return "runa " .. l.item .. " -> " .. amigo:getName()
        end
      end
    end
  end

  -- 4) tools
  local h = cfg.tools.haste
  if h.on and h.texto ~= "" and not temHaste() and podeAgir("haste", 2000) then
    falar(h.texto); return "haste"
  end
  if cfg.tools.antiParalyze and paralisado() and podeAgir("para", 800) then
    falar(cfg.tools.haste.texto ~= "" and cfg.tools.haste.texto or "utani hur")
    return "anti-paralyze"
  end

  -- 5) shooter: ordena por prioridade
  local fila = {}
  for i, l in ipairs(cfg.caster.spell) do
    if l.on and l.texto ~= "" then table.insert(fila, { l = l, k = "cs" .. i, runa = false }) end
  end
  for i, l in ipairs(cfg.caster.rune) do
    if l.on and l.item > 0 then table.insert(fila, { l = l, k = "cr" .. i, runa = true }) end
  end
  table.sort(fila, function(a, b) return (a.l.prio or 9) < (b.l.prio or 9) end)

  for _, e in ipairs(fila) do
    local l = e.l
    if #mobs >= (l.mobs or 1) and mp >= (l.mana or 0) then
      if e.runa then
        if alvo and podeAgir(e.k, 2000) then
          usarItem(l.item, alvo); return "runa " .. l.item .. " -> " .. alvo:getName()
        end
      else
        if podeAgir(e.k, 2000) then falar(l.texto); return l.texto end
      end
    end
  end

  return nil
end


-- escolhe o melhor alvo: respeita a lista de monstros (se houver alguma
-- linha ligada), depois prioridade e por fim distancia.
local function escolherAlvo(mobs)
  local p = jogador()
  if not p then return nil end
  local pos = p:getPosition()
  local t = cfg.target

  -- monta as regras ativas com nome preenchido
  local regras = {}
  for _, r in ipairs(t.lista or {}) do
    if r.on and r.nome and r.nome ~= "" then table.insert(regras, r) end
  end

  local melhor, melhorPrio, melhorDist = nil, 99, 99
  for _, m in ipairs(mobs) do
    local mp = m:getPosition()
    local d = math.max(math.abs(mp.x - pos.x), math.abs(mp.y - pos.y))
    local prio, alcance = nil, 7

    if #regras == 0 then
      prio, alcance = 5, 7          -- sem lista: qualquer monstro serve
    else
      local nome = m:getName():lower()
      for _, r in ipairs(regras) do
        if nome:find(r.nome:lower(), 1, true) then
          if not prio or (r.prio or 5) < prio then
            prio, alcance = r.prio or 5, r.dist or 7
          end
        end
      end
    end

    if prio and d <= alcance then
      if prio < melhorPrio or (prio == melhorPrio and d < melhorDist) then
        melhor, melhorPrio, melhorDist = m, prio, d
      end
    end
  end
  return melhor
end

-- cuida da mira: escolhe, ataca e liga/desliga o chase
local function cuidarDoAlvo(mobs, hp)
  local t = cfg.target
  if not t or not t.atacarAuto then return end

  -- condicoes de seguranca
  if t.pararSeFraco and hp < (t.hpMinimo or 0) then
    if g_game.getAttackingCreature() then g_game.cancelAttack() end
    return
  end
  if t.limitarMobs and #mobs > (t.maxMobs or 99) then
    if g_game.getAttackingCreature() then g_game.cancelAttack() end
    return
  end

  local atual = g_game.getAttackingCreature()
  -- se o alvo atual morreu ou sumiu, escolhe outro
  if atual and (atual:isDead() or not atual:getPosition()) then atual = nil end

  if not atual then
    local novo = escolherAlvo(mobs)
    if novo then
      g_game.attack(novo)
      if t.perseguir and g_game.getChaseMode() ~= ChaseOpponent then
        g_game.setChaseMode(ChaseOpponent)
      end
    end
  end
end

local function ciclo()
  if not cfg.ligado or not g_game.isOnline() then return end

  local mobsAgora = monstrosPerto(7)
  local hpAgora = pctVida(jogador())

  -- aba Target: escolhe o alvo pela lista/prioridade
  cuidarDoAlvo(mobsAgora, hpAgora)

  -- compatibilidade: o Auto Target simples da aba Caster
  if cfg.caster.autoTarget and not g_game.getAttackingCreature() then
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
local function ligarLinhaCura(w, dado, usaSlot, grupoMagia)
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
    w.slot:setItemId(dado.item or 0)
    w.slot.onItemChange = function(widget) dado.item = widget:getItemId() salvar() end
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

local function ligarLinhaShooter(w, dado, grupoMagia)
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

  w.slot:setItemId(dado.item or 0)
  w.slot.onItemChange = function(widget) dado.item = widget:getItemId() salvar() end

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
  ligarLinhaCura(painel.healing:recursiveGetChildById("pot1"),   cfg.healing.potion[1])
  ligarLinhaCura(painel.healing:recursiveGetChildById("pot2"),   cfg.healing.potion[2])
  ligarLinhaCura(painel.healing:recursiveGetChildById("amigo1"), cfg.healing.amigo[1], true, 2)
  ligarLinhaCura(painel.healing:recursiveGetChildById("amigo2"), cfg.healing.amigo[2])

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

  -- Caster
  ligarLinhaShooter(painel.caster:recursiveGetChildById("sh1"), cfg.caster.spell[1], 1)
  ligarLinhaShooter(painel.caster:recursiveGetChildById("sh2"), cfg.caster.spell[2], 1)
  ligarLinhaShooter(painel.caster:recursiveGetChildById("sh3"), cfg.caster.spell[3], 1)
  ligarLinhaShooter(painel.caster:recursiveGetChildById("rn1"), cfg.caster.rune[1])
  ligarLinhaShooter(painel.caster:recursiveGetChildById("rn2"), cfg.caster.rune[2])
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

  autocasterWindow = g_ui.displayUI("autocaster")
  autocasterWindow:hide()

  local barra = autocasterWindow:getChildById("abas")
  barra:setContentWidget(autocasterWindow:getChildById("conteudoAbas"))

  painel.healing = g_ui.createWidget("PainelHealing")
  painel.tools   = g_ui.createWidget("PainelTools")
  painel.caster  = g_ui.createWidget("PainelCaster")
  painel.target  = g_ui.createWidget("PainelTarget")

  barra:addTab(tr("Healing"), painel.healing, "/images/topbuttons/healthinfo")
  barra:addTab(tr("Tools"),   painel.tools,   "/images/topbuttons/options")
  barra:addTab(tr("Caster"),  painel.caster,  "/images/topbuttons/spelllist")
  barra:addTab(tr("Target"),  painel.target,  "/images/topbuttons/battle")

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
    botao = modules.client_topmenu.addRightGameToggleButton(
      "autocasterButton", tr("AutoCaster") .. " (Ctrl+Shift+A)",
      "/images/topbuttons/bot", toggle, false, 8)
  end

  g_keyboard.bindKeyDown("Ctrl+Shift+A", toggle)
  loopEvent = cycleEvent(ciclo, TICK)
end

function terminate()
  if loopEvent then loopEvent:cancel() loopEvent = nil end
  g_keyboard.unbindKeyDown("Ctrl+Shift+A")
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
