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

function InstanceManager.criarExecucao(template, slot, membros)
	local run = {
		id = proximoRunId,
		template = template,
		slot = slot,
		membros = {},          -- guid -> { nome, retorno }
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

	for _, player in ipairs(membros) do
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
	-- limpeza de verdade: sem ela o proximo grupo encontra o loot deste
	InstanceCleaner.limpar(slot, motivo)
	logger.info("[hunt-instance] run {} encerrada: {}", run.id, motivo)
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
