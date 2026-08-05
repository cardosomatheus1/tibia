-- Pool de slots fisicos. Spec: docs/spec_hunt_instanciada_v2.md secao 8.
--
-- NAO ha mutex nem reserva atomica de proposito. O Lua do Canary e
-- estritamente single-threaded -- `static ScriptEnvironment scriptEnv[16]` com
-- `++scriptEnvIndex` sem atomic (src/lua/functions/lua_functions_loader.hpp).
-- Nada preempta entre duas linhas, entao `if livre then livre = false end` ja
-- e' atomico. addEvent tambem nao preempta: so roda depois que o script
-- corrente retorna.

InstancePool = InstancePool or {}

-- estado em memoria; nao persiste. Depois de restart todo slot nasce FREE
-- e quem estiver dentro e' resgatado no login (spec 14.4).
local slots = {}

local ESTADOS = { FREE = "FREE", ACTIVE = "ACTIVE",
                  CLEANING = "CLEANING", FAULTED = "FAULTED" }

--- Nome estavel da zona do slot.
-- Zona NAO e destruivel: nao existe Zone:remove() em Lua nem removeZone em
-- C++; Zone::addZone insere num static phmap e so clearZones() global limpa.
-- Por isso o nome vem do indice do slot e nunca de um runId -- senao vaza uma
-- zona por execucao, para sempre (spec 8.4).
local function nomeDaZona(template, indice)
	return string.format("hunt.%s.slot.%d", template.slug, indice)
end

function InstancePool.registrar(template)
	slots[template.slug] = {}
	for i, origem in ipairs(template.slotOrigens) do
		slots[template.slug][i] = {
			indice = i,
			template = template,
			origem = origem,
			estado = ESTADOS.FREE,
			zona = Zone(nomeDaZona(template, i)),
			run = nil,
		}
	end
	return slots[template.slug]
end

function InstancePool.todos(template)
	return slots[template.slug] or {}
end

function InstancePool.get(template, indice)
	local lista = slots[template.slug]
	return lista and lista[indice] or nil
end

--- Converte posicao relativa do template em posicao real do slot.
function InstancePool.posicaoReal(slot, rel)
	-- z e' absoluto no recorte, entao nao soma o z da origem
	return Position(slot.origem.x + rel.x, slot.origem.y + rel.y, rel.z)
end

--- Area do slot, para addArea e para getSlotByPosition.
function InstancePool.area(slot)
	local t = slot.template.template
	return {
		x0 = slot.origem.x,
		y0 = slot.origem.y,
		x1 = slot.origem.x + t.largura - 1,
		y1 = slot.origem.y + t.altura - 1,
	}
end

--- Aloca o primeiro slot livre, ou nil.
-- Sem cerimonia de atomicidade (ver cabecalho). A checagem por presenca real
-- e defesa em profundidade: e' o padrao do BossLever (boss_lever.lua:170),
-- imune a dessincronia da flag.
function InstancePool.alocar(template)
	for _, slot in ipairs(InstancePool.todos(template)) do
		if slot.estado == ESTADOS.FREE
			and slot.zona:countPlayers(IgnoredByMonsters) == 0 then
			slot.estado = ESTADOS.ACTIVE
			return slot
		end
	end
	return nil
end

--- Devolve o slot ao pool. NAO limpa: quem limpa e' o InstanceCleaner.
-- Usar isto para abortar uma entrada que falhou antes de povoar o slot.
-- Para encerrar execucao com jogadores dentro, use InstanceCleaner.limpar.
function InstancePool.liberar(slot, motivo)
	slot.run = nil
	slot.estado = ESTADOS.FREE
	logger.info("[hunt-instance] slot {} do {} devolvido ao pool: {}",
		slot.indice, slot.template.slug, motivo or "sem motivo")
end

function InstancePool.disponiveis(template)
	local n = 0
	for _, slot in ipairs(InstancePool.todos(template)) do
		if slot.estado == ESTADOS.FREE then
			n = n + 1
		end
	end
	return n
end

--- Qual slot contem esta posicao. Usado no login para resgatar quem ficou
-- dentro de instancia orfa, e para derivar a instancia de um monstro sem
-- precisar marcar cada criatura (spec 13.3).
function InstancePool.slotDaPosicao(pos)
	for _, lista in pairs(slots) do
		for _, slot in ipairs(lista) do
			local a = InstancePool.area(slot)
			if pos.x >= a.x0 and pos.x <= a.x1
				and pos.y >= a.y0 and pos.y <= a.y1 then
				return slot
			end
		end
	end
	return nil
end

InstancePool.ESTADOS = ESTADOS
