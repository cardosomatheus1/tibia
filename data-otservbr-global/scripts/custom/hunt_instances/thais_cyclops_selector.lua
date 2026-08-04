-- Seletor de entrada: ModalWindow com Mundo Aberto / Instancia Privada.
-- Spec: docs/spec_hunt_instanciada_v2.md secoes 9.1, 9.3 e 9.4.
--
-- A ModalWindow serve SO para a escolha do lider, que e' uma interacao unica
-- com o jogador parado no obelisco. O consentimento dos membros e' por
-- presenca em tile (secao 9.2), porque andar invalida toda janela aberta
-- (player.cpp:12173) e a resposta e' descartada em silencio.

-- A ordem de carga dos scripts NAO e' garantida, e este arquivo precisa do
-- catalogo ja no escopo de arquivo (o Action:position()/id() e' registrado na
-- carga, nao em runtime). Os outros arquivos escapam disso porque so leem os
-- globais dentro do onStartup. Aqui a dependencia fica explicita.
if not HuntInstances then
	dofile(DATA_DIRECTORY .. "/scripts/custom/hunt_instances/catalogo.lua")
end

local template = HuntInstances.thaisCyclops

local function entrarPublico(player)
	-- A hunt publica e' o proprio mapa: nenhum runId, nenhum slot.
	-- Basta liberar o caminho -- o jogador desce pela escada da cabana.
	player:sendTextMessage(MESSAGE_EVENT_ADVANCE,
		"Voce escolheu o mundo aberto. Desca pela escada.")
	return true
end

local function entrarPrivado(player)
	-- 3a validacao, imediatamente antes do teleporte (secao 10). As duas
	-- anteriores (abrir o seletor e usar) nao bastam: da para atacar alguem
	-- entre a abertura da janela e o clique.
	local membros, erro = InstanceEligibility.validarEntrada(player, template)
	if not membros then
		player:sendCancelMessage(erro)
		return false
	end

	local slot = InstancePool.alocar(template)
	if not slot then
		player:sendCancelMessage("As areas privadas estao ocupadas no momento.")
		return false
	end

	local ok = InstanceManager.criarExecucao(template, slot, membros)
	if not ok then
		InstancePool.liberar(slot, "falha ao criar execucao")
		player:sendCancelMessage("Nao foi possivel abrir a instancia.")
		return false
	end
	return true
end

local function abrirJanela(player)
	local emParty = player:getParty() ~= nil
	local janela = ModalWindow({
		title = template.nome,
		message = emParty
			and "Como sua party deseja entrar nesta area?"
			or "Como voce deseja entrar nesta area?",
	})

	janela:addChoice("Mundo Aberto", function(p, botao, _)
		if botao.name ~= "Entrar" then return true end
		entrarPublico(p)
	end)

	-- A opcao privada so aparece se elegivel E com slot livre. O servidor
	-- revalida no clique de qualquer jeito: o cliente nao decide nada
	-- (secao 15) e buttonId/choiceId nao sao validados em C++.
	local podePrivado = InstanceEligibility.podeEntrar(player, template)
		and InstancePool.disponiveis(template) > 0
	if podePrivado then
		janela:addChoice(emParty and "Instancia Privada para a Party"
			or "Instancia Privada", function(p, botao, _)
			if botao.name ~= "Entrar" then return true end
			entrarPrivado(p)
		end)
	end

	janela:addButton("Entrar")
	janela:addButton("Cancelar")
	janela:setDefaultEnterButton(0)
	janela:setDefaultEscapeButton(1)
	janela:sendToPlayer(player)

	if not podePrivado then
		local motivo = InstanceEligibility.motivoBloqueio(player, template)
		player:sendTextMessage(MESSAGE_EVENT_ADVANCE,
			motivo and ("Somente a entrada no mundo aberto esta disponivel: "
				.. motivo)
			or "As areas privadas estao ocupadas no momento.")
	end
end

local acao = Action()

function acao.onUse(player)
	-- 1a validacao: ao abrir o seletor (secao 10)
	abrirJanela(player)
	return true
end

-- Registrado por POSICAO. O :position() dispensa editar mapa.
--
-- ATENCAO: Action:id() e' id de ITEM, nao action id -- quem quer action id
-- usa :aid(). Passar 65001 para :id() registra um item inexistente e derruba
-- o register() inteiro, levando junto a registro por posicao: o obelisco fica
-- no chao e responde "You cannot use this object".
acao:position(template.seletor.posicao)
acao:aid(template.seletor.actionId)
acao:register()
