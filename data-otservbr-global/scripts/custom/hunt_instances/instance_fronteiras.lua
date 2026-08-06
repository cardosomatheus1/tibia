-- Etapa 5: fronteira da instancia. Spec secao 11.0.
--
-- O JOGADOR NUNCA PODE VER O FIM DO MAPA. Observado em jogo: saindo da caverna
-- e andando para o sul chega-se a borda do recorte e ve-se o vazio. Pior, antes
-- disso a margem de terreno ENGANA -- e' copia fiel dos arredores de Thais,
-- entao o jogador acha que voltou ao mundo e continua andando.
--
-- A secao 11.0 previa duas fronteiras (saida e contencao). Na implementacao
-- vira UMA: se o beforeLeave da zona da hunt SEMPRE bloqueia e abre o dialogo,
-- o jogador nunca passa da borda da hunt, logo nunca alcanca a borda do
-- recorte. A margem continua existindo, mas so para ser VISTA -- o viewport
-- mostra 8 a 11 tiles alem, que e' exatamente para o que ela serve.
--
-- beforeLeave e' vetavel: retornar false bloqueia a saida
-- (src/game/game.cpp:12395, wrapper em data/libs/systems/zones.lua:126).

InstanceFronteiras = InstanceFronteiras or {}

-- A hunt dentro do recorte, em coordenada relativa: o recorte tem margem de
-- cada lado (secao 6.1.1) e a hunt ocupa o miolo.
--
-- Isto ficava escrito aqui, com os numeros dos ciclopes. Funcionava enquanto
-- so' havia uma hunt; na segunda, a fronteira de Lower Roshamuul foi calculada
-- com a geometria de Thais, o beforeLeave nunca reconhecia a borda certa e o
-- jogador ficava preso la' dentro. Agora vem do catalogo, por hunt.
local function huntDe(template)
	local f = template.fronteira
	if f then
		return f
	end
	-- Sem `fronteira` no catalogo, deduz da margem: o miolo e' o recorte menos
	-- a margem de cada lado. Mantem de pe' quem nao declarou.
	local t = template.template
	local m = template.margemRecorte or 16
	return { x0 = m, y0 = m, x1 = t.largura - m - 1, y1 = t.altura - m - 1 }
end

-- quem ja tem dialogo aberto, para nao reabrir a cada passo barrado
local perguntando = {}

-- Saidas AUTORIZADAS pelo sistema.
--
-- Sem isto o beforeLeave bloqueia o proprio teleporte de saida: sair da
-- instancia dispara mudanca de zona, a fronteira veta, e o jogador fica preso.
-- Foi exatamente o que aconteceu -- o dialogo confirmava e a mensagem de
-- resgate aparecia, mas ninguem saia do lugar.
local autorizados = {}

--- Libera a proxima saida deste jogador. Chamar ANTES de teleportar para fora.
function InstanceFronteiras.autorizarSaida(player)
	autorizados[player:getGuid()] = true
end

local function centroDaHunt(slot)
	local h = huntDe(slot.template)
	local andares = slot.template.template.andares
	return Position(
		slot.origem.x + math.floor((h.x0 + h.x1) / 2),
		slot.origem.y + math.floor((h.y0 + h.y1) / 2),
		-- o andar do meio da hunt, nao um 8 fixo: com z fixo o centro caia
		-- fora do recorte em qualquer hunt que nao tivesse esse andar
		andares[math.ceil(#andares / 2)])
end

local function perguntarSaida(player, slot)
	local guid = player:getGuid()
	if perguntando[guid] then
		return
	end
	perguntando[guid] = true

	-- O aviso muda conforme sobra ou nao alguem dentro: sair sozinho encerra
	-- a instancia e nao tem volta; sair de um grupo deixa a porta aberta.
	-- Dizer sempre "nao sera possivel retornar" era mentira depois que a
	-- reentrada passou a existir.
	local acompanhado = false
	if slot.run then
		for outro in pairs(slot.run.membros) do
			if outro ~= guid then
				acompanhado = true
				break
			end
		end
	end

	local janela = ModalWindow({
		title = slot.template.nome,
		message = "Voce esta saindo da area privada.\n\n" .. (acompanhado
			and "Seus companheiros continuam dentro, entao voce podera\n"
				.. "voltar pelo obelisco enquanto algum deles estiver la.\n"
			or "Voce e' o ultimo aqui dentro: ao sair, a instancia sera\n"
				.. "encerrada e nao havera como retornar.\n")
			.. "\nDeseja sair?",
	})
	janela:addChoice("Sair para o mapa global", function(p, botao, _)
		perguntando[p:getGuid()] = nil
		if botao.name ~= "Confirmar" then
			return true
		end
		InstanceManager.sair(p, "saiu pela borda da hunt")
	end)
	janela:addChoice("Continuar na instancia", function(p, botao, _)
		perguntando[p:getGuid()] = nil
	end)
	janela:addButton("Confirmar")
	janela:addButton("Cancelar")
	janela:setDefaultEnterButton(0)
	janela:setDefaultEscapeButton(1)
	janela:sendToPlayer(player)
	-- A janela nao corre risco de ser invalidada por movimento (secao 9.2):
	-- o passo dele acabou de ser barrado, entao esta parado por construcao.
end

--- Registra a fronteira de um slot. Chamado no startup, depois das zonas.
function InstanceFronteiras.registrar(slot)
	local t = slot.template.template
	local zona = Zone(string.format("hunt.%s.slot.%d.area",
		slot.template.slug, slot.indice))
	local h = huntDe(slot.template)
	-- Os andares da HUNT, nao os do recorte. O recorte inclui tambem o andar
	-- por onde se sai -- sem ele a escada nao existiria e o jogador ficaria
	-- preso. Mas se a zona cobrisse esse andar tambem, descer a escada nao
	-- seria sair: o jogador desceria e andaria a vontade pela margem, que foi
	-- o que aconteceu em Lower Roshamuul. Pisar no andar de saida tem de
	-- disparar o dialogo, e para isso ele fica FORA da zona.
	for _, z in ipairs(slot.template.andaresHunt or t.andares) do
		zona:addArea(
			Position(slot.origem.x + h.x0, slot.origem.y + h.y0, z),
			Position(slot.origem.x + h.x1, slot.origem.y + h.y1, z))
	end
	slot.zonaHunt = zona

	local ev = ZoneEvent(zona)

	function ev.beforeLeave(_, creature)
		local player = creature:getPlayer()
		if not player then
			return true      -- monstro nao e' barrado aqui; quem prende e' o
			                 -- trapMonsters da zona do slot
		end
		-- saida autorizada pelo sistema (dialogo confirmado, resgate, morte):
		-- deixa passar UMA vez, senao a fronteira bloqueia a propria saida
		local guid = player:getGuid()
		if autorizados[guid] then
			autorizados[guid] = nil
			perguntando[guid] = nil
			return true
		end
		-- GM passa: precisa poder inspecionar sem ficar preso
		if player:getGroup():getId() >= GROUP_TYPE_GAMEMASTER then
			return true
		end
		perguntarSaida(player, slot)
		return false         -- barra SEMPRE: e' o que impede de ver o vazio
	end

	ev:register()
end

function InstanceFronteiras.esquecer(player)
	perguntando[player:getGuid()] = nil
end

--- Onde devolver alguem que apareceu fora da hunt mas dentro do recorte
-- (teleporte de GM, ou instancia orfa depois de restart).
function InstanceFronteiras.resgate(slot)
	return centroDaHunt(slot)
end
