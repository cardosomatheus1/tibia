#!/usr/bin/env python3
"""Acha os acessos entre andares numa regiao: escadas, buracos, rampas.

Etapa 1 da spec de hunt instanciada. A entrada de uma hunt subterranea nao esta
onde os monstros estao -- esta onde o chao muda de andar. Procurar "tile seguro"
acha campo aberto; procurar floorchange acha a boca da caverna.

Tambem serve ao catalogo (secao 23.7): esses tiles sao a fronteira natural que
ancora um flood fill, evitando que ele engula meio mapa por uma passagem.

O criterio vem do items.xml -- os mesmos dois que o servidor usa
(`itemType.floorChange` e `isTeleport()`, src/items/tile.cpp:56-60).

    python3 achar_acessos.py <mapa.otbm> x0 y0 x1 y1 z
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
sys.path.insert(0, str(AQUI))

from achar_posicoes import ids_de_fuga
from otbm import Mapa


def nomes_de_item(caminho: Path) -> dict[int, str]:
    nomes: dict[int, str] = {}
    for linha in caminho.read_text(encoding="utf-8",
                                   errors="ignore").splitlines():
        s = linha.strip()
        if not s.startswith("<item "):
            continue
        nome = ""
        if 'name="' in s:
            nome = s.split('name="', 1)[1].split('"', 1)[0]
        try:
            if 'id="' in s:
                nomes[int(s.split('id="', 1)[1].split('"', 1)[0])] = nome
            elif 'fromid="' in s:
                a = int(s.split('fromid="', 1)[1].split('"', 1)[0])
                b = int(s.split('toid="', 1)[1].split('"', 1)[0])
                for i in range(a, b + 1):
                    nomes[i] = nome
        except (IndexError, ValueError):
            pass
    return nomes


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("mapa")
    p.add_argument("coords", nargs=5, type=int,
                   metavar=("X0", "Y0", "X1", "Y1", "Z"))
    p.add_argument("--items", default=str(RAIZ / "data/items/items.xml"))
    p.add_argument("--agrupar", type=int, default=6,
                   help="junta acessos a menos de N tiles num so ponto")
    args = p.parse_args()

    x0, y0, x1, y1, z = args.coords
    fuga = ids_de_fuga(Path(args.items))
    nomes = nomes_de_item(Path(args.items))
    print(f"regiao: x {x0}-{x1}  y {y0}-{y1}  z {z}   "
          f"({len(fuga)} ids de acesso)")

    m = Mapa(args.mapa)
    achados: list[tuple[int, int, int, str]] = []
    for tile in m.regiao(x0, y0, x1, y1, z):
        ids = ([tile.chao] if tile.chao else []) + [i for i, _, _ in tile.itens]
        for iid in ids:
            if iid in fuga:
                achados.append((tile.x, tile.y, iid,
                                nomes.get(iid, "?")))
                break

    print(f"acessos encontrados: {len(achados)}")
    if not achados:
        return 1

    tipos = Counter(a[3] for a in achados)
    print("\npor tipo:")
    for nome, n in tipos.most_common(12):
        print(f"  {n:>4}  {nome}")

    # agrupa os vizinhos, senao uma escada larga vira 20 "acessos"
    grupos: list[list[tuple[int, int, int, str]]] = []
    for a in sorted(achados):
        for g in grupos:
            if any(max(abs(a[0] - b[0]), abs(a[1] - b[1])) <= args.agrupar
                   for b in g):
                g.append(a)
                break
        else:
            grupos.append([a])

    print(f"\n=== {len(grupos)} ponto(s) de acesso (agrupados a {args.agrupar} "
          f"tiles) ===")
    for i, g in enumerate(sorted(grupos, key=len, reverse=True)[:15], 1):
        xs = [b[0] for b in g]
        ys = [b[1] for b in g]
        cx, cy = sum(xs) // len(g), sum(ys) // len(g)
        tipo = Counter(b[3] for b in g).most_common(1)[0][0]
        print(f"  {i}. centro ({cx}, {cy}, {z})  {len(g)} tiles  "
              f"x {min(xs)}-{max(xs)} y {min(ys)}-{max(ys)}  [{tipo}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
