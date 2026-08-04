-- Spawn e respawn da instancia, em Lua.
-- Spec: docs/spec_hunt_instanciada_v2.md secao 7.
--
-- POR QUE NAO USAR O MOTOR DE SPAWN DO SERVIDOR
--
-- monster:setSpawnPosition() cria um SpawnMonster de verdade e faz
-- emplace_back na lista GLOBAL (monster_functions.cpp:433). Nada no codigo
-- remove entradas dessa lista exceto SpawnsMonster::clear() no reload de mapa.
-- Cada execucao vazaria N entradas permanentes. Alem disso tem radius e
-- direcao hardcoded.
--
-- AS QUATRO ARMADILHAS QUE QUEBRAM A PARIDADE (secao 7.4)
--
--   1. 5o argumento de Game.createMonster e' `master`: o monstro vira summon
--      e Player::onKilledMonster devolve false antes do bestiary. NUNCA passar.
--   2. a lib Encounter chama setRewardBoss() em todo monstro que cria
--      (encounters.lua:217) -- o loot normal some. Nao usar para hunt.
--   3. Monster:soulPit(true) faz setDropLoot(false) e bypassa o bestiary.
--   4. piso com TILESTATE_NOLOGOUT sai do pool de forge (game.cpp:12074).
--      Por isso a spec decidiu nao marcar o piso (secao 6.3).
--
-- Fora dessas quatro, bestiary/charms/loot/exp sao AGNOSTICOS a origem do
-- monstro: Player::onKilledMonster (player.cpp:6571) so guarda contra
-- hasBeenSummoned() e getSoulPit(); addBestiaryKill so olha raceid.

InstanceSpawns = InstanceSpawns or {}

local EVENTO_MORTE = "HuntInstanceMonsterDeath"

-- creatureId -> { slot = , ponto = }
local porCriatura = {}

--- Nasce um monstro num ponto, se puder.
local function nascer(slot, ponto)
	local tile = Tile(ponto.pos)
	if not tile then
		return false
	end
	-- Replica a regra do SpawnMonster::checkSpawnMonster: monstro bloqueante
	-- nao nasce em cima de jogador. Sem isso, alguem parado no ponto de
	-- respawn trava ou empurra o spawn.
	if tile:getTopCreature() then
		return false
	end

	-- extended = true amplia a busca de tile livre; force = true ignora
	-- restricao de tile. SEM 5o argumento (ver cabecalho).
	local monstro = Game.createMonster(ponto.def.nome, ponto.pos, true, true)
	if not monstro then
		return false
	end

	monstro:registerEvent(EVENTO_MORTE)
	ponto.criatura = monstro:getId()
	porCriatura[ponto.criatura] = { slot = slot, ponto = ponto }
	return true
end

--- Agenda o renascimento e guarda o handle para poder cancelar no teardown.
local function agendar(slot, ponto)
	if ponto.evento then
		stopEvent(ponto.evento)
	end
	ponto.evento = addEvent(function()
		ponto.evento = nil
		-- a execucao pode ter acabado enquanto o timer corria
		if slot.spawnsAtivos then
			if not nascer(slot, ponto) then
				agendar(slot, ponto)   -- tile ocupado: tenta de novo
			end
		end
	end, ponto.def.respawnMs)
end

--- Monta os pontos do slot e nasce todo mundo. Chamado ao criar a execucao.
function InstanceSpawns.iniciar(slot)
	local defs = HuntInstanceSpawns and HuntInstanceSpawns[slot.template.slug]
	if not defs then
		logger.error("[hunt-instance] sem spawns definidos para {}",
			slot.template.slug)
		return 0
	end

	slot.pontos = {}
	slot.spawnsAtivos = true
	local nascidos = 0
	for _, def in ipairs(defs) do
		local ponto = {
			def = def,
			pos = InstancePool.posicaoReal(slot, def),
			criatura = nil,
			evento = nil,
		}
		slot.pontos[#slot.pontos + 1] = ponto
		if nascer(slot, ponto) then
			nascidos = nascidos + 1
		else
			agendar(slot, ponto)
		end
	end
	logger.info("[hunt-instance] slot {} do {}: {}/{} monstros nasceram",
		slot.indice, slot.template.slug, nascidos, #defs)
	return nascidos
end

--- Cancela tudo e remove os monstros. Chamado no teardown.
function InstanceSpawns.parar(slot)
	slot.spawnsAtivos = false
	for _, ponto in ipairs(slot.pontos or {}) do
		if ponto.evento then
			stopEvent(ponto.evento)
			ponto.evento = nil
		end
		if ponto.criatura then
			porCriatura[ponto.criatura] = nil
			ponto.criatura = nil
		end
	end
	-- cache vivo de criaturas da zona: custo O(monstros), sem varrer tile
	slot.zona:removeMonsters()
	slot.pontos = nil
end

--- Quantos monstros do slot estao vivos agora.
function InstanceSpawns.vivos(slot)
	local n = 0
	for _, ponto in ipairs(slot.pontos or {}) do
		if ponto.criatura and Monster(ponto.criatura) then
			n = n + 1
		end
	end
	return n
end

-- ------------------------------------------------------------------ evento

local morte = CreatureEvent(EVENTO_MORTE)

function morte.onDeath(creature)
	local id = creature:getId()
	local reg = porCriatura[id]
	if not reg then
		return true
	end
	porCriatura[id] = nil
	reg.ponto.criatura = nil
	if reg.slot.spawnsAtivos then
		agendar(reg.slot, reg.ponto)
	end
	return true
end

morte:register()
