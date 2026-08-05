-- Carga das copias fisicas e montagem do pool, no boot.
-- Spec: docs/spec_hunt_instanciada_v2.md secoes 3.1, 8.4 e 21.1.

local function carregarCopias(template)
	local caminho = DATA_DIRECTORY .. template.template.caminho
	for i, origem in ipairs(template.slotOrigens) do
		-- pos.z = 0 SEMPRE: o recorte ja guarda o andar absoluto (5-9).
		Game.loadMapChunk(caminho, Position(origem.x, origem.y, 0))
		logger.info("[hunt-instance] {} slot {} pedido em ({}, {})",
			template.slug, i, origem.x, origem.y)
	end
end

local function montarZonas(template)
	local t = template.template
	for _, slot in ipairs(InstancePool.todos(template)) do
		local a = InstancePool.area(slot)
		for _, z in ipairs(t.andares) do
			slot.zona:addArea(Position(a.x0, a.y0, z), Position(a.x1, a.y1, z))
		end
		-- Sem SpawnMonster associado, isInSpawnRange() devolve true sempre
		-- (monster.cpp:3321) e o monstro nunca e' puxado de volta. Sem isto
		-- ele passeia pra fora da instancia.
		slot.zona:trapMonsters()

		-- fronteira da hunt: barra o passo e abre o dialogo de saida, para o
		-- jogador nunca alcancar a borda do recorte e ver o vazio (secao 11.0)
		if InstanceFronteiras then
			InstanceFronteiras.registrar(slot)
		end
	end
end

local function criarSeletor(template)
	local s = template.seletor
	local tile = Tile(s.posicao)
	if not tile then
		logger.error("[hunt-instance] sem tile em {} para o seletor de {}",
			s.posicao, template.slug)
		return
	end
	-- idempotente: o boot roda toda vez, o obelisco nao pode empilhar
	local existente = tile:getItemById(s.itemId)
	if not existente then
		existente = Game.createItem(s.itemId, 1, s.posicao)
	end
	if existente then
		existente:setActionId(s.actionId)
		logger.info("[hunt-instance] seletor de {} em ({},{},{}) aid {}",
			template.slug, s.posicao.x, s.posicao.y, s.posicao.z, s.actionId)
	end
end

--- Confere que a carga e as zonas de fato aconteceram.
-- Log de "pronto" sem isto so prova que o script rodou, nao que o mapa
-- chegou. Erro de carga e' silencioso: Map::load engole o e.what().
local function conferir(template)
	local ok, semTile, semArea = 0, {}, {}
	for _, slot in ipairs(InstancePool.todos(template)) do
		local rel = template.entradasRelativas[1]
		local tile = Tile(InstancePool.posicaoReal(slot, rel))
		if not (tile and tile:getGround()) then
			semTile[#semTile + 1] = slot.indice
		elseif #slot.zona:getPositions() == 0 then
			semArea[#semArea + 1] = slot.indice
		else
			ok = ok + 1
		end
	end
	logger.info("[hunt-instance] {}: {}/{} slots com mapa e zona",
		template.slug, ok, #InstancePool.todos(template))
	if #semTile > 0 then
		logger.error("[hunt-instance] {} SEM MAPA nos slots: {}",
			template.slug, table.concat(semTile, ","))
	end
	if #semArea > 0 then
		logger.error("[hunt-instance] {} SEM ZONA nos slots: {}",
			template.slug, table.concat(semArea, ","))
	end
end

local ev = GlobalEvent("hunt_instances_startup")

function ev.onStartup()
	for _, template in pairs(HuntInstances) do
		if template.enabled then
			InstancePool.registrar(template)
			carregarCopias(template)
			criarSeletor(template)

			-- addArea itera toda posicao do retangulo e o refresh re-itera;
			-- para 169x121x5 isso e' aceitavel UMA vez no boot, e proibitivo
			-- por execucao. Por isso as zonas nascem aqui, nunca por run.
			-- Espera a carga assincrona do loadMapChunk terminar antes.
			addEvent(function()
				montarZonas(template)
				conferir(template)
			end, 5000)
		end
	end
	return true
end

ev:register()
