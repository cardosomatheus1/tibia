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

		addEvent(function()
			local q = Player(player:getId())
			if not q then return end
			passou(q, "voltou para fora da instancia",
				InstancePool.slotDaPosicao(q:getPosition()) == nil)
			passou(q, "voltou para a posicao de origem",
				q:getPosition():getDistance(origem) <= 2,
				tostring(q:getPosition()))
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
