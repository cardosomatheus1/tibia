-- Ativa a expansao de charms para os personagens de teste (gabriel/andre/
-- matheus) - assim como magias/mochila/dinheiro, isso normalmente vem de
-- pontos de bestiary ganhos jogando, entao personagens criados direto no
-- banco ficam sem. Acesso de area (freequests) e resolvido via config.lua
-- (toggleFreeQuest = true), nao por migration - o proprio sistema aplica
-- os storages no login de qualquer personagem. Wheel of Destiny ja funciona
-- (level > 50, premium e vocacao promovida ja estao corretos nesses 15
-- personagens - conferido direto no player_wheel.cpp/player.cpp).

local OWNERS = { "Gabriel", "Andre", "Matheus" }
local VOCACOES = { "Sorcerer", "Druid", "Paladin", "Knight", "Monk" }

local migration = Migration("20260803010000_charms_personagens_teste")

function migration:onExecute()
	for _, dono in ipairs(OWNERS) do
		for _, voc in ipairs(VOCACOES) do
			local nome = dono .. " " .. voc
			local player = Game.getOfflinePlayer(nome)
			if not player then
				logger.warn("[charms_personagens_teste] '{}' nao encontrado, pulando.", nome)
			else
				player:charmExpansion(true)
				player:save()
				logger.info("[charms_personagens_teste] '{}' atualizado: charm expansion ativado.", nome)
			end
		end
	end
end

migration:register()
