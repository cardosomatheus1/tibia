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
import pathlib
import re
from pathlib import Path

# A tabela sai dos catalogos do datapack, nao e' escrita aqui. Enquanto havia
# uma hunt so', repetir os numeros a mao passava; na segunda, Lower Roshamuul
# ficou de fora da traducao e o minimapa dela nasceu preto -- o jogador entrava
# num lugar que ele conhece e nao reconhecia nada.
CATALOGOS = pathlib.Path(__file__).resolve().parents[1] /     "data-otservbr-global/scripts/custom/hunt_instances"

RE_ORIGEM = re.compile(r"origem\s*=\s*Position\((\d+),\s*(\d+),")
RE_LARG = re.compile(r"largura\s*=\s*(\d+)")
RE_ALT = re.compile(r"altura\s*=\s*(\d+)")
RE_SLOTS = re.compile(r"slotOrigens\s*=\s*\{(.*?)\}", re.S)
RE_POS = re.compile(r"Position\((\d+),\s*(\d+),")


def ler_catalogos() -> list[dict]:
    """Toda hunt do datapack, com o recorte de onde veio e onde ela roda."""
    saida = []
    for arq in sorted(CATALOGOS.glob("catalogo*.lua")):
        texto = arq.read_text(encoding="utf-8")
        o, l, a, s = (RE_ORIGEM.search(texto), RE_LARG.search(texto),
                      RE_ALT.search(texto), RE_SLOTS.search(texto))
        if not (o and l and a and s):
            continue
        slots = [(int(x), int(y)) for x, y in RE_POS.findall(s.group(1))]
        if slots:
            saida.append({"nome": arq.stem, "ox": int(o.group(1)),
                          "oy": int(o.group(2)), "larg": int(l.group(1)),
                          "alt": int(a.group(1)), "slots": slots})
    return saida


def montar_bloco(hunts: list[dict]) -> str:
    linhas = [
        "",
        "-- " + "-" * 75,
        "-- Hunt instanciada: traducao de coordenada do minimapa.",
        "-- Gerado por tools/patch_client_minimapa.py -- nao editar a mao.",
        "--",
        "-- O minimapa e' do client e indexado por coordenada absoluta. Dentro da",
        "-- instancia o jogador esta em x >= 36864, onde ele nunca pisou, entao",
        "-- ficaria preto -- e a instancia deixaria de parecer o lugar que ele",
        "-- conhece. Aqui a posicao e' traduzida de volta para a hunt publica.",
        "--",
        "-- Vale nos DOIS sentidos: real -> publico ao desenhar, publico -> real",
        "-- ao clicar. So' o primeiro deixa o mapa bonito e o clique quebrado --",
        "-- o client tenta caminhar milhares de tiles e responde \"Destination is",
        "-- out of range\".",
        "-- " + "-" * 75,
        "INSTANCIAS = {",
    ]
    for h in hunts:
        linhas.append(f"    {{ -- {h['nome']}")
        linhas.append(f"        origem = {{ x = {h['ox']}, y = {h['oy']} }},")
        linhas.append(f"        larg = {h['larg']}, alt = {h['alt']},")
        linhas.append("        slots = {")
        for sx, sy in h["slots"]:
            linhas.append(f"            {{ x = {sx}, y = {sy} }},")
        linhas.append("        },")
        linhas.append("    },")
    linhas += [
        "}",
        "",
        "--- Em que hunt e slot esta esta posicao real, se estiver em alguma.",
        "local function acharSlot(pos)",
        "    for _, h in ipairs(INSTANCIAS) do",
        "        for _, s in ipairs(h.slots) do",
        "            if pos.x >= s.x and pos.x < s.x + h.larg",
        "                and pos.y >= s.y and pos.y < s.y + h.alt then",
        "                return h, s",
        "            end",
        "        end",
        "    end",
        "end",
        "",
        "--- Posicao real -> posicao equivalente na hunt publica (para DESENHAR).",
        "function InstanciaParaExibicao(pos)",
        "    if not pos then return pos end",
        "    local h, s = acharSlot(pos)",
        "    if not h then return pos end",
        "    return { x = pos.x - s.x + h.origem.x,",
        "             y = pos.y - s.y + h.origem.y, z = pos.z }",
        "end",
        "",
        "--- Posicao exibida -> posicao real do slot onde o jogador esta (CLICAR).",
        "-- Qual slot vem da posicao real do jogador, nao da posicao clicada.",
        "function InstanciaParaReal(pos)",
        "    if not pos then return pos end",
        "    local player = g_game.getLocalPlayer()",
        "    if not player then return pos end",
        "    local real = player:getPosition()",
        "    if not real then return pos end",
        "    local h, s = acharSlot(real)",
        "    if not h then return pos end",
        "    return { x = pos.x - h.origem.x + s.x,",
        "             y = pos.y - h.origem.y + s.y, z = pos.z }",
        "end",
        "",
    ]
    return "\n".join(linhas)


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
