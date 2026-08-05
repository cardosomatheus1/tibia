-- Morte dentro da instancia. Spec secao 20.
--
-- A morte NAO passa pela fronteira: Creature::onDeath chama
-- afterCreatureZoneChange direto (creature.cpp:865), o hook *after*, entao o
-- veto do beforeLeave nunca e' consultado. Morrer nao trava o jogador -- isso
-- ja funcionava.
--
-- O que faltava e' o estado. Sem este handler o morto ressuscita no templo mas
-- continua contando como membro da execucao: o slot nunca esvazia sozinho, o
-- cooldown nao e' aplicado, e a vaga fica presa ate o timeout.
--
-- Regra da secao 20: so o morto deixa a instancia, os demais continuam, ele
-- nao pode retornar, e o corpo fica ate a limpeza do slot.

local ev = CreatureEvent("HuntInstanceDeath")

function ev.onDeath(creature)
	local player = creature:getPlayer()
	if not player then
		return true
	end

	local slot = InstancePool and InstancePool.slotDaPosicao(player:getPosition())
	if not slot or not slot.run then
		return true
	end

	local run = slot.run
	local guid = player:getGuid()
	if not run.membros[guid] then
		return true
	end

	-- Tira da execucao SEM teleportar: quem move o jogador e' a propria morte,
	-- que o leva ao templo. Chamar sair() aqui competiria com isso.
	local nome = run.membros[guid].nome
	run.membros[guid] = nil
	InstanceEligibility.aplicarCooldown(player, run.template)

	if InstanceFronteiras then
		InstanceFronteiras.esquecer(player)
	end

	local restantes = 0
	for _ in pairs(run.membros) do
		restantes = restantes + 1
	end
	logger.info("[hunt-instance] run {}: {} morreu, restam {}",
		run.id, nome, restantes)

	-- O corpo fica ate a limpeza do slot (secao 20), entao nao se remove nada
	-- aqui. Se era o ultimo, a execucao encerra e a limpeza leva o corpo junto.
	if restantes == 0 then
		InstanceManager.encerrar(run, "ultimo participante morreu")
	end
	return true
end

ev:register()

-- vincula ao jogador no login, junto do resgate de instancia orfa
local bind = CreatureEvent("HuntInstanceDeathBind")

function bind.onLogin(player)
	player:registerEvent("HuntInstanceDeath")
	return true
end

bind:register()
