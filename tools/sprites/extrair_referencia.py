#!/usr/bin/env python3
"""Tira quadros de uma folha de referência (jpg/png) e salva em 32x32 PNG.

Serve para aproveitar arte que já existe num mockup ou concept sheet: recorta
a região, apaga o fundo por diferença de cor, corta na caixa do desenho e
centraliza num quadro do tamanho do tile.

O resultado é sempre pior do que desenhar direto em 32x32 — um mockup em jpg
tem artefato de compressão e resolução alta demais, e o downscale come
detalhe. Use isto para prototipar; para valer, desenhe no tamanho final.

    python3 tools/sprites/extrair_referencia.py folha.jpg saida/ \\
        --caixa 243,183,275,215 --caixa 693,160,760,228

As caixas são (esquerda, topo, direita, baixo) em pixels da folha.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


def tirar_fundo(img: Image.Image, canal: str = "vermelho") -> Image.Image:
    """Apaga o fundo mantendo só os pixels dominados por um canal.

    O padrão (`vermelho`) serve para fogo sobre fundo escuro: mantém o que é
    claro e mais vermelho que azul.
    """
    ordem = {"vermelho": (0, 2), "verde": (1, 2), "azul": (2, 0)}[canal]
    img = img.convert("RGBA")
    px = img.load()
    for y in range(img.height):
        for x in range(img.width):
            c = px[x, y]
            forte, fraco = c[ordem[0]], c[ordem[1]]
            if forte < 95 or forte < fraco + 35:
                px[x, y] = (0, 0, 0, 0)
            else:
                px[x, y] = (c[0], c[1], c[2], min(255, int((forte - 60) * 1.6)))
    return img


def centralizar(img: Image.Image, lado: int = 32) -> Image.Image:
    caixa = img.getbbox()
    if caixa:
        img = img.crop(caixa)
    escala = min(lado / img.width, lado / img.height)
    img = img.resize((max(1, round(img.width * escala)),
                      max(1, round(img.height * escala))), Image.LANCZOS)

    px = img.load()                       # pixel art não tem meio-tom de borda
    for y in range(img.height):
        for x in range(img.width):
            c = px[x, y]
            px[x, y] = (c[0], c[1], c[2], 0 if c[3] < 70 else 255)

    quadro = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    quadro.paste(img, ((lado - img.width) // 2, (lado - img.height) // 2), img)
    return quadro


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("folha")
    p.add_argument("saida")
    p.add_argument("--caixa", action="append", required=True,
                   metavar="E,T,D,B", help="região a recortar (repetível)")
    p.add_argument("--canal", default="vermelho",
                   choices=["vermelho", "verde", "azul"],
                   help="canal dominante do desenho (o resto vira transparente)")
    p.add_argument("--tamanho", type=int, default=32)
    p.add_argument("--prefixo", default="quadro")
    args = p.parse_args()

    im = Image.open(args.folha)
    destino = Path(args.saida)
    destino.mkdir(parents=True, exist_ok=True)

    for i, txt in enumerate(args.caixa, 1):
        caixa = tuple(int(v) for v in txt.split(","))
        if len(caixa) != 4:
            raise SystemExit(f"caixa inválida: {txt}")
        quadro = centralizar(tirar_fundo(im.crop(caixa), args.canal), args.tamanho)
        arquivo = destino / f"{args.prefixo}_{i:02d}.png"
        quadro.save(arquivo)
        print(f"  {arquivo}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
