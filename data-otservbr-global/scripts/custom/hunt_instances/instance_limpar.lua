-- /limparinstancia [n] -- forca a limpeza de um slot.
--
-- Sem argumento, limpa o slot onde o GM esta. Com numero, limpa aquele slot.
--
-- Existe porque a limpeza automatica so roda ao encerrar a execucao. Item que
-- entrou por outro caminho -- script de teste, spawn de GM, bug -- fica no chao
-- ate alguem tirar. Foi o caso: um teste largou spikes (id 2148) dentro da
-- hunt e a versao antiga do cleaner nao as removia, porque classificava
-- "nao movivel" como cenario.

local tk = TalkAction("/limparinstancia")

function tk.onSay(player, words, param)
	local tpl = HuntInstances.thaisCyclops
	local slot

	local n = tonumber(param)
	if n then
		slot = InstancePool.get(tpl, n)
		if not slot then
			player:sendTextMessage(MESSAGE_EVENT_ADVANCE,
				"Slot " .. n .. " nao existe.")
			return true
		end
	else
		slot = InstancePool.slotDaPosicao(player:getPosition())
		if not slot then
			player:sendTextMessage(MESSAGE_EVENT_ADVANCE,
				"Voce nao esta em um slot. Use /limparinstancia <numero>.")
			return true
		end
	end

	local antes = #(slot.zona:getItems() or {})
	local removidos = InstanceCleaner.limpar(slot, "limpeza manual de GM")
	local ok, m, j, s = InstanceCleaner.verificar(slot)

	player:sendTextMessage(MESSAGE_EVENT_ADVANCE, string.format(
		"Slot %d: %d itens no total, %d removidos. Sobrou: %d monstro(s), "
		.. "%d jogador(es), %d item(ns) solto(s). %s",
		slot.indice, antes, removidos, m, j, s, ok and "LIMPO" or "AINDA SUJO"))
	return true
end

tk:separator(" ")
tk:groupType("god")
tk:register()
