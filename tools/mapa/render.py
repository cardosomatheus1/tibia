#!/usr/bin/env python3
"""Desenha uma regiao do OTBM como PNG, usando os sprites do client.

Serve para conferir uma edicao **antes** de subir o servidor: editar,
renderizar, olhar, corrigir — sem o ciclo de reiniciar o Canary e entrar no
jogo a cada tentativa.

    python3 tools/mapa/render.py --assets /caminho/dos/assets \\
        --saida previa.png 32350 32215 32360 32226 7

A ordem dos argumentos e x1 y1 x2 y2 z. O desenho e simples de proposito:
chao, depois os itens na ordem em que estao empilhados no tile. Sprite de
64x64 sobe e vai pra esquerda, que e como o client encaixa peca grande no
tile. Deslocamento por item (o `shift` das aparencias) nao e aplicado — a
previa fica alguns pixels fora do que o client mostra, o que nao atrapalha
para conferir layout.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
from otbm import Mapa            # noqa: E402
from ver_item import Assets      # noqa: E402

TILE = 32


def desenhar(mapa: Mapa, assets: Assets, x1, y1, x2, y2, z, zoom=2,
             grade=False, px_tile: int = TILE) -> Image.Image:
    """Desenha a regiao. `px_tile` e' a resolucao: 32 e' o sprite inteiro.

    Pedir menos que 32 encolhe cada sprite UMA vez e cola tudo ja pequeno,
    em vez de compor em tamanho cheio para reduzir depois. Como o custo de
    colar e' proporcional a area, px_tile=8 gasta 1/16 do trabalho de colagem
    -- e para quem esta olhando o mapa de longe o resultado e' o mesmo.
    """
    larg, alt = (x2 - x1 + 1), (y2 - y1 + 1)
    tela = Image.new("RGBA", (larg * px_tile, alt * px_tile), (24, 24, 28, 255))
    cache: dict[int, Image.Image | None] = {}

    def sprite(item_id):
        if item_id not in cache:
            s = assets.item(item_id)
            if s is not None and px_tile != TILE:
                # BOX faz media da area; NEAREST comeria as paredes finas
                s = s.resize((max(1, s.width * px_tile // TILE),
                              max(1, s.height * px_tile // TILE)), Image.BOX)
            cache[item_id] = s
        return cache[item_id]

    for y in range(y1, y2 + 1):
        for x in range(x1, x2 + 1):
            t = mapa.tile(x, y, z)
            if not t:
                continue
            px, py = (x - x1) * px_tile, (y - y1) * px_tile
            ids = ([t.chao] if t.chao else []) + [i for i, _, _ in t.itens]
            for iid in ids:
                s = sprite(iid)
                if s is None:
                    continue
                # peca maior que o tile e ancorada pelo canto inferior direito
                # paste com mascara mede ~2x mais rapido que alpha_composite
                tela.paste(s, (px - (s.width - px_tile), py - (s.height - px_tile)), s)

    if grade:
        for i in range(larg + 1):
            for j in range(alt * TILE):
                if j % 4 == 0 and i * TILE < tela.width:
                    tela.putpixel((min(i * TILE, tela.width - 1), j), (255, 255, 255, 60))
        for j in range(alt + 1):
            for i in range(larg * TILE):
                if i % 4 == 0 and j * TILE < tela.height:
                    tela.putpixel((i, min(j * TILE, tela.height - 1)), (255, 255, 255, 60))

    return tela.resize((tela.width * zoom, tela.height * zoom), Image.NEAREST)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("x1", type=int)
    p.add_argument("y1", type=int)
    p.add_argument("x2", type=int)
    p.add_argument("y2", type=int)
    p.add_argument("z", type=int)
    p.add_argument("--mapa", default="data-otservbr-global/world/otservbr.otbm")
    p.add_argument("--assets", required=True)
    p.add_argument("--saida", required=True)
    p.add_argument("--zoom", type=int, default=2)
    p.add_argument("--grade", action="store_true", help="desenha a grade de tiles")
    args = p.parse_args()

    mapa = Mapa(args.mapa)
    assets = Assets(args.assets)
    img = desenhar(mapa, assets, args.x1, args.y1, args.x2, args.y2, args.z,
                   args.zoom, args.grade)
    img.convert("RGB").save(args.saida)
    print(f"{args.x2 - args.x1 + 1}x{args.y2 - args.y1 + 1} tiles -> {args.saida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
