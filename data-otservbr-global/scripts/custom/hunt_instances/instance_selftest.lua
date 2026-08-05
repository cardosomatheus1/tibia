-- Auto-teste do ciclo entrar/sair. Spec: docs/spec_hunt_instanciada_v2.md.
--
-- Existe como talkaction porque Player(nome) so resolve jogador ONLINE: sem um
-- personagem logado nao ha como exercitar teleporte, snapshot, cooldown na
-- saida e retorno. Um GlobalEvent no boot nunca alcanca esse caminho.
--
-- Restrito a GOD e opt-in: teleporta quem executa para dentro de uma instancia
-- e traz de volta. Nao deixar habilitado sem motivo.
--
--     /testeinstancia

-- Position nao tem __tostring: um tostring() nele imprime "table: 0x...", e foi
-- assim que a falha do retorno a origem apareceu -- sem dizer PARA ONDE o
-- jogador tinha ido, que era exatamente o dado que faltava.
local function coord(p)
	if not p then
		return "nil"
	end
	return string.format("%d,%d,%d", p.x, p.y, p.z)
end

local function passou(player, nome, ok, detalhe)
	local texto = (ok and "ok    " or "FALHA ") .. nome
		.. (ok and "" or (" -- " .. tostring(detalhe or "")))
	player:sendTextMessage(MESSAGE_EVENT_ADVANCE, texto)
	if ok then
		logger.info("[SELFTEST] {}", texto)
	else
		logger.error("[SELFTEST] {}", texto)
	end
end

local tk = TalkAction("/testeinstancia")

function tk.onSay(player)
	if player:getGroup():getId() < GROUP_TYPE_GOD then
		return true
	end

	local tpl = HuntInstances.thaisCyclops
	local kv = KV.scoped("hunt-instance"):scoped(tpl.slug)
		:scoped(tostring(player:getAccountId()))
	kv:remove("ate")

	local origem = player:getPosition()
	passou(player, "cooldown comeca zerado",
		InstanceEligibility.cooldownRestante(player, tpl) == 0)
	passou(player, "jogador limpo pode entrar",
		InstanceEligibility.podeEntrar(player, tpl),
		InstanceEligibility.motivoBloqueio(player, tpl))

	local livresAntes = InstancePool.disponiveis(tpl)
	local slot = InstancePool.alocar(tpl)
	if not slot then
		passou(player, "alocou slot", false, "pool cheio")
		return true
	end

	passou(player, "execucao criada",
		InstanceManager.criarExecucao(tpl, slot, { player }))
	passou(player, "pool diminuiu",
		InstancePool.disponiveis(tpl) == livresAntes - 1)

	addEvent(function()
		local p = Player(player:getId())
		if not p then return end

		local dentro = InstancePool.slotDaPosicao(p:getPosition())
		passou(p, "jogador esta dentro do slot",
			dentro and dentro.indice == slot.indice,
			dentro and ("slot " .. dentro.indice) or "fora")
		passou(p, "run localizada pela posicao",
			InstanceManager.runDoJogador(p) ~= nil)
		passou(p, "monstros nasceram",
			#slot.zona:getMonsters() > 100,
			#slot.zona:getMonsters() .. " monstros")

		InstanceManager.sair(p, "selftest")

		-- Onde ele caiu, medido AGORA. Medir depois do intervalo dava falso
		-- negativo: sao 3 segundos com o jogador solto no mapa global, e um
		-- passo dele bastava para "nao voltou a origem". O que se quer provar
		-- e' que o sair() devolve ao ponto de entrada, nao que o jogador ficou
		-- imovel esperando o teste terminar.
		local ondeCaiu = p:getPosition()
		local distancia = ondeCaiu:getDistance(origem)

		addEvent(function()
			local q = Player(player:getId())
			if not q then return end
			passou(q, "voltou para fora da instancia",
				InstancePool.slotDaPosicao(ondeCaiu) == nil)
			passou(q, "voltou para a posicao de origem",
				distancia <= 2,
				string.format("entrou em %s, voltou em %s (distancia %d)",
					coord(origem), coord(ondeCaiu), distancia))
			passou(q, "cooldown aplicado na saida",
				InstanceEligibility.cooldownRestante(q, tpl) > 0,
				"zero -- exploit de sair e voltar")
			passou(q, "bloqueado por cooldown agora",
				not InstanceEligibility.podeEntrar(q, tpl))
			passou(q, "pool voltou ao normal",
				InstancePool.disponiveis(tpl) == livresAntes)
			passou(q, "zona esvaziou",
				#slot.zona:getMonsters() == 0,
				#slot.zona:getMonsters() .. " sobraram")

			kv:remove("ate")
			q:sendTextMessage(MESSAGE_EVENT_ADVANCE, "=== fim do auto-teste ===")
		end, 3000)
	end, 5000)

	return true
end

tk:separator(" ")
tk:groupType("god")
tk:register()
