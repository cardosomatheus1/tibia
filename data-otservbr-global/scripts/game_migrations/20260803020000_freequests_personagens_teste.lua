-- Aplica de uma vez as ~362 storages do freequests.lua (acesso de area) nos
-- personagens de teste. O sistema original faz isso via addEvent a cada
-- 500ms (5 storages por vez), o que exige o personagem ficar uns 36s
-- online sem cair - em teste real só 3 foram aplicadas porque a conexao
-- nao durou o suficiente. Aqui aplica tudo de forma sincrona e marca
-- Storage.FreeQuests com o stage atual, entao o hook de login normal
-- (freequests.lua) ve que ja esta completo e nao repete o processo.

local OWNERS = { "Gabriel", "Andre", "Matheus" }
local VOCACOES = { "Sorcerer", "Druid", "Paladin", "Knight", "Monk" }

local migration = Migration("20260803020000_freequests_personagens_teste")

function migration:onExecute()
	local stage = configManager.getNumber(configKeys.FREE_QUEST_STAGE)

	for _, dono in ipairs(OWNERS) do
		for _, voc in ipairs(VOCACOES) do
			local nome = dono .. " " .. voc
			local player = Game.getOfflinePlayer(nome)
			if not player then
				logger.warn("[freequests_personagens_teste] '{}' nao encontrado, pulando.", nome)
			else
				local aplicados = 0
				for _, questData in ipairs(FreeQuestsTable) do
					if questData.storage and player:getStorageValue(questData.storage) ~= questData.storageValue then
						player:setStorageValue(questData.storage, questData.storageValue)
						aplicados = aplicados + 1
					end
				end

				player:setStorageValue(Storage.FreeQuests, stage)
				player:addOutfit(251, 0)
				player:addOutfit(252, 0)
				player:save()

				logger.info(
					"[freequests_personagens_teste] '{}' atualizado: {} storages de {} aplicadas.",
					nome, aplicados, #FreeQuestsTable
				)
			end
		end
	end
end

migration:register()
