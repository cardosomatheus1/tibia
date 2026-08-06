-- Carga das copias fisicas e montagem do pool, no boot.
-- Spec: docs/spec_hunt_instanciada_v2.md secoes 3.1, 8.4 e 21.1.

-- O recorte NAO entra mais na memoria no boot.
--
-- Pre-alocar custa ~13 MB por slot mesmo vazio -- medido, 6 para 12 slots em 9
-- hunts levou o servidor de 2004 para 2799 MB. Com as 65 hunts contornadas
-- seriam ~5,7 GB. Agora quem carrega e' o InstancePool.carregar, na entrada, e
-- o InstancePool.descarregar devolve na saida.
--
-- A ZONA continua nascendo aqui, e de proposito: addArea itera toda posicao do
-- retangulo, o que e' aceitavel uma vez no boot e proibitivo por execucao. E
-- zona nao depende de tile existir -- e' so' coordenada.

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
	-- Nao confere mais se o tile existe: agora nao deve existir mesmo antes de
	-- alguem entrar. O que se confere e' a zona, que nasce no boot.
	local ok, semArea = 0, {}
	for _, slot in ipairs(InstancePool.todos(template)) do
		if #slot.zona:getPositions() == 0 then
			semArea[#semArea + 1] = slot.indice
		else
			ok = ok + 1
		end
	end
	logger.info("[hunt-instance] {}: {}/{} slots com zona (mapa sob demanda)",
		template.slug, ok, #InstancePool.todos(template))
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
			criarSeletor(template)

			-- addArea itera toda posicao do retangulo e o refresh re-itera;
			-- para 169x121x5 isso e' aceitavel UMA vez no boot, e proibitivo
			-- por execucao. Por isso as zonas nascem aqui, nunca por run.
			-- Nao ha mais carga assincrona para esperar, mas as zonas seguem
			-- fora do onStartup: addArea em 9 hunts x 6 slots dentro do boot
			-- atrasaria o servidor a subir.
			addEvent(function()
				montarZonas(template)
				conferir(template)
			end, 1000)
		end
	end
	return true
end

ev:register()
