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

local function ciclo()
  if not cfg.ligado or not g_game.isOnline() then return end

  -- auto target: so escolhe alvo, nao anda atras dele
  if cfg.caster.autoTarget and not g_game.getAttackingCreature() then
    local m = maisProximo(monstrosPerto(7))
    if m then g_game.attack(m) end
  end

  local feito = passo()
  if feito and ui.status then
    ui.status:setText(feito .. "   [hp " .. pctVida(jogador()) .. "% mp " .. pctMana() .. "%]")
  end
end

-- ------------------------------------------------------------- UI

local function salvar()
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
local function ligarLinhaCura(w, dado, usaSlot)
  w.on:setChecked(dado.on)
  w.on.onCheckChange = function(_, v) dado.on = v salvar() end

  w.texto:setText(dado.texto or "")
  w.texto.onTextChange = function(_, t) dado.texto = t salvar() end

  w.pct:setValue(dado.pct or 50)
  w.pct.onValueChange = function(_, v) dado.pct = v salvar() end

  if usaSlot ~= false then
    w.slot:setItemId(dado.item or 0)
    w.slot.onItemChange = function(widget) dado.item = widget:getItemId() salvar() end
  end
end

local function ligarLinhaShooter(w, dado)
  w.on:setChecked(dado.on)
  w.on.onCheckChange = function(_, v) dado.on = v salvar() end

  w.texto:setText(dado.texto or "")
  w.texto.onTextChange = function(_, t) dado.texto = t salvar() end

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
  ligarLinhaCura(painel.healing:recursiveGetChildById("spell1"), cfg.healing.spell[1])
  ligarLinhaCura(painel.healing:recursiveGetChildById("spell2"), cfg.healing.spell[2])
  ligarLinhaCura(painel.healing:recursiveGetChildById("spell3"), cfg.healing.spell[3])
  ligarLinhaCura(painel.healing:recursiveGetChildById("pot1"),   cfg.healing.potion[1])
  ligarLinhaCura(painel.healing:recursiveGetChildById("pot2"),   cfg.healing.potion[2])
  ligarLinhaCura(painel.healing:recursiveGetChildById("amigo1"), cfg.healing.amigo[1])
  ligarLinhaCura(painel.healing:recursiveGetChildById("amigo2"), cfg.healing.amigo[2])

  -- Tools
  ligarLinhaCura(painel.tools:recursiveGetChildById("haste"), cfg.tools.haste)
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
  ligarLinhaShooter(painel.caster:recursiveGetChildById("sh1"), cfg.caster.spell[1])
  ligarLinhaShooter(painel.caster:recursiveGetChildById("sh2"), cfg.caster.spell[2])
  ligarLinhaShooter(painel.caster:recursiveGetChildById("sh3"), cfg.caster.spell[3])
  ligarLinhaShooter(painel.caster:recursiveGetChildById("rn1"), cfg.caster.rune[1])
  ligarLinhaShooter(painel.caster:recursiveGetChildById("rn2"), cfg.caster.rune[2])
  local at = painel.caster:recursiveGetChildById("autoTarget")
  at:setChecked(cfg.caster.autoTarget)
  at.onCheckChange = function(_, v) cfg.caster.autoTarget = v salvar() end
end

function init()
  raiz = g_settings.getNode("autocaster")
  if not raiz or not raiz.presets or not raiz.presets[raiz.atual or ""] then
    raiz = { atual = "Default", presets = { Default = padroes() } }
  end
  cfg = raiz.presets[raiz.atual]
  if not cfg or not cfg.healing or not cfg.caster then
    cfg = padroes(); raiz.presets[raiz.atual] = cfg
  end

  autocasterWindow = g_ui.displayUI("autocaster")
  autocasterWindow:hide()

  local barra = autocasterWindow:getChildById("abas")
  barra:setContentWidget(autocasterWindow:getChildById("conteudoAbas"))

  painel.healing = g_ui.createWidget("PainelHealing")
  painel.tools   = g_ui.createWidget("PainelTools")
  painel.caster  = g_ui.createWidget("PainelCaster")

  barra:addTab(tr("Healing"), painel.healing, "/images/topbuttons/healthinfo")
  barra:addTab(tr("Tools"),   painel.tools,   "/images/topbuttons/options")
  barra:addTab(tr("Caster"),  painel.caster,  "/images/topbuttons/spelllist")

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
