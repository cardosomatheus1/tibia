-- Carga das copias fisicas e montagem do pool, no boot.
-- Spec: docs/spec_hunt_instanciada_v2.md secoes 3.1, 8.4 e 21.1.

-- O recorte NAO entra mais na memoria no boot.
--
-- Pre-alocar custa ~13 MB por slot mesmo vazio -- medido, 6 para 12 slots em 9
-- hunts levou o servidor de 2004 para 2799 MB. Com as 65 hunts contornadas
-- seriam ~5,7 GB. Agora quem carrega e' o InstancePool.carregar, na entrada, e
-- o InstancePool.descarregar devolve na saida.
--
-- O OBJETO da zona continua nascendo aqui, porque Zone nao e' destruivel. A
-- AREA dela nao: ela custa mais que o proprio recorte -- medido, tirar os 54
-- recortes do boot economizou 103 MB e dobrar os slots tinha custado 795 -- e
-- agora sobe e desce junto com o mapa, no InstancePool.

local function montarZonas(template)
	-- Cria os OBJETOS de zona e liga o comportamento deles. A AREA nao entra
	-- aqui: ela custa mais que o recorte do mapa e agora sobe e desce junto com
	-- ele, no InstancePool.montarAreas.
	--
	-- Medido: tirar os 54 recortes do boot economizou 103 MB, mas dobrar os
	-- slots tinha custado 795. A diferenca eram as zonas -- cada posicao do
	-- retangulo guardada duas vezes (zone.hpp:187 e :199), vezes DUAS zonas por
	-- slot, a do pool e a da fronteira.
	--
	-- Zone nao e' destruivel, entao o objeto nasce aqui e vive para sempre. Isso
	-- e' barato: o que pesa e' a area, e essa da' para tirar com subtractArea.
	for _, slot in ipairs(InstancePool.todos(template)) do
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
	-- Nem tile nem area de zona sao conferidos aqui: os dois entram sob
	-- demanda, entao no boot o certo e' NAO existirem. O que se confere e' o
	-- que tem de estar de pe' antes de alguem chegar -- o slot registrado, o
	-- objeto de zona criado e a fronteira ligada.
	local ok, falhos = 0, {}
	for _, slot in ipairs(InstancePool.todos(template)) do
		if slot.zona and slot.zonaHunt then
			ok = ok + 1
		else
			falhos[#falhos + 1] = slot.indice
		end
	end
	logger.info("[hunt-instance] {}: {}/{} slots com zona (mapa sob demanda)",
		template.slug, ok, #InstancePool.todos(template))
	if #falhos > 0 then
		logger.error("[hunt-instance] {} SEM ZONA nos slots: {}",
			template.slug, table.concat(falhos, ","))
	end
end

local ev = GlobalEvent("hunt_instances_startup")

function ev.onStartup()
	for _, template in pairs(HuntInstances) do
		if template.enabled then
			InstancePool.registrar(template)
			criarSeletor(template)

			-- So' os objetos de zona e o trapMonsters; a area entra na
			-- primeira entrada de cada slot.
			-- Segue fora do onStartup so' para nao atrasar o servidor a subir.
			addEvent(function()
				montarZonas(template)
				conferir(template)
			end, 1000)
		end
	end
	return true
end

ev:register()
