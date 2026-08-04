-- /pos -- mostra a posicao do jogador e o que ha no tile.
-- Auxiliar de desenvolvimento: nao ha talkaction de posicao no datapack, e
-- toda escolha de coordenada (seletor, tiles de consentimento, entrada da
-- instancia) depende de saber onde se esta.

local tk = TalkAction("/pos")

function tk.onSay(player)
	if player:getGroup():getId() < GROUP_TYPE_GOD then
		return true
	end

	local pos = player:getPosition()
	local texto = string.format("Position(%d, %d, %d)", pos.x, pos.y, pos.z)
	player:sendTextMessage(MESSAGE_EVENT_ADVANCE, texto)
	logger.info("[pos] {} em {}", player:getName(), texto)

	local tile = Tile(pos)
	if tile then
		local chao = tile:getGround()
		local ids = {}
		for _, item in ipairs(tile:getItems() or {}) do
			ids[#ids + 1] = tostring(item:getId())
		end
		player:sendTextMessage(MESSAGE_EVENT_ADVANCE, string.format(
			"chao=%s itens=[%s]",
			chao and chao:getId() or "nenhum",
			table.concat(ids, ", ")))
	end

	-- o que ha em volta, para achar buraco/escada perto
	for dx = -1, 1 do
		for dy = -1, 1 do
			if dx ~= 0 or dy ~= 0 then
				local t = Tile(Position(pos.x + dx, pos.y + dy, pos.z))
				local g = t and t:getGround()
				if g then
					local n = ItemType(g:getId()):getName()
					if n:lower():find("hole") or n:lower():find("stair")
						or n:lower():find("ladder") or n:lower():find("ramp") then
						player:sendTextMessage(MESSAGE_EVENT_ADVANCE,
							string.format("acesso vizinho: %s em (%d,%d,%d)",
								n, pos.x + dx, pos.y + dy, pos.z))
					end
				end
			end
		end
	end
	return true
end

tk:separator(" ")
tk:groupType("god")
tk:register()
