-- Conexao: saida no logout e resgate no login. Spec secao 14.1, 14.2 e 6.3.
--
-- O estado do slot vive em memoria e NAO sobrevive a restart, mas a posicao do
-- jogador esta no banco. Sem este handler, quem estava dentro de uma instancia
-- quando o servidor reiniciou volta preso: a fronteira barra o passo e nao ha
-- execucao para o sair() encerrar.
--
-- Cobre tres casos com o MESMO teste, que foi o argumento para nao marcar o
-- piso como NOLOGOUT (secao 6.3):
--
--   logout voluntario dentro da instancia
--   queda de conexao
--   instancia orfa depois de restart
--
-- A regra e' incondicional (secao 14.1): logou dentro, nasce fora. Nao existe
-- reconectar para dentro -- essa maquina de estado foi removida de proposito.

local ev = CreatureEvent("HuntInstanceLogin")

function ev.onLogin(player)
	local slot = InstancePool and InstancePool.slotDaPosicao(player:getPosition())
	if not slot then
		return true
	end

	local tpl = slot.template
	if InstanceFronteiras then
		InstanceFronteiras.autorizarSaida(player)
	end
	player:teleportTo(tpl.retornoGlobal or tpl.retornoEmergencia)

	-- Logar dentro continua proibido (secao 14.1), mas se a execucao ainda
	-- estiver rodando ele pode voltar pelo obelisco. Dizer "nao existe mais"
	-- nesse caso seria falso e o mandaria abrir uma instancia nova, vazia.
	local podeVoltar = InstanceManager
		and InstanceManager.execucaoParaVoltar(player, tpl) ~= nil
	player:sendTextMessage(MESSAGE_EVENT_ADVANCE, podeVoltar
		and "Voce foi devolvido ao mapa global. Sua instancia continua em "
			.. "andamento: use o obelisco para voltar."
		or "A instancia em que voce estava nao existe mais. "
			.. "Voce foi devolvido ao mapa global.")
	logger.info("[hunt-instance] {} logou dentro do slot {} e foi devolvido "
		.. "(pode voltar: {})", player:getName(), slot.indice, tostring(podeVoltar))

	if InstanceFronteiras then
		InstanceFronteiras.esquecer(player)
	end
	return true
end

ev:register()

-- O onLogin so dispara para eventos registrados no jogador. Um creaturevent
-- global precisa ser vinculado no login padrao do datapack, entao registra
-- tambem por aqui.
local vincular = CreatureEvent("HuntInstanceLoginBind")

function vincular.onLogin(player)
	player:registerEvent("HuntInstanceLogin")
	player:registerEvent("HuntInstanceLogout")
	return true
end

vincular:register()

-- Saida por desconexao (secao 14.2).
--
-- Sem isto o membro desconectado ficava na execucao PARA SEMPRE: segurava o
-- slot aberto mesmo depois de todos os outros sairem, e nao recebia o
-- cooldown que a secao 14.2 exige em toda saida -- derrubar o cliente virava
-- justamente o caminho barato que o cooldown existe para fechar.
--
-- Ele entra em `saidos`, entao pode voltar pelo obelisco enquanto sobrar
-- alguem do grupo dentro. Uma queda de conexao nao deve custar a hunt.
local desconectar = CreatureEvent("HuntInstanceLogout")

function desconectar.onLogout(player)
	local slot = InstancePool and InstancePool.slotDaPosicao(player:getPosition())
	if not slot or not slot.run then
		return true
	end
	local run = slot.run
	local guid = player:getGuid()
	local dados = run.membros[guid]
	if not dados then
		return true
	end

	run.membros[guid] = nil
	run.saidos[guid] = dados
	InstanceEligibility.aplicarCooldown(player, run.template)
	if InstanceFronteiras then
		InstanceFronteiras.esquecer(player)
	end

	local restantes = 0
	for _ in pairs(run.membros) do
		restantes = restantes + 1
	end
	logger.info("[hunt-instance] run {}: {} caiu/deslogou, restam {}",
		run.id, dados.nome, restantes)

	-- O corpo do jogador nao fica no mapa ao deslogar, entao nao ha nada a
	-- preservar: se era o ultimo, a execucao encerra como em qualquer saida.
	if restantes == 0 then
		InstanceManager.encerrar(run, "ultimo participante desconectou")
	end
	return true
end

desconectar:register()
