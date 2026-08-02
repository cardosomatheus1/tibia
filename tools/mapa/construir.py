#!/usr/bin/env python3
"""Constroi no mapa a partir de uma planta em texto.

A planta e um JSON com duas partes: o **desenho**, uma lista de linhas onde
cada caractere e um tile, e a **legenda**, que diz o que cada caractere
coloca ali.

    {
      "legenda": {
        ".": {"chao": 409, "limpar": true},
        "-": {"chao": 409, "itens": [1295], "limpar": true},
        "|": {"chao": 409, "itens": [1294], "limpar": true}
      },
      "desenho": ["-----", "|...|", "-----"]
    }

Cada entrada da legenda aceita:

    chao    id do item de chao (troca no lugar, sem mexer nos offsets)
    itens   ids empilhados por cima, de baixo pra cima
    limpar  true apaga o que ja estava em cima do chao (mato, pedra...)

Caractere que nao esta na legenda e ignorado, entao da pra deixar espaco
para "nao mexe aqui".

    python3 tools/mapa/construir.py planta.json 32362 32286 7

O canto superior esquerdo do desenho cai na coordenada informada. Sempre
faca uma copia do .otbm antes — a ferramenta grava por cima.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from otbm import Mapa   # noqa: E402


def aplicar(mapa: Mapa, planta: dict, x0: int, y0: int, z: int) -> dict:
    legenda = planta["legenda"]
    conta = {"chao": 0, "itens": 0, "limpos": 0, "fora": 0}

    for dy, linha in enumerate(planta["desenho"]):
        for dx, ch in enumerate(linha):
            regra = legenda.get(ch)
            if regra is None:
                continue
            x, y = x0 + dx, y0 + dy
            if mapa.tile(x, y, z) is None:
                conta["fora"] += 1          # buraco no mapa: nao da pra por nada
                continue
            if regra.get("limpar"):
                conta["limpos"] += mapa.limpar_itens(x, y, z)
            if regra.get("chao") and mapa.trocar_chao(x, y, z, regra["chao"]):
                conta["chao"] += 1
            for iid in regra.get("itens", []):
                if mapa.adicionar_item(x, y, z, iid):
                    conta["itens"] += 1
    return conta


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("planta")
    p.add_argument("x", type=int)
    p.add_argument("y", type=int)
    p.add_argument("z", type=int)
    p.add_argument("--mapa", default="data-otservbr-global/world/otservbr.otbm")
    p.add_argument("--saida", help="grava noutro arquivo em vez de por cima")
    p.add_argument("--backup", action="store_true",
                   help="guarda uma copia .bak antes de gravar")
    args = p.parse_args()

    planta = json.loads(Path(args.planta).read_text())
    largura = max(len(l) for l in planta["desenho"])
    print(f"planta {largura}x{len(planta['desenho'])} em "
          f"({args.x}, {args.y}, {args.z})")

    mapa = Mapa(args.mapa)
    conta = aplicar(mapa, planta, args.x, args.y, args.z)
    print(f"  chao trocado: {conta['chao']} | itens postos: {conta['itens']} "
          f"| itens tirados: {conta['limpos']}"
          + (f" | tiles inexistentes: {conta['fora']}" if conta["fora"] else ""))

    if not mapa.pendentes:
        print("  nada a gravar")
        return 0

    if args.backup and not args.saida:
        copia = Path(args.mapa).with_suffix(".otbm.bak")
        if not copia.exists():
            shutil.copy2(args.mapa, copia)
            print(f"  copia de seguranca em {copia.name}")

    destino = mapa.salvar(args.saida)
    print(f"  gravado em {destino}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
