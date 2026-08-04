-- Elegibilidade: PK, PvP lock e cooldown.
-- Spec: docs/spec_hunt_instanciada_v2.md secao 10.
--
-- A validacao roda TRES vezes (secao 10): ao abrir o seletor, ao usar, e
-- imediatamente antes do teleporte. E' o que impede o abuso de abrir a janela
-- limpo, atacar alguem, e confirmar.

InstanceEligibility = InstanceEligibility or {}

--- Cooldown por CONTA, nao por personagem.
-- O padrao do repo (Player:getBossCooldown) e por GUID, mas aqui precisa ser
-- por conta: senao trocar de personagem reseta o cooldown e reabre o exploit
-- de matar o respawn da entrada e voltar (secao 12.3).
local function chaveCooldown(player, template)
	return KV.scoped("hunt-instance"):scoped(template.slug)
		:scoped(tostring(player:getAccountId()))
end

function InstanceEligibility.cooldownRestante(player, template)
	local ate = chaveCooldown(player, template):get("ate") or 0
	local falta = ate - os.time()
	return falta > 0 and falta or 0
end

function InstanceEligibility.aplicarCooldown(player, template)
	chaveCooldown(player, template):set("ate",
		os.time() + template.cooldownMinutos * 60)
end

function InstanceEligibility.skullBloqueada(player, template)
	local skull = player:getSkull()
	for _, s in ipairs(template.skullsBloqueadas) do
		if skull == s then
			return true
		end
	end
	return false
end

function InstanceEligibility.emPvp(player)
	-- PZ lock aceso por combate PvP, ou battle sign com jogador
	return player:hasCondition(CONDITION_INFIGHT) and player:isPzLocked()
end

--- Motivo pelo qual NAO pode entrar, ou nil se pode.
function InstanceEligibility.motivoBloqueio(player, template)
	if InstanceEligibility.skullBloqueada(player, template) then
		return "esta com skull"
	end
	if template.bloqueiaComPvpLock and InstanceEligibility.emPvp(player) then
		return "esta em combate PvP"
	end
	local falta = InstanceEligibility.cooldownRestante(player, template)
	if falta > 0 then
		return string.format("precisa esperar %d minuto(s)",
			math.ceil(falta / 60))
	end
	return nil
end

function InstanceEligibility.podeEntrar(player, template)
	return InstanceEligibility.motivoBloqueio(player, template) == nil
end

--- Quem esta em cima dos tiles de consentimento.
-- Presenca fisica E o consentimento (secao 9.2): a ModalWindow morre quando o
-- jogador anda, entao um ready check por janela seria cancelado por qualquer
-- passo de qualquer membro, em silencio.
function InstanceEligibility.presentes(template)
	local lista = {}
	for _, pos in ipairs(template.playerPositions) do
		local tile = Tile(pos)
		if tile then
			local c = tile:getTopCreature()
			if c and c:isPlayer() then
				lista[#lista + 1] = c
			end
		end
	end
	return lista
end

--- Valida o grupo inteiro. Devolve (lista, nil) ou (nil, mensagem).
function InstanceEligibility.validarEntrada(lider, template)
	local presentes = InstanceEligibility.presentes(template)

	local temLider = false
	for _, p in ipairs(presentes) do
		if p:getId() == lider:getId() then
			temLider = true
		end
	end
	if not temLider then
		return nil, "Suba em um dos tiles marcados diante do obelisco."
	end

	local party = lider:getParty()
	if party then
		if party:getLeader():getId() ~= lider:getId() then
			return nil, "Somente o lider da party pode iniciar uma instancia privada."
		end
		-- todos os membros online tem que estar presentes (secao 9.5)
		local membros = { party:getLeader() }
		for _, m in ipairs(party:getMembers()) do
			membros[#membros + 1] = m
		end
		if #membros < template.minimoMembrosParty then
			return nil, "A party nao possui membros suficientes."
		end
		if #membros > template.maximoMembros then
			return nil, string.format(
				"Esta instancia permite no maximo %d jogadores.",
				template.maximoMembros)
		end
		if template.exigeTodosOsMembros then
			for _, m in ipairs(membros) do
				local achou = false
				for _, p in ipairs(presentes) do
					if p:getId() == m:getId() then achou = true end
				end
				if not achou then
					return nil, m:getName() .. " nao esta nos tiles de entrada."
				end
			end
		end
		presentes = membros
	elseif not template.permiteSolo then
		return nil, "Esta hunt exige uma party."
	end

	if #presentes > template.maximoMembros then
		return nil, string.format("No maximo %d jogadores.", template.maximoMembros)
	end

	-- elegibilidade individual: um impedido bloqueia todo mundo (secao 10)
	local impedidos = {}
	for _, p in ipairs(presentes) do
		local motivo = InstanceEligibility.motivoBloqueio(p, template)
		if motivo then
			impedidos[#impedidos + 1] = p:getName() .. " -- " .. motivo
		end
	end
	if #impedidos > 0 then
		return nil, "Membros impedidos:\n" .. table.concat(impedidos, "\n")
	end

	return presentes, nil
end
