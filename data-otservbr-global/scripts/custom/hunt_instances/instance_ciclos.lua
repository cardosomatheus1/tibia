-- Etapa 6: teste de vazamento por ciclos. Spec secao 21.
--
--     /testeciclos [n]      padrao 100
--
-- Um ciclo e' abrir e fechar uma execucao: 204 monstros nascem, a zona e'
-- limpa, o slot volta ao pool. E' o que mais aloca em toda a feature, e o que
-- mais roda ao longo da vida do servidor -- se algo vaza, vaza aqui.
--
-- SEM JOGADOR de proposito. O ciclo com jogador ja e' coberto pelo
-- /testeinstancia; o que este mede e' o custo REPETIDO de nascer e morrer 204
-- monstros, e amarrar um personagem a isso so limitaria o numero de ciclos.
--
-- Roda em fatias, com addEvent entre elas. Cem ciclos em linha reta prendem o
-- servidor por dezenas de segundos, e o Lua do Canary e' single-threaded: nada
-- mais anda enquanto isso. Em fatias, o servidor respira entre uma e outra.
--
-- O que se mede:
--   monstros    tem de dar 204 ao nascer e 0 depois de limpar, TODA vez
--   zonas       nao pode aparecer zona nova (o Zone e' get-or-create e NAO e'
--               destruivel -- uma por ciclo vazaria para sempre, spec 8.4)
--   itens       o cache do slot nao pode crescer de ciclo para ciclo
--   memoria     medida de fora, via RSS do processo, antes e depois

local FATIA = 5             -- ciclos por fatia
local ESPERA = 250          -- ms entre fatias

local function contarMonstros(slot)
	return #(slot.zona:getMonsters() or {})
end

local function contarItens(slot)
	return #(slot.zona:getItems() or {})
end

--- Uma volta completa: nascer, conferir, limpar, conferir.
local function umCiclo(slot, n, relatorio)
	InstanceSpawns.iniciar(slot)
	local nasceram = contarMonstros(slot)
	if nasceram ~= relatorio.esperado then
		relatorio.falhas[#relatorio.falhas + 1] = string.format(
			"ciclo %d: nasceram %d, esperava %d", n, nasceram, relatorio.esperado)
	end

	InstanceSpawns.parar(slot)
	slot.zona:removeMonsters()
	local removidos = InstanceCleaner.removerItens(slot)
	relatorio.removidos = relatorio.removidos + removidos

	local sobraram = contarMonstros(slot)
	if sobraram ~= 0 then
		relatorio.falhas[#relatorio.falhas + 1] = string.format(
			"ciclo %d: %d monstros sobraram depois de limpar", n, sobraram)
	end
	relatorio.itens[n] = contarItens(slot)
end

local fatia

-- playerId e nao o Player: userdata atravessando addEvent e' a armadilha que o
-- proprio datapack evita (exercise_training_weapons.lua:208 passa o id).
function fatia(playerId, slot, n, total, relatorio)
	local ate = math.min(n + FATIA - 1, total)
	for i = n, ate do
		umCiclo(slot, i, relatorio)
	end

	if ate < total then
		if ate % 25 == 0 then
			logger.info("[hunt-instance] ciclos: {}/{}", ate, total)
			local p = Player(playerId)
			if p then
				p:sendTextMessage(MESSAGE_EVENT_ADVANCE,
					string.format("ciclos: %d/%d", ate, total))
			end
		end
		addEvent(function()
			fatia(playerId, slot, ate + 1, total, relatorio)
		end, ESPERA)
		return
	end

	-- ------------------------------------------------------------ resultado
	slot.estado = InstancePool.ESTADOS.FREE
	local primeiro, ultimo = relatorio.itens[1], relatorio.itens[total]
	local zonasDepois = #Zone.getAll()

	local linhas = {
		string.format("=== %d ciclos ===", total),
		string.format("monstros por ciclo: %d esperados", relatorio.esperado),
		string.format("itens no slot: %d no 1o ciclo, %d no ultimo",
			primeiro, ultimo),
		string.format("zonas: %d antes, %d depois", relatorio.zonasAntes,
			zonasDepois),
		string.format("itens removidos no total: %d", relatorio.removidos),
	}
	if zonasDepois ~= relatorio.zonasAntes then
		linhas[#linhas + 1] = string.format(
			"FALHA vazou %d zona(s) -- Zone nao e' destruivel (spec 8.4)",
			zonasDepois - relatorio.zonasAntes)
	end
	for _, f in ipairs(relatorio.falhas) do
		linhas[#linhas + 1] = "FALHA " .. f
	end
	if #relatorio.falhas == 0 and zonasDepois == relatorio.zonasAntes then
		linhas[#linhas + 1] = "sem falhas"
	end

	local p = Player(playerId)
	for _, l in ipairs(linhas) do
		logger.info("[CICLOS] {}", l)
		if p then
			p:sendTextMessage(MESSAGE_EVENT_ADVANCE, l)
		end
	end
end

local tk = TalkAction("/testeciclos")

function tk.onSay(player, words, param)
	if player:getGroup():getId() < GROUP_TYPE_GOD then
		return true
	end

	local total = math.max(1, math.min(500, tonumber(param) or 100))
	local tpl = HuntInstances.thaisCyclops

	-- Slot proprio, nao o alocar(): o teste nao pode roubar vaga de jogador
	-- nem ser interrompido por alguem entrando. O ultimo do pool e' o menos
	-- disputado, porque o alocar() sempre pega o primeiro livre.
	local slot = InstancePool.get(tpl, tpl.maximoSlots)
	if not slot or slot.run then
		player:sendTextMessage(MESSAGE_EVENT_ADVANCE,
			"O ultimo slot esta em uso; tente de novo mais tarde.")
		return true
	end
	slot.estado = InstancePool.ESTADOS.CLEANING   -- fora do alcance do alocar

	-- a lista de spawns nao vive no template: fica no HuntInstanceSpawns,
	-- indexado pelo slug (ver instance_spawns.lua)
	local defs = HuntInstanceSpawns and HuntInstanceSpawns[tpl.slug]
	if not defs then
		player:sendTextMessage(MESSAGE_EVENT_ADVANCE,
			"Sem spawns definidos para " .. tpl.slug .. ".")
		slot.estado = InstancePool.ESTADOS.FREE
		return true
	end

	local relatorio = {
		esperado = #defs,
		falhas = {},
		itens = {},
		removidos = 0,
		zonasAntes = #Zone.getAll(),
	}

	player:sendTextMessage(MESSAGE_EVENT_ADVANCE, string.format(
		"Rodando %d ciclos no slot %d. Acompanhe pelo log.", total, slot.indice))
	logger.info("[CICLOS] inicio: {} ciclos no slot {}, {} zonas",
		total, slot.indice, relatorio.zonasAntes)

	fatia(player:getId(), slot, 1, total, relatorio)
	return true
end

tk:separator(" ")
tk:groupType("god")
tk:register()
