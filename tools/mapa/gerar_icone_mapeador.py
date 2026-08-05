#!/usr/bin/env python3
"""Desenha o icone do Mapeador de Hunts a partir do proprio mapa.

Faz o que a ferramenta faz: recorta um pedaco do mapa com os sprites do
client e marca os limites de vermelho. Assim o atalho mostra exatamente o
que o programa entrega, em vez de um simbolo generico.

    python3 tools/mapa/gerar_icone_mapeador.py <mapa.otbm> --assets <pasta> \\
        --saida mapeador.ico
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI.parents[1] / "sprites"))

from otbm import Mapa            # noqa: E402
from render import desenhar      # noqa: E402
from ver_item import Assets      # noqa: E402

# Boca da caverna dos ciclopes de Thais: tem pedra, grama e o contorno da
# entrada, entao fica reconhecivel mesmo em 16x16.
X, Y, Z, LADO = 32452, 32074, 7, 22

TAMANHOS = [16, 24, 32, 48, 64, 128, 256]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("mapa")
    p.add_argument("--assets", required=True)
    p.add_argument("--saida", required=True)
    args = p.parse_args()

    m = Mapa(args.mapa, cache_tiles=False)
    a = Assets(args.assets)
    a.aparencias.indexar("object")

    im = desenhar(m, a, X, Y, X + LADO - 1, Y + LADO - 1, Z,
                  zoom=1, px_tile=32).convert("RGBA")

    # a marca vermelha do pincel, que e' a assinatura visual da ferramenta
    marca = Image.new("RGBA", im.size, (0, 0, 0, 0))
    lado_px = im.width
    faixa = Image.new("RGBA", (lado_px // 2, lado_px // 2), (255, 77, 77, 110))
    marca.paste(faixa, (lado_px // 4, lado_px // 4))
    im = Image.alpha_composite(im, marca)

    # borda escura: destaca o icone sobre papel de parede claro
    borda = max(2, lado_px // 32)
    for i in range(borda):
        for x in range(lado_px):
            im.putpixel((x, i), (20, 20, 24, 255))
            im.putpixel((x, lado_px - 1 - i), (20, 20, 24, 255))
        for y in range(lado_px):
            im.putpixel((i, y), (20, 20, 24, 255))
            im.putpixel((lado_px - 1 - i, y), (20, 20, 24, 255))

    saida = Path(args.saida)
    im.save(saida, sizes=[(n, n) for n in TAMANHOS])
    print(f"{saida}  ({im.width}x{im.height}, {len(TAMANHOS)} resolucoes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
