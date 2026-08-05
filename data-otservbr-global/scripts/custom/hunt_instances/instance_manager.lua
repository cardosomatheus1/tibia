-- Execucao: cria, teleporta, encerra.
-- Spec: docs/spec_hunt_instanciada_v2.md secoes 9.7 e 11.

InstanceManager = InstanceManager or {}

local proximoRunId = 1

local function coord(p)
	if not p then
		return "nil"
	end
	return string.format("%d,%d,%d", p.x, p.y, p.z)
end

--- Devolve o jogador ao mapa global, insistindo ate conseguir.
--
-- O teleportTo devolve false quando o tile de destino nao serve -- ocupado por
-- outra criatura, virou intransponivel -- e so registra isso em nivel DEBUG
-- (creature_functions.cpp:869). Como o sair() ignorava esse retorno, uma volta
-- que falhava deixava o jogador DENTRO; logo em seguida a limpeza varria a
-- zona e o despejava no retornoGlobal. O jogador saia da instancia, sim, mas
-- longe de onde tinha entrado, e nada no log dizia por que.
--
-- Ordem das tentativas: o ponto exato, depois empurrando para um tile livre ao
-- lado, e so entao os pontos fixos do template.
local function devolver(player, destino, template, motivo)
	if destino and player:teleportTo(destino) then
		return true
	end
	if destino and player:teleportTo(destino, true) then
		logger.warn("[hunt-instance] {} voltou empurrado para perto de {} ({})",
			player:getName(), coord(destino), motivo or "sem motivo")
		return true
	end
	local reservas = { template.retornoGlobal, template.retornoEmergencia }
	for _, alternativa in ipairs(reservas) do
		if alternativa and player:teleportTo(alternativa, true) then
			logger.error("[hunt-instance] {} nao coube em {}; devolvido a {} ({})",
				player:getName(), coord(destino), coord(alternativa),
				motivo or "sem motivo")
			return true
		end
	end
	logger.error("[hunt-instance] {} NAO saiu da instancia: nenhum destino "
		.. "aceitou o teleporte (queria {})", player:getName(), coord(destino))
	return false
end

--- Teleporte atomico (secao 9.7): se qualquer um falhar, devolve todos.
local function teleportarTodos(slot, membros)
	local feitos = {}
	for i, player in ipairs(membros) do
		local rel = slot.template.entradasRelativas[i]
			or slot.template.entradasRelativas[1]
		local destino = InstancePool.posicaoReal(slot, rel)
		local antes = player:getPosition()
		if player:teleportTo(destino) then
			feitos[#feitos + 1] = { player = player, antes = antes }
			destino:sendMagicEffect(CONST_ME_TELEPORT)
		else
			-- desfaz os que ja foram
			for _, f in ipairs(feitos) do
				f.player:teleportTo(f.antes)
			end
			return false
		end
	end
	return true
end

-- ---------------------------------------------------------------- duracao
--
-- Quanto falta, avisado com antecedencia suficiente para o jogador decidir se
-- ainda comeca uma parada ou se ja volta. 15 minutos da tempo de terminar o
-- que esta fazendo; 1 minuto e' so para ninguem ser teleportado no meio de um
-- ataque sem entender por que.
local AVISOS_MINUTOS = { 15, 5, 1 }

local function frase(minutos)
	return minutos == 1 and "1 minuto" or (minutos .. " minutos")
end

local function avisarMembros(run, texto)
	for guid in pairs(run.membros) do
		local p = Player(guid)
		if p then
			p:sendTextMessage(MESSAGE_EVENT_ADVANCE, texto)
		end
	end
end

--- Marca os avisos e o encerramento por tempo.
--
-- Todo callback confere `slot.run == run` antes de agir. Sem isso um timer da
-- execucao anterior encontraria o slot ja reocupado e avisaria -- ou pior,
-- encerraria -- a hunt de quem acabou de entrar. E' a mesma armadilha que o
-- instance_spawns documenta: evento em voo nao sabe que o mundo mudou.
local function agendarFim(run, duracaoSegundos)
	local total = duracaoSegundos
		or (run.template.duracaoMaximaMinutos or 180) * 60
	run.fim = run.inicio + total
	run.eventos = {}

	for _, restantes in ipairs(AVISOS_MINUTOS) do
		local atraso = (total - restantes * 60) * 1000
		if atraso > 0 then
			run.eventos[#run.eventos + 1] = addEvent(function()
				if run.slot.run == run then
					avisarMembros(run, string.format(
						"A instancia sera encerrada em %s.", frase(restantes)))
				end
			end, atraso)
		end
	end

	run.eventos[#run.eventos + 1] = addEvent(function()
		if run.slot.run == run then
			InstanceManager.encerrarPorTempo(run)
		end
	end, total * 1000)
end

--- Cancela os timers de uma execucao que acabou antes da hora.
-- Sem isto cada execucao curta deixaria quatro eventos em voo, e o slot vive
-- para sempre: em algumas horas de uso seriam centenas de callbacks orfaos.
local function cancelarFim(run)
	for _, id in ipairs(run.eventos or {}) do
		stopEvent(id)
	end
	run.eventos = nil
end

--- Fim por tempo: todo mundo sai como se tivesse usado a porta.
-- Passa pelo sair() de proposito -- e' ele que devolve ao ponto de entrada e
-- aplica o cooldown, e o tempo esgotado nao e' motivo para abrir excecao.
function InstanceManager.encerrarPorTempo(run)
	avisarMembros(run, "O tempo da instancia acabou.")

	local guids = {}
	for guid in pairs(run.membros) do
		guids[#guids + 1] = guid
	end
	for _, guid in ipairs(guids) do
		local p = Player(guid)
		if p then
			InstanceManager.sair(p, "tempo esgotado")
		else
			-- offline nao tem quem teleportar, mas a vaga tem de ser liberada
			run.membros[guid] = nil
		end
	end

	-- se todos estavam offline, nenhum sair() rodou e o encerrar nao veio
	if run.slot.run == run then
		InstanceManager.encerrar(run, "tempo esgotado")
	end
end

--- Abre uma execucao. `duracaoSegundos` so existe para o auto-teste: sem
-- encurtar o prazo, o caminho do encerramento por tempo so rodaria depois de
-- alguem jogar 3 horas de verdade -- ou seja, nunca antes de ir para producao.
function InstanceManager.criarExecucao(template, slot, membros, duracaoSegundos)
	local run = {
		id = proximoRunId,
		template = template,
		slot = slot,
		membros = {},          -- guid -> { nome, retorno }
		saidos = {},           -- quem saiu e ainda pode voltar (ver voltar())
		inicio = os.time(),
	}
	proximoRunId = proximoRunId + 1

	-- Snapshot: quem entrou esta autorizado, e mais ninguem (secao 9.6).
	-- Depois disso a execucao nao depende da composicao atual da party.
	for _, player in ipairs(membros) do
		run.membros[player:getGuid()] = {
			nome = player:getName(),
			retorno = player:getPosition(),
		}
	end

	if not teleportarTodos(slot, membros) then
		logger.error("[hunt-instance] run {}: teleporte falhou, abortada", run.id)
		return false
	end

	slot.run = run
	InstanceSpawns.iniciar(slot)
	agendarFim(run, duracaoSegundos)

	-- em horas quando passa de uma; abaixo disso "0.0 horas" nao diz nada
	local segundos = run.fim - run.inicio
	local prazo
	if segundos >= 3600 then
		prazo = string.format("%g horas", segundos / 3600)
	elseif segundos >= 60 then
		prazo = string.format("%d minutos", math.floor(segundos / 60))
	else
		prazo = string.format("%d segundos", segundos)
	end
	for _, player in ipairs(membros) do
		player:sendTextMessage(MESSAGE_EVENT_ADVANCE, string.format(
			"Voce tem %s nesta instancia. Havera aviso aos 15, 5 e 1 "
			.. "minuto do fim.", prazo))
		player:sendTextMessage(MESSAGE_EVENT_ADVANCE,
			"Itens deixados no chao serao removidos quando a instancia encerrar.")
	end

	logger.info("[hunt-instance] run {} aberta no slot {} com {} jogador(es)",
		run.id, slot.indice, #membros)
	return true
end

--- Tira um jogador da execucao. Motivo entra na telemetria.
--- Devolve ao mapa global quem esta dentro de um slot sem execucao valida.
-- Acontece sempre que o servidor reinicia: o estado do slot e' em memoria, mas
-- a posicao do jogador esta no banco. Sem isto ele fica PRESO -- a fronteira
-- barra o passo, o dialogo abre, e o sair() falha em silencio.
function InstanceManager.resgatar(player, slot, motivo)
	local tpl = slot.template
	-- a fronteira bloqueia toda saida; sem autorizar, ela bloqueia esta aqui
	if InstanceFronteiras then
		InstanceFronteiras.autorizarSaida(player)
		InstanceFronteiras.esquecer(player)
	end
	-- aqui nao ha ponto de entrada guardado (o estado do slot se perdeu no
	-- restart), entao o destino e' o retorno fixo do template mesmo
	devolver(player, tpl.retornoGlobal, tpl, motivo or "resgate")
	player:sendTextMessage(MESSAGE_EVENT_ADVANCE,
		"Voce foi devolvido ao mapa global.")
	logger.info("[hunt-instance] {} resgatado do slot {} ({})",
		player:getName(), slot.indice, motivo or "sem execucao")
	return true
end

function InstanceManager.sair(player, motivo)
	local slot = InstancePool.slotDaPosicao(player:getPosition())
	if not slot then
		return false
	end
	-- sem execucao (restart, teleporte de GM): resgata em vez de falhar calado
	if not slot.run then
		return InstanceManager.resgatar(player, slot, "slot sem execucao")
	end
	local run = slot.run
	local guid = player:getGuid()
	local dados = run.membros[guid]
	if not dados then
		return InstanceManager.resgatar(player, slot, "nao e membro da execucao")
	end

	run.membros[guid] = nil
	run.saidos[guid] = dados      -- pode voltar enquanto a execucao viver
	if InstanceFronteiras then
		InstanceFronteiras.autorizarSaida(player)
		InstanceFronteiras.esquecer(player)
	end
	-- de volta ao ponto EXATO de onde entrou -- em geral na frente do obelisco
	devolver(player, dados.retorno, run.template, motivo)

	-- Cooldown vale em TODA saida, inclusive queda de conexao (secao 14.2):
	-- se cair fora fosse de graca, derrubar o cliente viraria o caminho do
	-- exploit que o cooldown existe para fechar.
	InstanceEligibility.aplicarCooldown(player, run.template)

	local restantes = 0
	for _ in pairs(run.membros) do
		restantes = restantes + 1
	end
	logger.info("[hunt-instance] run {}: {} saiu ({}), restam {}",
		run.id, dados.nome, motivo or "sem motivo", restantes)

	if restantes == 0 then
		InstanceManager.encerrar(run, "ultimo participante saiu")
	end
	return true
end

function InstanceManager.encerrar(run, motivo)
	local slot = run.slot
	-- antes de qualquer coisa: timer que sobrevive ao fim encontra o slot ja
	-- reocupado e age sobre a execucao errada
	cancelarFim(run)
	-- limpeza de verdade: sem ela o proximo grupo encontra o loot deste
	InstanceCleaner.limpar(slot, motivo)
	logger.info("[hunt-instance] run {} encerrada apos {} min: {}",
		run.id, math.floor((os.time() - run.inicio) / 60), motivo)
end

--- Minutos que faltam para o fim, ou nil se a execucao nao tem prazo.
function InstanceManager.minutosRestantes(run)
	if not run or not run.fim then
		return nil
	end
	return math.max(0, math.ceil((run.fim - os.time()) / 60))
end

-- -------------------------------------------------------------- reentrada
--
-- Quem sai de uma execucao que CONTINUA rodando pode voltar para ela. Nao e'
-- uma excecao ao cooldown, e' outra coisa: o cooldown existe para fechar o
-- abuso de entrar, matar o respawn da entrada, sair e entrar num slot LIMPO
-- (secao 12.3). Voltar para a mesma execucao nao limpa nada -- o que ja morreu
-- continua morto -- entao nao ha o que abusar.
--
-- A condicao e' uma so: a execucao tem de estar viva. Como ela encerra quando
-- o ultimo membro sai, isso equivale a "ainda tem alguem do grupo la dentro".
-- Quem sai sozinho fecha a instancia e nao tem para onde voltar.
--
-- Vale inclusive para quem morreu: decisao consciente, a punicao da morte
-- passa a ser o caminho de volta e nao a perda da hunt.

--- Execucao viva a que este jogador pode voltar, ou nil.
function InstanceManager.execucaoParaVoltar(player, template)
	local guid = player:getGuid()
	for _, slot in ipairs(InstancePool.todos(template)) do
		local run = slot.run
		if run and run.saidos and run.saidos[guid] then
			-- so faz sentido voltar se sobrou alguem dentro; sem isso a
			-- execucao ja teria encerrado, mas a checagem e' barata
			for _ in pairs(run.membros) do
				return run, slot
			end
		end
	end
	return nil
end

--- Recoloca o jogador numa execucao de que ele ja fez parte.
function InstanceManager.voltar(player, template)
	local run, slot = InstanceManager.execucaoParaVoltar(player, template)
	if not run then
		return false, "Nao ha instancia em andamento para voltar."
	end

	local dentro = 0
	for _ in pairs(run.membros) do
		dentro = dentro + 1
	end
	if dentro >= (run.template.maximoMembros or 5) then
		return false, "A instancia esta cheia."
	end

	local guid = player:getGuid()
	local dados = run.saidos[guid]
	-- o ponto de volta passa a ser onde ele esta AGORA, que e' onde clicou
	dados.retorno = player:getPosition()

	local destino = InstancePool.posicaoReal(slot,
		run.template.entradasRelativas[1])
	if not player:teleportTo(destino) and not player:teleportTo(destino, true) then
		return false, "Nao foi possivel entrar agora."
	end
	destino:sendMagicEffect(CONST_ME_TELEPORT)

	run.saidos[guid] = nil
	run.membros[guid] = dados

	-- Confirmacao para QUEM VOLTA. So os que estavam dentro eram avisados, e
	-- quem voltava nao via linha nenhuma no chat -- o teste em jogo terminou
	-- com "nao apareceu isso", mesmo tendo funcionado.
	player:sendTextMessage(MESSAGE_EVENT_ADVANCE, string.format(
		"Voce voltou para a instancia. Restam %d minuto(s) de hunt.",
		InstanceManager.minutosRestantes(run) or 0))

	for outro in pairs(run.membros) do
		if outro ~= guid then
			local p = Player(outro)
			if p then
				p:sendTextMessage(MESSAGE_EVENT_ADVANCE,
					dados.nome .. " voltou para a instancia.")
			end
		end
	end
	logger.info("[hunt-instance] run {}: {} voltou, agora {} dentro",
		run.id, dados.nome, dentro + 1)
	return true
end

--- Execucao em que o jogador esta, ou nil. Derivada da POSICAO -- nao ha
-- storage por criatura, e derivar evita ter de marcar cada um (secao 13.3).
function InstanceManager.runDoJogador(player)
	local slot = InstancePool.slotDaPosicao(player:getPosition())
	if slot and slot.run and slot.run.membros[player:getGuid()] then
		return slot.run, slot
	end
	return nil
end
