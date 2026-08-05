--[[ Minimapa da hunt instanciada.

O jogador dentro de uma instancia esta fisicamente em x >= 36864, longe do
mundo. O minimapa e' 100% client-side e indexado por coordenada absoluta,
entao ali fica preto: ninguem nunca explorou aquelas coordenadas.

Nao ha solucao no servidor. sendAddCreature manda player->getPosition() cru
(protocolgame.cpp:1098) e nao existe mensagem de minimapa vinda do servidor --
o unico hit em todo o protocolgame.cpp e' MinimapMarker, da cyclopedia. Mentir
a posicao exigiria traduzir tudo que entra e sai da camada de protocolo, em C++.

A solucao e' traduzir na EXIBICAO. Este modulo converte a posicao para a
coordenada equivalente na hunt publica antes de alimentar o widget, entao o
jogador se ve em Thais, com o mapa real em volta -- e o .otmm que ja vem no
client e' reaproveitado, sem precisar gerar minimapa da regiao da instancia.

E' cosmetico: a verdade do servidor continua sendo 36864. Comando de GM e
exiva mostram a posicao real, e isso e' proposital.

Precisa rodar DEPOIS do game_minimap, que tambem escreve no widget a cada
passo -- dai o autoload-priority maior no .otmod.

Os valores abaixo espelham data-otservbr-global/scripts/custom/hunt_instances/
catalogo.lua. Se as origens de slot mudarem la, mudam aqui.
]]

local ORIGEM_HUNT = { x = 32384, y = 32016 }   -- de onde o recorte foi tirado
local LARGURA, ALTURA = 169, 121

local SLOTS = {
	{ x = 36864, y = 36864 },
	{ x = 37376, y = 36864 },
	{ x = 37888, y = 36864 },
	{ x = 38400, y = 36864 },
	{ x = 38912, y = 36864 },
	{ x = 39424, y = 36864 },
}

local controller = Controller:new()

--- Posicao equivalente no mundo publico, ou nil se nao esta em instancia.
local function traduzir(pos)
	if not pos then
		return nil
	end
	for _, s in ipairs(SLOTS) do
		if pos.x >= s.x and pos.x < s.x + LARGURA
			and pos.y >= s.y and pos.y < s.y + ALTURA then
			return {
				x = pos.x - s.x + ORIGEM_HUNT.x,
				y = pos.y - s.y + ORIGEM_HUNT.y,
				z = pos.z,          -- o andar e' o mesmo (5-9)
			}
		end
	end
	return nil
end

local function widget()
	local mod = modules.game_minimap
	if not mod or not mod.mapController then
		return nil
	end
	local ui = mod.mapController.ui
	if not ui or not ui.minimapBorder then
		return nil
	end
	return ui.minimapBorder.minimap
end

local function corrigir()
	local jogador = g_game.getLocalPlayer()
	if not jogador then
		return
	end
	local destino = traduzir(jogador:getPosition())
	if not destino then
		return          -- fora de instancia: deixa o game_minimap em paz
	end

	local mm = widget()
	if not mm or mm:isDragging() then
		return
	end
	-- fullMapView tem camera propria; mexer nela atrapalharia o arrastar
	if not mm.fullMapView then
		mm:setCameraPosition(destino)
	end
	mm:setCrossPosition(destino)
end

function init()
	controller:init()
	controller:registerEvents(LocalPlayer, {
		onPositionChange = corrigir,
	})
	-- ao entrar no jogo ja dentro de uma instancia (relog), o evento de
	-- posicao pode nao disparar
	controller:scheduleEvent(corrigir, 1000, "instancia_minimapa_inicial")
end

function terminate()
	controller:terminate()
end
