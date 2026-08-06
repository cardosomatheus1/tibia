-- Teste da carga sob demanda: /testecarga [n]     padrao 50
--
-- O /testeciclos existente usa um slot fixo e so' cicla spawns -- nao passa
-- pelo alocar/liberar, entao nao exercita carregar nem descarregar. Este passa.
--
-- O QUE ELE PROVA, E POR QUE NAO E' O RSS
--
-- Medir memoria do processo engana: o alocador do sistema devolve paginas
-- quando quer, entao RSS estavel nao prova que nada vazou e RSS crescendo nao
-- prova que vazou. O que prova e' estrutural: depois do descarregar, o tile
-- TEM de sumir. Se ele continua la', a memoria ficou presa -- e nenhum numero
-- de RSS muda isso.
--
-- Entao aqui se mede o que e' determinista:
--
--   tile existe depois de carregar    (senao o jogador cai num buraco)
--   tile some depois de descarregar   (senao nao adiantou nada)
--   quanto tempo a carga levou        (o jogador espera isso)
--
-- O RSS se olha de fora, com ps, enquanto isto roda. E' complemento, nao a
-- prova.
--
-- SEM JOGADOR de proposito, igual ao /testeciclos: amarrar um personagem a
-- cinquenta ciclos so' limitaria o numero de ciclos.

local FATIA = 5              -- ciclos por fatia, para nao prender o servidor

local function tileDeProva(slot)
	local e = slot.template.entradasRelativas[1]
	return Position(slot.origem.x + e.x, slot.origem.y + e.y, e.z)
end

--- Uma volta: aloca, carrega, confere, libera, confere.
local function umCiclo(template, n, rel, seguir)
	local slot = InstancePool.alocar(template)
	if not slot then
		rel.falhas[#rel.falhas + 1] = string.format(
			"ciclo %d: nenhum slot livre", n)
		seguir()
		return
	end

	-- Nao ha relogio de milissegundos neste Lua (os.time da' segundos e
	-- os.clock da' CPU, nao parede). Entao o tempo se mede em CHECAGENS: o
	-- InstancePool.carregar confere a cada 50 ms, e ele registra no log quantos
	-- ms levou. Aqui basta contar quantas voltas foram instantaneas -- carga
	-- que termina antes da primeira checagem e' o caso bom.
	local instantanea = InstancePool.carregado(slot)
	InstancePool.carregar(slot, function(carregou)
		if instantanea then
			rel.instantaneas = rel.instantaneas + 1
		end

		if not carregou or not Tile(tileDeProva(slot)) then
			rel.falhas[#rel.falhas + 1] = string.format(
				"ciclo %d: mapa nao apareceu depois de carregar", n)
			InstancePool.liberar(slot, "teste de carga")
			seguir()
			return
		end

		InstancePool.liberar(slot, "teste de carga")

		-- a prova: sem isto, sob demanda so' adia o custo
		if Tile(tileDeProva(slot)) then
			rel.falhas[#rel.falhas + 1] = string.format(
				"ciclo %d: tile continua no mapa depois de descarregar", n)
		else
			rel.ok = rel.ok + 1
		end
		seguir()
	end)
end

local function rodarFatia(template, n, total, rel, terminar)
	if n > total then
		terminar()
		return
	end
	local feitos = 0
	local function proximo()
		feitos = feitos + 1
		if feitos >= FATIA or n + feitos > total then
			addEvent(function()
				rodarFatia(template, n + feitos, total, rel, terminar)
			end, 100)
		else
			umCiclo(template, n + feitos, rel, proximo)
		end
	end
	umCiclo(template, n, rel, proximo)
end

local tk = TalkAction("/testecarga")

function tk.onSay(player, words, param)
	local total = tonumber(param) or 50
	if total < 1 or total > 500 then
		player:sendCancelMessage("Use /testecarga [1..500]")
		return false
	end

	local template = HuntInstances.thaisCyclops
	if not template then
		player:sendCancelMessage("Catalogo nao carregado.")
		return false
	end

	local rel = { ok = 0, falhas = {}, instantaneas = 0 }
	player:sendTextMessage(MESSAGE_EVENT_ADVANCE,
		string.format("Teste de carga: %d ciclos em %s. Acompanhe o log.",
			total, template.slug))
	logger.info("[hunt-instance] teste de carga: {} ciclos em {}",
		total, template.slug)

	rodarFatia(template, 1, total, rel, function()
		logger.info("[hunt-instance] teste de carga: {}/{} ok "
			.. "({} ja estavam carregados). O tempo de cada carga sai nas "
			.. "linhas 'carregado em N ms' acima.",
			rel.ok, total, rel.instantaneas)
		for _, f in ipairs(rel.falhas) do
			logger.error("[hunt-instance] {}", f)
		end
		if player and player:isPlayer() then
			player:sendTextMessage(MESSAGE_EVENT_ADVANCE, string.format(
				"Teste de carga: %d/%d ok, %d falha(s)", rel.ok, total,
				#rel.falhas))
		end
	end)
	return false
end

tk:separator(" ")
tk:groupType("god")
tk:register()
