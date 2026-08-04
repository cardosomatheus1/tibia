#!/usr/bin/env python3
"""Acha tiles seguros para teleportar jogador, e prova que sao seguros.

Etapa 1 da spec de hunt instanciada. Precisa escolher:

  - os tiles de consentimento diante do seletor, no mapa GLOBAL (secao 9.2);
  - os tiles de entrada dentro da INSTANCIA (secao 13 da v1).

Escolher no olho e' como se perde uma tarde: teleportar em cima de parede, de
buraco, de campo magico ou dentro do primeiro respawn. Aqui o criterio e'
verificavel e vem do mesmo appearances.dat que o gerar_minimapa ja usa.

Um tile e' considerado seguro quando:
  - tem chao;
  - nenhum item nele tem a flag unpass (parede, movel bloqueante);
  - nao e' escada/buraco/teleport (o jogador escorregaria pra outro andar);
  - esta a pelo menos `--espaco` tiles de qualquer outro escolhido.

    python3 achar_posicoes.py <mapa.otbm> x0 y0 x1 y1 z [--n 5] [--espaco 2]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
sys.path.insert(0, str(AQUI))

from gerar_minimapa import ITEM_VAZIO, ler_atributos
from otbm import Mapa

def ids_de_fuga(caminho_items: Path) -> set[int]:
    """Ids que tiram o jogador do tile: floorchange e teleport.

    Sao os mesmos dois que o servidor usa (`itemType.floorChange` e
    `itemType.isTeleport()`, src/items/tile.cpp:56-60). Nao da pra deduzir do
    appearances.dat -- so o items.xml tem.

    Atencao ao caminho: o items.xml fica em data/items/, NAO em
    data-otservbr-global/items/. Apontar errado devolve conjunto vazio e o
    filtro passa a nao filtrar nada, em silencio.
    """
    if not caminho_items.exists():
        raise SystemExit(f"items.xml nao encontrado: {caminho_items}")

    achados: set[int] = set()
    faixa: tuple[int, int] | None = None
    for linha in caminho_items.read_text(encoding="utf-8",
                                         errors="ignore").splitlines():
        s = linha.strip()
        if s.startswith("<item "):
            faixa = None
            try:
                if 'id="' in s:
                    v = int(s.split('id="', 1)[1].split('"', 1)[0])
                    faixa = (v, v)
                elif 'fromid="' in s:
                    a = int(s.split('fromid="', 1)[1].split('"', 1)[0])
                    b = int(s.split('toid="', 1)[1].split('"', 1)[0])
                    faixa = (a, b)
            except (IndexError, ValueError):
                faixa = None
        elif faixa and 'key="' in s:
            baixo = s.lower()
            if 'key="floorchange"' in baixo or 'value="teleport"' in baixo:
                achados.update(range(faixa[0], faixa[1] + 1))
    return achados


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("mapa")
    p.add_argument("coords", nargs=5, type=int, metavar=("X0", "Y0", "X1", "Y1", "Z"))
    p.add_argument("--n", type=int, default=5)
    p.add_argument("--espaco", type=int, default=2,
                   help="distancia minima entre os escolhidos")
    p.add_argument("--dat", default=str(RAIZ / "data/items/appearances.dat"))
    p.add_argument("--items", default=str(RAIZ / "data/items/items.xml"))
    p.add_argument("--centro", nargs=2, type=int, metavar=("CX", "CY"),
                   help="agrupa as escolhas em volta deste ponto")
    p.add_argument("--spawns", help="XML de spawn a evitar")
    p.add_argument("--rebase", nargs=2, type=int, default=[0, 0],
                   metavar=("X0", "Y0"),
                   help="offset do recorte, p/ converter o spawn global")
    p.add_argument("--longe", type=int, default=3,
                   help="distancia minima de um spawn")
    args = p.parse_args()

    x0, y0, x1, y1, z = args.coords
    print(f"regiao: x {x0}-{x1}  y {y0}-{y1}  z {z}")

    attrs = ler_atributos(Path(args.dat))
    fuga = ids_de_fuga(Path(args.items))
    print(f"atributos de {len(attrs)} itens; {len(fuga)} ids de fuga (escada/"
          f"buraco/teleport)")

    # spawns a evitar: teleportar em cima do respawn e' o erro classico
    perto_de_spawn: set[tuple[int, int]] = set()
    if args.spawns:
        import re
        RB = re.compile(rb'<monster\s+centerx="(\d+)"\s+centery="(\d+)"'
                        rb'\s+centerz="(\d+)"(?:\s+radius="(\d+)")?\s*>'
                        rb'(.*?)</monster>', re.DOTALL)
        RF = re.compile(rb'<monster\s+name="[^"]+"\s+x="(-?\d+)"\s+y="(-?\d+)"'
                        rb'\s+z="(\d+)"')
        rx, ry = args.rebase
        dados = Path(args.spawns).read_bytes()
        n_spawn = 0
        for mm in RB.finditer(dados):
            cx, cy = int(mm.group(1)), int(mm.group(2))
            for ff in RF.finditer(mm.group(5)):
                if int(ff.group(3)) != z:
                    continue
                sx = cx + int(ff.group(1)) - rx
                sy = cy + int(ff.group(2)) - ry
                n_spawn += 1
                for dx in range(-args.longe, args.longe + 1):
                    for dy in range(-args.longe, args.longe + 1):
                        perto_de_spawn.add((sx + dx, sy + dy))
        print(f"{n_spawn} spawns no andar {z}; {len(perto_de_spawn)} tiles "
              f"bloqueados por proximidade (raio {args.longe})")

    m = Mapa(args.mapa)
    seguros: list[tuple[int, int]] = []
    total = com_chao = 0

    for tile in m.regiao(x0, y0, x1, y1, z):
        total += 1
        if tile.chao is None:
            continue
        com_chao += 1
        if tile.chao in fuga:
            continue
        if (tile.x, tile.y) in perto_de_spawn:
            continue
        ok = True
        for iid, _, _ in tile.itens:
            if attrs.get(iid, ITEM_VAZIO).bloqueia or iid in fuga:
                ok = False
                break
        if ok:
            seguros.append((tile.x, tile.y))

    print(f"tiles na regiao: {total}   com chao: {com_chao}   "
          f"seguros: {len(seguros)}")
    if not seguros:
        print("\nNENHUM tile seguro -- confira a regiao e o andar")
        return 1

    # Sem centro, a ordem de varredura enfileira tudo na borda de menor y --
    # posicao ruim. Por padrao agrupa em volta do centroide dos tiles seguros,
    # que cai numa area aberta de verdade.
    if args.centro:
        cx, cy = args.centro
    else:
        cx = sum(p[0] for p in seguros) // len(seguros)
        cy = sum(p[1] for p in seguros) // len(seguros)
    print(f"agrupando em volta de ({cx}, {cy})")

    seguros.sort(key=lambda p: max(abs(p[0] - cx), abs(p[1] - cy)))

    escolhidos: list[tuple[int, int]] = []
    for pos in seguros:
        if all(max(abs(pos[0] - e[0]), abs(pos[1] - e[1])) >= args.espaco
               for e in escolhidos):
            escolhidos.append(pos)
            if len(escolhidos) == args.n:
                break

    print(f"\n=== {len(escolhidos)} posicoes escolhidas "
          f"(espacamento minimo {args.espaco}) ===")
    for i, (x, y) in enumerate(escolhidos, 1):
        print(f"  {i}. Position({x}, {y}, {z})")

    if len(escolhidos) < args.n:
        print(f"\nAVISO: pedidas {args.n}, achadas {len(escolhidos)}. "
              f"Diminua --espaco ou amplie a regiao.")
        return 1

    print("\nem Lua:")
    print("    {")
    for x, y in escolhidos:
        print(f"        Position({x}, {y}, {z}),")
    print("    }")
    return 0


if __name__ == "__main__":
    sys.exit(main())
