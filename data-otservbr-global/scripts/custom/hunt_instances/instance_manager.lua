-- Execucao: cria, teleporta, encerra.
-- Spec: docs/spec_hunt_instanciada_v2.md secoes 9.7 e 11.

InstanceManager = InstanceManager or {}

local proximoRunId = 1

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
function InstanceManager.sair(player, motivo)
	local slot = InstancePool.slotDaPosicao(player:getPosition())
	if not slot or not slot.run then
		return false
	end
	local run = slot.run
	local guid = player:getGuid()
	local dados = run.membros[guid]
	if not dados then
		return false
	end

	run.membros[guid] = nil
	player:teleportTo(dados.retorno or run.template.retornoEmergencia)

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
	InstanceSpawns.parar(slot)
	slot.run = nil
	InstancePool.liberar(slot, motivo)
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
