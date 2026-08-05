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

-- ------------------------------------------------------- fim por tempo
--
-- O prazo de verdade e' de 3 horas, entao o caminho do encerramento por tempo
-- so rodaria depois de alguem jogar 3 horas -- ou seja, nunca antes de ir para
-- producao. Este modo abre uma execucao com prazo curto e observa o fim
-- acontecer: saida por tempo, cooldown, slot devolvido ao pool.
--
--     /testeinstancia tempo         20 s, so o encerramento
--     /testeinstancia tempo 1200    20 min, tambem os avisos
--
-- O prazo em segundos existe por causa dos AVISOS. Eles disparam a 15, 5 e 1
-- minuto do fim, entao com 20 segundos nenhum chega a rodar -- o agendamento
-- descarta atraso negativo. Com 1200 os tres acontecem, o primeiro em 5
-- minutos de espera. Era o unico pedaco da etapa 5 sem cobertura.
local function testarPrazo(player, tpl, segundos)
	local kv = KV.scoped("hunt-instance"):scoped(tpl.slug)
		:scoped(tostring(player:getAccountId()))
	kv:remove("ate")

	local livresAntes = InstancePool.disponiveis(tpl)
	local slot = InstancePool.alocar(tpl)
	if not slot then
		passou(player, "alocou slot", false, "pool cheio")
		return
	end

	local origem = player:getPosition()
	passou(player, "execucao criada com prazo curto",
		InstanceManager.criarExecucao(tpl, slot, { player }, segundos))
	local run = slot.run
	passou(player, string.format("prazo de %d s marcado", segundos),
		run and run.fim and run.fim - run.inicio == segundos,
		run and run.fim and (run.fim - run.inicio .. " s") or "sem prazo")

	-- diz QUANDO cada aviso deve chegar, para dar para conferir na hora em vez
	-- de esperar sem saber o que esperar
	local quando = {}
	for _, m in ipairs({ 15, 5, 1 }) do
		if segundos - m * 60 > 0 then
			quando[#quando + 1] = string.format("%s min de aviso em %d s",
				m, segundos - m * 60)
		end
	end
	player:sendTextMessage(MESSAGE_EVENT_ADVANCE, string.format(
		"Aguardando o prazo estourar (%d s). %s", segundos,
		#quando > 0 and table.concat(quando, "; ")
			or "Curto demais para os avisos; so o encerramento."))

	-- prazo mais folga para a limpeza terminar
	addEvent(function()
		local q = Player(player:getId())
		if not q then return end
		passou(q, "prazo encerrou a execucao",
			slot.run == nil,
			slot.run and "slot ainda ocupado" or "")
		passou(q, "tirou o jogador da instancia",
			InstancePool.slotDaPosicao(q:getPosition()) == nil)
		passou(q, "devolveu ao ponto de entrada",
			q:getPosition():getDistance(origem) <= 2,
			string.format("entrou em %s, voltou em %s",
				coord(origem), coord(q:getPosition())))
		passou(q, "cooldown aplicado pelo fim do prazo",
			InstanceEligibility.cooldownRestante(q, tpl) > 0,
			"zero -- fim por tempo saiu de graca")
		passou(q, "pool voltou ao normal",
			InstancePool.disponiveis(tpl) == livresAntes)
		passou(q, "zona esvaziou",
			#slot.zona:getMonsters() == 0,
			#slot.zona:getMonsters() .. " sobraram")
		passou(q, "timers do prazo cancelados",
			run and run.eventos == nil,
			run and run.eventos and (#run.eventos .. " em voo") or "sem run")
		kv:remove("ate")
		q:sendTextMessage(MESSAGE_EVENT_ADVANCE, "=== fim do teste de prazo ===")
	end, (segundos + 6) * 1000)
end

local tk = TalkAction("/testeinstancia")

function tk.onSay(player, words, param)
	if player:getGroup():getId() < GROUP_TYPE_GOD then
		return true
	end

	if param and param:lower():find("tempo") then
		-- 10 s e' o minimo que da para observar; 2 h e' teto de sanidade, para
		-- um digito a mais nao prender um slot pelo resto do dia
		local segundos = math.max(10, math.min(7200,
			tonumber(param:match("(%d+)")) or 20))
		testarPrazo(player, HuntInstances.thaisCyclops, segundos)
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

	local run = slot.run
	local restam = run and InstanceManager.minutosRestantes(run)
	local previsto = tpl.duracaoMaximaMinutos
	passou(player, "prazo marcado",
		restam and restam >= previsto - 1 and restam <= previsto,
		string.format("previa %d min, marcou %s", previsto, tostring(restam)))
	-- 3 avisos + o encerramento. Se este numero mudar sem querer, algum aviso
	-- deixou de ser agendado e ninguem descobriria ate a hunt fechar calada.
	passou(player, "timers do prazo agendados",
		run and run.eventos and #run.eventos == 4,
		run and run.eventos and (#run.eventos .. " timers") or "nenhum")

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
			-- timer em voo depois do fim acha o slot ja reocupado e encerra a
			-- hunt de quem acabou de entrar
			passou(q, "timers do prazo cancelados",
				run and run.eventos == nil,
				run and run.eventos and (#run.eventos .. " ficaram em voo")
					or "sem run")
			-- reentrada exige alguem do grupo la dentro. Saindo sozinho, a
			-- execucao encerra e nao ha para onde voltar -- se isto passar a
			-- oferecer volta, o jogador cairia num slot ja limpo e vazio.
			passou(q, "sem volta depois de sair sozinho",
				InstanceManager.execucaoParaVoltar(q, tpl) == nil,
				"ofereceu voltar para execucao encerrada")

			kv:remove("ate")
			q:sendTextMessage(MESSAGE_EVENT_ADVANCE, "=== fim do auto-teste ===")
		end, 3000)
	end, 5000)

	return true
end

tk:separator(" ")
tk:groupType("god")
tk:register()
