-- Troca o idioma das conversas com NPC, por personagem.
--
-- A escolha fica no KV do jogador, entao acompanha o personagem e nao
-- depende de client nenhum. O client-modules/idioma/ so manda este mesmo
-- comando ao clicar na bandeirinha.
local idioma = TalkAction("!idioma", "!language")

local function listar(player)
	local partes = {}
	for _, i in ipairs(Idioma.lista()) do
		table.insert(partes, i.codigo .. " (" .. i.nome .. ")")
	end
	table.sort(partes)
	player:sendTextMessage(MESSAGE_LOOK, "Idiomas: " .. table.concat(partes, ", ")
		.. ". Use !idioma <codigo> para trocar.")
end

function idioma.onSay(player, words, param)
	param = param:trimSpace():lower()

	if param == "" then
		local atual = Idioma.do_jogador(player)
		local nome = atual == "en" and "English" or Idioma.dicionarios[atual].nome
		player:sendTextMessage(MESSAGE_LOOK, "Idioma atual: " .. nome .. " (" .. atual .. ").")
		listar(player)
		return true
	end

	-- aceita tanto o codigo quanto o nome do pais, que e o que a
	-- bandeirinha do client manda
	local apelidos = { br = "pt", ["pt-br"] = "pt", us = "en", usa = "en", eua = "en" }
	param = apelidos[param] or param

	if not Idioma.existe(param) then
		player:sendCancelMessage("Idioma desconhecido: " .. param .. ".")
		listar(player)
		return true
	end

	Idioma.definir(player, param)
	if param == "en" then
		player:sendTextMessage(MESSAGE_LOOK, "NPCs will now talk to you in English.")
	else
		player:sendTextMessage(MESSAGE_LOOK, "Os NPCs agora falam com voce em "
			.. Idioma.dicionarios[param].nome .. ".")
	end
	player:getPosition():sendMagicEffect(CONST_ME_MAGIC_BLUE)
	return true
end

idioma:separator(" ")
idioma:groupType("normal")
idioma:register()
