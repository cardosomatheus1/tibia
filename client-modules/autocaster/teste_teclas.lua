-- Banco de prova das teclas de atalho do AutoCaster.
--
-- POR QUE EXISTE. O modulo roda dentro do otclient, que precisa de janela,
-- OpenGL e assets -- nao da' para subir aqui so' para conferir se um toggle
-- inverte a chave certa. Este arquivo simula as APIs do client (g_keyboard,
-- g_settings, g_game, modules...), carrega o autocaster.lua DE VERDADE e
-- exercita o caminho das teclas.
--
-- O que ele cobre: registro e liberacao de binds, o que cada acao inverte,
-- exclusividade de combinacao, persistencia e a migracao de preset antigo.
-- O que ele NAO cobre: desenho da interface e o toque real de tecla -- isso
-- so' no client em jogo.
--
-- Uso:  lua5.4 client-modules/autocaster/teste_teclas.lua

local falhas, total = 0, 0

local function ok(cond, oque)
	total = total + 1
	if cond then
		print(("  ok   %s"):format(oque))
	else
		falhas = falhas + 1
		print(("  FALHA %s"):format(oque))
	end
end

local function igual(a, b, oque)
	ok(a == b, ("%s  (esperado %s, veio %s)"):format(oque, tostring(b), tostring(a)))
end

-- ------------------------------------------------ simulacao do client

local binds = {}          -- combinacao -> callback
local avisos = {}         -- mensagens mostradas na tela
local salvou = 0

g_keyboard = {
	bindKeyDown = function(desc, cb) binds[desc] = cb end,
	unbindKeyDown = function(desc) binds[desc] = nil end,
}

local nodeSalvo = nil
g_settings = {
	getNode = function() return nodeSalvo end,
	setNode = function(_, v) nodeSalvo = v end,
	save = function() salvou = salvou + 1 end,
}

g_clock = { millis = function() return 0 end }
g_game = {
	isOnline = function() return false end,
	getLocalPlayer = function() return nil end,
	getAttackingCreature = function() return nil end,
	getChaseMode = function() return 0 end,
	setChaseMode = function() end,
	attack = function() end,
}
g_map = { getSpectatorsInRange = function() return {} end }
g_ui = { displayUI = function() return nil end }
g_logger = { info = function() end, warning = function() end, error = function() end }

modules = {
	game_textmessage = {
		displayStatusMessage = function(t) avisos[#avisos + 1] = t end,
	},
}

function tr(s) return s end
function connect() end
function disconnect() end
function cycleEvent() return { cancel = function() end } end
function scheduleEvent() return { cancel = function() end } end
function determineKeyComboDesc(code) return code end
ChaseOpponent = 1

-- ------------------------------------------------ carga do modulo real

-- O modulo declara init/terminate como globais e o resto como locais. Para
-- alcancar os locais, carregamos o arquivo num ambiente proprio e pedimos os
-- upvalues das funcoes globais que ele deixou para tras.
local caminho = "client-modules/autocaster/autocaster.lua"
local chunk, err = loadfile(caminho)
if not chunk then
	print("nao consegui carregar " .. caminho .. ": " .. tostring(err))
	os.exit(1)
end
chunk()

-- pesca um local do modulo pelos upvalues de uma funcao global dele
local function upvalue(fn, nome)
	local i = 1
	while true do
		local n, v = debug.getupvalue(fn, i)
		if not n then return nil end
		if n == nome then return v, i end
		i = i + 1
	end
end

local function setUpvalue(fn, nome, valor)
	local _, i = upvalue(fn, nome)
	if i then debug.setupvalue(fn, i, valor) end
end

local padroes       = upvalue(init, "padroes")
local migrarConfig  = upvalue(init, "migrarConfig")
local prenderTeclas = upvalue(init, "prenderTeclas")
-- soltarTeclas so' aparece em terminate: init nunca precisa soltar
local soltarTeclas  = upvalue(terminate, "soltarTeclas")

if not (padroes and migrarConfig and prenderTeclas and soltarTeclas) then
	print("nao achei as funcoes internas -- o modulo mudou de forma?")
	os.exit(1)
end

-- cfg e raiz sao locais do modulo compartilhados por todas as closures: em Lua
-- o upvalue e' uma celula unica, entao trocar por init basta -- prenderTeclas
-- e as callbacks dos binds enxergam a mesma coisa.
local cfg = padroes()
local raiz = { atual = "Default", presets = { Default = cfg } }
setUpvalue(init, "cfg", cfg)
setUpvalue(init, "raiz", raiz)

-- ------------------------------------------------ testes

print("\n== padroes ==")
igual(cfg.chaves.cura, true, "cura comeca ligada")
igual(cfg.chaves.magia, true, "magia comeca ligada")
igual(cfg.chaves.runa, true, "runa comeca ligada")
igual(cfg.teclas.geral, "", "nenhuma tecla vem fixa de fabrica")

print("\n== registro de binds ==")
cfg.teclas.geral = "="
cfg.teclas.cura = "'"
cfg.teclas.magiaRuna = "Ctrl+G"
prenderTeclas()
ok(binds["="] ~= nil, "registrou a tecla geral")
ok(binds["'"] ~= nil, "registrou a tecla de cura")
ok(binds["Ctrl+G"] ~= nil, "registrou a tecla de magia+runa")
igual(binds["F1"], nil, "nao registrou tecla que ninguem pediu")

print("\n== o que cada acao inverte ==")
igual(cfg.ligado, false, "autocaster comeca desligado")
binds["="]()
igual(cfg.ligado, true, "geral ligou o autocaster")
binds["="]()
igual(cfg.ligado, false, "geral desligou de novo")

binds["'"]()
igual(cfg.chaves.cura, false, "cura desligou")
igual(cfg.chaves.magia, true, "cura nao mexeu na magia")
binds["'"]()
igual(cfg.chaves.cura, true, "cura voltou")

print("\n== magia + runa na mesma tecla ==")
binds["Ctrl+G"]()
igual(cfg.chaves.magia, false, "desligou magia")
igual(cfg.chaves.runa, false, "desligou runa junto")
binds["Ctrl+G"]()
igual(cfg.chaves.magia, true, "religou magia")
igual(cfg.chaves.runa, true, "religou runa junto")

-- divergentes: o primeiro toque deve LIGAR as duas, nao apagar a que estava on
cfg.chaves.magia, cfg.chaves.runa = true, false
binds["Ctrl+G"]()
igual(cfg.chaves.magia, true, "estado misto -> liga as duas (magia)")
igual(cfg.chaves.runa, true, "estado misto -> liga as duas (runa)")

print("\n== avisos na tela ==")
ok(#avisos > 0, "cada toggle avisa o jogador")
ok(tostring(avisos[#avisos]):find("ligado") ~= nil, "o aviso diz o estado novo")

print("\n== soltar binds ==")
soltarTeclas()
igual(binds["="], nil, "soltou a tecla geral")
igual(binds["'"], nil, "soltou a tecla de cura")
igual(binds["Ctrl+G"], nil, "soltou a tecla de magia+runa")

print("\n== rebind nao deixa a tecla velha respondendo ==")
cfg.teclas.geral = "="
prenderTeclas()
ok(binds["="] ~= nil, "tecla velha ativa")
cfg.teclas.geral = "F4"
prenderTeclas()
igual(binds["="], nil, "tecla velha foi solta")
ok(binds["F4"] ~= nil, "tecla nova responde")
soltarTeclas()

print("\n== preset antigo (sem chaves/teclas) ==")
local velho = padroes()
velho.chaves, velho.teclas = nil, nil
migrarConfig(velho)
igual(type(velho.chaves), "table", "migracao criou as chaves")
igual(type(velho.teclas), "table", "migracao criou as teclas")
igual(velho.chaves.cura, true, "chave nova entra ligada")
igual(velho.teclas.geral, "", "tecla nova entra vazia")

local parcial = padroes()
parcial.chaves.runa = nil
parcial.teclas.magiaRuna = nil
migrarConfig(parcial)
igual(parcial.chaves.runa, true, "completou chave faltando sem apagar o resto")
igual(parcial.teclas.magiaRuna, "", "completou tecla faltando")

-- ------------------------------------------------ resultado

print(("\n%d testes, %d falha(s)"):format(total, falhas))
os.exit(falhas == 0 and 0 or 1)
