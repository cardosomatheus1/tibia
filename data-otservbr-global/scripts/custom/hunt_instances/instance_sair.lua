-- /sairinstancia -- saida manual da instancia.
--
-- A saida automatica (andar ate a borda da hunt, confirmar no dialogo) e a
-- Etapa 5, secao 11.0. Ate ela existir, o jogador que entra fica preso: o
-- InstanceManager.sair() ja faz o trabalho todo, mas nada o chamava.
--
-- Aplica cooldown igual a qualquer outra saida (secao 14.2): se sair por aqui
-- fosse de graca, viraria o caminho do exploit que o cooldown existe pra fechar.

local tk = TalkAction("/sairinstancia")

function tk.onSay(player)
	local slot = InstancePool.slotDaPosicao(player:getPosition())
	if not slot then
		player:sendTextMessage(MESSAGE_EVENT_ADVANCE,
			"Voce nao esta dentro de uma instancia.")
		return true
	end

	if InstanceManager.sair(player, "saida manual") then
		player:sendTextMessage(MESSAGE_EVENT_ADVANCE,
			"Voce saiu da instancia.")
		return true
	end

	-- dentro da area mas sem execucao registrada (instancia orfa apos restart,
	-- ou entrada por teleporte de GM): manda pro retorno global mesmo assim
	local tpl = slot.template
	player:teleportTo(tpl.retornoGlobal or tpl.retornoEmergencia)
	player:sendTextMessage(MESSAGE_EVENT_ADVANCE,
		"Voce foi devolvido ao mapa global.")
	return true
end

tk:separator(" ")
tk:groupType("normal")
tk:register()
