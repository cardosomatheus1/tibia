local feature = TalkAction("!autoloot")

local validValues = {
	-- "all",
	"on",
	"off",
	-- "status" nao muda nada: so responde o estado atual. Serve para o modulo
	-- de client (modules/lootpouch) sincronizar a borda do botao (verde ligado,
	-- vermelha desligado) ao abrir a Loot Pouch. O servidor nao consegue enviar
	-- extended opcode para o client -- ele so recebe --, entao o estado viaja
	-- por mensagem de texto, que o modulo le e esconde do chat.
	"status",
}

-- Prefixo fixo para o client reconhecer a resposta sem depender de traducao
-- ou de mudanca de texto. Formato: "[LP] <temPouch> <estado>"
local MARCA_STATUS = "[LP]"

-- MESSAGE_MANA e' um dos poucos tipos que o client NAO desenha (o proprio enum
-- do servidor o marca como "no effect"). Assim o estado chega ao modulo pelo
-- onTextMessage sem aparecer para o jogador. Um tipo visivel encheria a tela de
-- "[LP] 1 1" toda vez que a pouch fosse aberta.
local TIPO_SILENCIOSO = MESSAGE_MANA

local function responderEstado(player, temPouch)
	player:sendTextMessage(TIPO_SILENCIOSO,
		string.format("%s %d %d", MARCA_STATUS, temPouch and 1 or 0,
			player:getFeature(Features.AutoLoot) or 0))
end

function feature.onSay(player, words, param)
	if not configManager.getBoolean(configKeys.AUTOLOOT) then
		return true
	end
	if configManager.getBoolean(configKeys.VIP_SYSTEM_ENABLED) and configManager.getBoolean(configKeys.VIP_AUTOLOOT_VIP_ONLY) and not player:isVip() then
		player:sendCancelMessage("You need to be VIP to use this command!")
		return true
	end

	local temPouch = player:getLootPouch() ~= nil

	-- "status" responde mesmo sem a pouch: o client precisa saber que deve
	-- mostrar o botao desligado em vez de nao mostrar nada.
	if param == "status" then
		responderEstado(player, temPouch)
		return true
	end

	-- AutoLoot e' um beneficio de quem comprou a Loot Pouch, nao de VIP.
	-- Quick Loot manual continua livre para todos: e' outro caminho de codigo
	-- (Game::playerQuickLoot) e nao passa por aqui.
	--
	-- A trava vive no Lua porque o Player::checkAutoLoot em C++ so le o KV
	-- features.autoloot; quem decide se o jogador PODE ligar esse KV e' este
	-- comando. Assim nao precisa recompilar o servidor.
	if not temPouch then
		player:sendCancelMessage("You need a Loot Pouch to use AutoLoot. You can buy one in the Store.")
		return true
	end
	if not table.contains(validValues, param) then
		local validValuesStr = table.concat(validValues, "/")
		player:sendTextMessage(MESSAGE_EVENT_ADVANCE, "Invalid param specified. Usage: !feature [" .. validValuesStr .. "]")
		return true
	end

	if param == "all" then
		player:setFeature(Features.AutoLoot, 2)
		player:sendTextMessage(MESSAGE_EVENT_ADVANCE, "AutoLoot is now enabled for all kills (including bosses).")
	elseif param == "on" then
		player:setFeature(Features.AutoLoot, 1)
		player:sendTextMessage(MESSAGE_EVENT_ADVANCE, "AutoLoot is now enabled for all regular kills (no bosses).")
	elseif param == "off" then
		player:setFeature(Features.AutoLoot, 0)
		player:sendTextMessage(MESSAGE_EVENT_ADVANCE, "AutoLoot is now disabled.")
	end

	-- eco silencioso: o modulo de client atualiza a borda a partir daqui,
	-- inclusive quando o jogador usa o comando digitado em vez do botao
	responderEstado(player, true)
	return true
end

feature:separator(" ")
feature:groupType("normal")
feature:register()
