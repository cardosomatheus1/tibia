-- Resgate no login. Spec secao 14.4 e 6.3.
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
	player:teleportTo(tpl.retornoGlobal or tpl.retornoEmergencia)
	player:sendTextMessage(MESSAGE_EVENT_ADVANCE,
		"A instancia em que voce estava nao existe mais. "
		.. "Voce foi devolvido ao mapa global.")
	logger.info("[hunt-instance] {} logou dentro do slot {} e foi devolvido",
		player:getName(), slot.indice)

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
	return true
end

vincular:register()
