#!/usr/bin/env python3
"""Lista o que existe numa regiao do mapa — o jeito mais direto de
descobrir id de item.

O `items.xml` do datapack so nomeia o que tem comportamento (porta, chave,
comida). Parede, chao e decoracao nao aparecem por nome. Entao, para achar
o id de uma parede de pedra, olhe uma casa que ja existe:

    python3 tools/mapa/ler_mapa.py 32351 32218 32355 32224 7

Sai um mapa em texto com o chao e os itens de cada tile, mais um resumo
dos ids que mais aparecem na regiao. Depois use o `ver_item.py` para ver
como cada um e desenhado.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from otbm import Mapa   # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("x1", type=int)
    p.add_argument("y1", type=int)
    p.add_argument("x2", type=int)
    p.add_argument("y2", type=int)
    p.add_argument("z", type=int)
    p.add_argument("--mapa", default="data-otservbr-global/world/otservbr.otbm")
    p.add_argument("--detalhe", action="store_true",
                   help="lista tile a tile em vez do resumo")
    args = p.parse_args()

    mapa = Mapa(args.mapa)
    print(f"mapa {mapa.cabecalho[1]}x{mapa.cabecalho[2]}")

    chaos, itens, vazios = Counter(), Counter(), 0
    for y in range(args.y1, args.y2 + 1):
        linha = []
        for x in range(args.x1, args.x2 + 1):
            t = mapa.tile(x, y, args.z)
            if t is None:
                vazios += 1
                linha.append("     -")
                continue
            chaos[t.chao] += 1
            for iid, _, _ in t.itens:
                itens[iid] += 1
            if args.detalhe:
                marca = "C" if t.casa else " "
                print(f"{x},{y},{args.z}{marca} chao={t.chao} "
                      f"itens={[i for i, _, _ in t.itens]}")
            else:
                linha.append(f"{t.chao:6d}" + ("*" if t.itens else " "))
        if not args.detalhe:
            print("".join(linha))

    print(f"\nchao mais comum: {chaos.most_common(6)}")
    print(f"itens mais comuns: {itens.most_common(12)}")
    if vazios:
        print(f"tiles inexistentes: {vazios}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
