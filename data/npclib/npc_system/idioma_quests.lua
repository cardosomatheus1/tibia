-- Traducao do quest log, da linha de missoes e da quest tracker.
--
-- Mesma ideia do idioma.lua: embrulha os pontos por onde o texto sai
-- (getQuestName, getMissionName, getMissionDescription — tudo o mais,
-- como sendQuestLog e a quest tracker, ja passa por eles) e troca pelo
-- texto do idioma do jogador. Sem tradução, sai em inglês — nunca vazio.
--
-- Descricao/estado de missao pode ser uma string fixa (traduz via
-- Idioma.saida, igual a fala de NPC) ou uma function(player) que monta o
-- texto com um valor dinamico no meio (ex.: "Voce tem %d pontos..."). Uma
-- string inteira nunca bate depois que o numero foi resolvido, entao esses
-- casos usam QuestsDinamico: a mesma logica da function original, só que
-- com o texto em portugues.

QuestsDinamico = QuestsDinamico or {}
-- QuestsDinamico[questId][missionId] = {
--   description = function(player) ... end,        -- so quando mission.description e function
--   states = { [stateIndex] = function(player) ... end },  -- so quando aquele estado e function
-- }

local function avaliar_texto(valor, player)
	if type(valor) == "function" then
		return tostring(valor(player))
	end
	return tostring(valor)
end

local function override_de(questId, missionId)
	local porQuest = QuestsDinamico[questId]
	return porQuest and porQuest[missionId]
end

-- ------------------------------------------------------------ nome da quest

local getQuestName_original = Player.getQuestName
function Player.getQuestName(self, questId)
	return Idioma.saida(getQuestName_original(self, questId), self)
end

-- ---------------------------------------------------------- nome da missao

function Player.getMissionName(self, questId, missionId)
	local mission = Game.getMission(questId, missionId)
	if not mission then
		return ""
	end
	local nome = Idioma.saida(mission.name, self)
	if self:missionIsCompleted(questId, missionId) then
		local completo = (Idioma.do_jogador(self) == "pt") and " (concluída)" or " (completed)"
		return nome .. completo
	end
	return nome
end

-- ----------------------------------------------------- descricao da missao

function Player.getMissionDescription(self, questId, missionId)
	local mission = Game.getMission(questId, missionId)
	if not mission then
		return Idioma.saida("An error has occurred, please contact a gamemaster.", self)
	end

	local overrides = override_de(questId, missionId)

	if mission.description then
		if type(mission.description) == "string" then
			return Idioma.saida(mission.description, self)
		end
		if overrides and overrides.description then
			return tostring(overrides.description(self))
		end
		return avaliar_texto(mission.description, self)
	end

	local value = self:getStorageValue(mission.storageId)
	local state = value
	if mission.ignoreendvalue and value > table.maxn(mission.states) then
		state = table.maxn(mission.states)
	end

	local estado = mission.states[state]
	if type(estado) == "string" then
		return Idioma.saida(estado, self)
	end
	if overrides and overrides.states and overrides.states[state] then
		return tostring(overrides.states[state](self))
	end
	return avaliar_texto(estado, self)
end
