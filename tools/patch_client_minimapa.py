#!/usr/bin/env python3
"""Aplica no client montado os patches do minimapa da hunt instanciada.

Dentro de uma instancia o jogador esta em x >= 36864. O minimapa e' client-side
e indexado por coordenada absoluta, entao ali fica preto. Nao ha solucao no
servidor: sendAddCreature manda player->getPosition() cru e nao existe mensagem
de minimapa vinda do servidor.

A traducao e' na exibicao, e precisa valer nos DOIS sentidos:

  real -> publico   ao desenhar (camera e cruz do minimapa)
  publico -> real   ao clicar (checagem de distancia e autoWalk)

Fazer so o primeiro deixa o mapa bonito e o clique quebrado: o client tenta
caminhar ate Thais, a milhares de tiles, e responde "Destination is out of
range". Foi exatamente o que aconteceu.

As funcoes vao em gamelib/ui/uiminimap.lua, que carrega antes dos modulos de
jogo, e ficam globais para o game_minimap tambem usar -- assim a tabela de
slots existe num lugar so.

Roda depois de montar o client. O preparar_mehah.ps1 chama este script, senao
o patch se perde no proximo rebuild.

    python3 tools/patch_client_minimapa.py <pasta do client>
"""
from __future__ import annotations

import sys
from pathlib import Path

# Espelha data-otservbr-global/scripts/custom/hunt_instances/catalogo.lua.
# Se as origens de slot mudarem la, mudam aqui.
BLOCO = '''
-- ---------------------------------------------------------------------------
-- Hunt instanciada: traducao de coordenada do minimapa.
-- Gerado por tools/patch_client_minimapa.py -- nao editar a mao.
-- Espelha catalogo.lua do datapack.
-- ---------------------------------------------------------------------------
INSTANCIA_ORIGEM = { x = 32384, y = 32016 }
INSTANCIA_LARG, INSTANCIA_ALT = 169, 121
INSTANCIA_SLOTS = {
    { x = 36864, y = 36864 }, { x = 37376, y = 36864 }, { x = 37888, y = 36864 },
    { x = 38400, y = 36864 }, { x = 38912, y = 36864 }, { x = 39424, y = 36864 },
}

--- Posicao real -> posicao equivalente na hunt publica (para DESENHAR).
function InstanciaParaExibicao(pos)
    if not pos then return pos end
    for _, s in ipairs(INSTANCIA_SLOTS) do
        if pos.x >= s.x and pos.x < s.x + INSTANCIA_LARG
            and pos.y >= s.y and pos.y < s.y + INSTANCIA_ALT then
            return { x = pos.x - s.x + INSTANCIA_ORIGEM.x,
                     y = pos.y - s.y + INSTANCIA_ORIGEM.y,
                     z = pos.z }
        end
    end
    return pos
end

--- Posicao exibida -> posicao real do slot onde o jogador esta (para CLICAR).
-- Precisa saber em que slot ele esta, e isso vem da posicao real dele.
function InstanciaParaReal(pos)
    if not pos then return pos end
    local player = g_game.getLocalPlayer()
    if not player then return pos end
    local real = player:getPosition()
    if not real then return pos end
    for _, s in ipairs(INSTANCIA_SLOTS) do
        if real.x >= s.x and real.x < s.x + INSTANCIA_LARG
            and real.y >= s.y and real.y < s.y + INSTANCIA_ALT then
            -- o jogador esta neste slot: converte o alvo para dentro dele
            return { x = pos.x - INSTANCIA_ORIGEM.x + s.x,
                     y = pos.y - INSTANCIA_ORIGEM.y + s.y,
                     z = pos.z }
        end
    end
    return pos
end
'''

MARCA = "InstanciaParaExibicao"


def patch_uiminimap(caminho: Path) -> str:
    t = caminho.read_text(encoding="utf-8")
    if MARCA in t:
        return "ja patchado"

    # as funcoes vao no topo, antes de qualquer uso
    t = BLOCO + "\n" + t

    trocas = 0
    # os dois pontos onde o clique vira caminhada. A checagem de distancia
    # compara a posicao REAL do jogador com a posicao do mapa -- se a do mapa
    # vier traduzida e a dele nao, da sempre "out of range".
    for alvo, novo in [
        ("local function onFlagMouseRelease(widget, pos, button)\n"
         "    if button == MouseLeftButton then\n"
         "        local player = g_game.getLocalPlayer()\n",
         "local function onFlagMouseRelease(widget, pos, button)\n"
         "    if button == MouseLeftButton then\n"
         "        local player = g_game.getLocalPlayer()\n"
         "        widget.pos = InstanciaParaReal(widget.pos)\n"),
    ]:
        if alvo in t:
            t = t.replace(alvo, novo, 1)
            trocas += 1

    # o caminho do clique direto no mapa usa a variavel mapPos
    alvo2 = ("        if Position.distance(player:getPosition(), mapPos) > 250 then")
    if alvo2 in t:
        t = t.replace(alvo2,
                      "        mapPos = InstanciaParaReal(mapPos)\n" + alvo2, 1)
        trocas += 1

    caminho.write_text(t, encoding="utf-8")
    return f"patchado ({trocas} ponto(s) de clique)"


def patch_minimap(caminho: Path) -> str:
    t = caminho.read_text(encoding="utf-8")

    # remove uma versao anterior deste patch, que definia a traducao local
    if "instancia_traduzir" in t:
        ini = t.find("-- Hunt instanciada:")
        fim = t.find("local function onPositionChange")
        if 0 <= ini < fim:
            t = t[:ini] + t[fim:]
        t = t.replace("\tpos = instancia_traduzir(pos)\n", "")
        t = t.replace("    pos = instancia_traduzir(pos)\n", "")

    if "InstanciaParaExibicao(pos)" in t:
        return "ja patchado"

    for velho in ["    local pos = player:getPosition()",
                  "\tlocal pos = player:getPosition()"]:
        if velho in t:
            ind = velho[:len(velho) - len(velho.lstrip())]
            t = t.replace(velho,
                          velho + "\n" + ind + "pos = InstanciaParaExibicao(pos)",
                          1)
            caminho.write_text(t, encoding="utf-8")
            return "patchado"
    return "PADRAO NAO ENCONTRADO -- confira o minimap.lua"


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    raiz = Path(sys.argv[1])
    ui = raiz / "modules/gamelib/ui/uiminimap.lua"
    mm = raiz / "modules/game_minimap/minimap.lua"

    for f in (ui, mm):
        if not f.exists():
            print(f"nao encontrado: {f}", file=sys.stderr)
            return 1

    print(f"uiminimap.lua : {patch_uiminimap(ui)}")
    print(f"minimap.lua   : {patch_minimap(mm)}")

    # o modulo separado de antes nao serve mais: a traducao vive dentro dos
    # arquivos que desenham e que tratam o clique
    velho = raiz / "modules/instancia_minimapa"
    if velho.exists():
        import shutil
        shutil.rmtree(velho, ignore_errors=True)
        print("modulo instancia_minimapa removido (substituido pelo patch)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
