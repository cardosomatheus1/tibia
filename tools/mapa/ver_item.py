#!/usr/bin/env python3
"""Desenha os sprites de ids de item, para escolher o que usar no mapa.

Editar mapa e escolher numero: parede e 1294, chao de marmore e 409. So que
o `items.xml` nao nomeia decoracao, entao o jeito de descobrir e olhar. Esta
ferramenta le os assets do client e monta uma folha de contato com os ids
pedidos.

    python3 tools/mapa/ver_item.py --assets /caminho/dos/assets \\
        --saida itens.png 1294 1295 1301

    python3 tools/mapa/ver_item.py --assets ... --saida portas.png --faixa 1209 1260

O outro jeito de descobrir id e perguntar ao proprio mapa: veja o
`ler_mapa.py`, que lista o que ja existe numa regiao.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parents[1] / "sprites"))
import tibia_assets as ta   # noqa: E402

VERDE = (86, 124, 54, 255)


class Assets:
    def __init__(self, pasta: str | Path):
        self.pasta = Path(pasta)
        self.catalogo = ta.Catalogo(self.pasta)
        nome = next(e for e in self.catalogo.entradas
                    if e.get("type") == "appearances")["file"]
        self.aparencias = ta.Appearances(self.pasta / nome)
        self._folhas: dict[str, Image.Image] = {}

    def sprite(self, spriteid: int) -> Image.Image | None:
        e = self.catalogo.folha_de(spriteid)
        if not e:
            return None
        if e["file"] not in self._folhas:
            self._folhas[e["file"]] = ta.ler_folha(self.pasta / e["file"])
        folha = self._folhas[e["file"]]
        larg, alt = ta.TAMANHOS[e["spritetype"]]
        por_linha = ta.LADO_FOLHA // larg
        i = spriteid - e["firstspriteid"]
        cx, cy = (i % por_linha) * larg, (i // por_linha) * alt
        return folha.crop((cx, cy, cx + larg, cy + alt))

    def item(self, item_id: int) -> Image.Image | None:
        ids = self.aparencias.sprite_ids("object", item_id)
        return self.sprite(ids[0]) if ids else None


def folha_de_contato(assets: Assets, ids, colunas=12, zoom=3) -> Image.Image:
    cel = 64 * zoom
    linhas = (len(ids) + colunas - 1) // colunas
    out = Image.new("RGB", (colunas * (cel + 6) + 6, linhas * (cel + 22) + 6),
                    (40, 40, 46))
    d = ImageDraw.Draw(out)
    for k, iid in enumerate(ids):
        cx = 6 + (k % colunas) * (cel + 6)
        cy = 6 + (k // colunas) * (cel + 22)
        d.text((cx + 2, cy), str(iid), fill=(232, 200, 120))
        s = assets.item(iid)
        if s is None:
            continue
        s = s.resize((s.width * zoom, s.height * zoom), Image.NEAREST)
        fundo = Image.new("RGBA", (cel, cel), VERDE)
        fundo.alpha_composite(s, (0, max(0, cel - s.height)))
        out.paste(fundo.convert("RGB"), (cx, cy + 16))
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("ids", nargs="*", type=int)
    p.add_argument("--assets", required=True)
    p.add_argument("--saida", required=True)
    p.add_argument("--faixa", nargs=2, type=int, metavar=("DE", "ATE"))
    p.add_argument("--colunas", type=int, default=12)
    p.add_argument("--zoom", type=int, default=3)
    args = p.parse_args()

    ids = list(args.ids)
    if args.faixa:
        ids += list(range(args.faixa[0], args.faixa[1] + 1))
    if not ids:
        raise SystemExit("passe ids ou --faixa")

    assets = Assets(args.assets)
    img = folha_de_contato(assets, ids, args.colunas, args.zoom)
    img.save(args.saida)
    print(f"{len(ids)} itens -> {args.saida} ({img.width}x{img.height})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
