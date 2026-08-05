-- Limpeza do slot entre execucoes. Spec secao 13.
--
-- POR QUE ISTO E' URGENTE, e nao arrumacao: sem limpar, o grupo B pega o slot
-- do grupo A e encontra o loot dele no chao. Isso e' duplicacao de item -- o
-- mesmo corpo de dragao rende loot uma vez por grupo que passar pelo slot.
--
-- NAO varre tiles. Zone:getItems() e Zone:getMonsters() sao caches VIVOS,
-- mantidos incrementalmente por Tile::addThing/removeThing (tile.cpp:1983,
-- 2004, 556). Custo O(entidades), nao O(area). A spec v1 pedia "100 tiles por
-- ciclo" -- desnecessario, o cache ja existe.

InstanceCleaner = InstanceCleaner or {}

--- Decide se o item deve ser REMOVIDO na limpeza.
--
-- A primeira versao usava "nao movivel = cenario", e estava errada: spikes
-- (id 2148) nao sao moviveis e tambem nao sao cenario -- ficaram no chao da
-- hunt. "Movivel" descreve como o item se comporta ao ser empurrado, nao se
-- ele pertence ao mapa.
--
-- O criterio certo e por NATUREZA do item. Sai o que aparece durante o jogo:
-- loot, corpo, campo magico, sacola. Fica o que veio do OTBM: chao, parede,
-- escada, porta.
local function deveRemover(item)
	local it = ItemType(item:getId())
	if not it then
		return false         -- na duvida, preserva: melhor sujeira que buraco
	end
	if it:isGroundTile() or it:isDoor() then
		return false
	end
	-- o que um jogador larga ou o que uma luta deixa
	return it:isPickupable()
		or it:isCorpse()
		or it:isMagicField()
		or it:isContainer()
		or it:isRune()
end

--- Remove o que os jogadores deixaram: loot, corpos, sacolas, campos.
--
-- Devolve tambem os ids preservados mais frequentes.
--
-- O numero de preservados CRESCE entre execucoes (606, 2247, 4161) e isso
-- parece vazamento, mas nao e'. Os ids mais comuns sao grama, borda de rocha
-- e cascalho -- cenario do proprio recorte. O Zone:getItems() e' um cache
-- preenchido sob demanda, e a zona nasce DEPOIS do loadMapChunk: os itens do
-- mapa nunca passaram pelo thingAdded, entao entram no cache aos poucos,
-- conforme a area e' visitada.
--
-- Nada disso afeta a limpeza: o que aparece DURANTE a execucao (corpo, loot,
-- sacola, campo) passa por Tile::addThing -> Zone::thingAdded, entao o cache
-- sempre conhece a sujeira. O log dos ids fica para nao ter de redescobrir
-- isso na proxima vez que alguem estranhar o numero.
function InstanceCleaner.removerItens(slot)
	local removidos, preservados = 0, 0
	local porId = {}
	for _, item in ipairs(slot.zona:getItems() or {}) do
		if deveRemover(item) then
			item:remove()
			removidos = removidos + 1
		else
			preservados = preservados + 1
			local id = item:getId()
			porId[id] = (porId[id] or 0) + 1
		end
	end
	return removidos, preservados, porId
end

--- Os ids preservados mais comuns, como texto para o log.
local function maisComuns(porId, quantos)
	local lista = {}
	for id, n in pairs(porId) do
		lista[#lista + 1] = { id = id, n = n }
	end
	table.sort(lista, function(a, b) return a.n > b.n end)
	local partes = {}
	for i = 1, math.min(quantos, #lista) do
		partes[#partes + 1] = string.format("%dx id %d", lista[i].n, lista[i].id)
	end
	return table.concat(partes, ", ")
end

--- Teardown completo do slot. Chamado ao encerrar a execucao.
function InstanceCleaner.limpar(slot, motivo)
	slot.estado = InstancePool.ESTADOS.CLEANING

	-- 1. para os respawns antes de remover, senao um timer em voo repovoa
	--    o slot depois da limpeza
	InstanceSpawns.parar(slot)

	-- 2. o que sobrou de criatura (summon do jogador, monstro fora da lista)
	slot.zona:removeMonsters()

	-- 3. itens largados
	local removidos, preservados, porId = InstanceCleaner.removerItens(slot)

	-- 4. ninguem pode ficar para tras
	--
	-- Aqui e' rede de seguranca, nao caminho normal: quem sai pelo sair() ja
	-- foi devolvido ao ponto de entrada. Se alguem AINDA aparece nesta lista,
	-- e' porque a volta dele falhou -- e ai o log tem de dizer, senao o
	-- jogador reaparece longe de onde entrou sem explicacao nenhuma.
	local presos = slot.zona:getPlayers() or {}
	for _, p in ipairs(presos) do
		if InstanceFronteiras then
			InstanceFronteiras.autorizarSaida(p)
			InstanceFronteiras.esquecer(p)
		end
		local destino = slot.template.retornoGlobal
			or slot.template.retornoEmergencia
		logger.warn("[hunt-instance] {} ainda estava no slot {} na limpeza; "
			.. "despejado em {},{},{}", p:getName(), slot.indice,
			destino.x, destino.y, destino.z)
		if not p:teleportTo(destino) then
			p:teleportTo(destino, true)
		end
		p:sendTextMessage(MESSAGE_EVENT_ADVANCE,
			"A instancia foi encerrada.")
	end

	slot.run = nil
	slot.estado = InstancePool.ESTADOS.FREE

	logger.info("[hunt-instance] slot {} limpo ({}): {} itens removidos, "
		.. "{} de cenario preservados, {} jogador(es) retirado(s)",
		slot.indice, motivo or "sem motivo", removidos, preservados, #presos)
	logger.info("[hunt-instance] slot {} preservados mais comuns: {}",
		slot.indice, maisComuns(porId, 8))
	return removidos
end

--- Confere que o slot esta mesmo vazio. Usado no teste dos 100 ciclos.
function InstanceCleaner.verificar(slot)
	local monstros = #(slot.zona:getMonsters() or {})
	local jogadores = #(slot.zona:getPlayers() or {})
	local soltos = 0
	for _, item in ipairs(slot.zona:getItems() or {}) do
		if deveRemover(item) then
			soltos = soltos + 1
		end
	end
	return monstros == 0 and jogadores == 0 and soltos == 0,
		monstros, jogadores, soltos
end
