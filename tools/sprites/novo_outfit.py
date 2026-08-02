#!/usr/bin/env python3
"""Injeta um outfit proprio nos assets do client 15.x.

Espera a pasta gerada pelo `folha_para_outfit.py`, com os arquivos
``<direcao>_<quadro>.png`` de 64x64 nas quatro direcoes:

    python3 tools/sprites/novo_outfit.py \\
        --assets /caminho/do/client/assets \\
        --dat-servidor data/items/appearances.dat \\
        --id 1950 tools/sprites/arte/mago

Um outfit tem dois frame groups: **parado** (um sprite por direcao) e
**andando** (um sprite por direcao e por fase da caminhada). A ordem dos
sprites e a que o client usa para indexar:

    indice = fase * 4 + direcao          direcao: 0 norte, 1 leste, 2 sul, 3 oeste

Ao contrario dos efeitos, o outfit **nao** leva bloco de animacao: quem
avanca as fases e o proprio deslocamento do personagem.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
import tibia_assets as ta   # noqa: E402
from novo_efeito import atualizar_dat, gravar_assets   # noqa: E402

# a ordem dos arquivos e a ordem do client
DIRECOES = ["norte", "leste", "sul", "oeste"]


def carregar(pasta: Path) -> tuple[list[Image.Image], int]:
    """Devolve os sprites na ordem do client e o numero de fases."""
    por_direcao = {}
    for d in DIRECOES:
        arquivos = sorted(pasta.glob(f"{d}_*.png"))
        if not arquivos:
            raise SystemExit(f"nao achei {d}_*.png em {pasta}")
        por_direcao[d] = [Image.open(a).convert("RGBA") for a in arquivos]

    fases = min(len(v) for v in por_direcao.values())
    if len(set(len(v) for v in por_direcao.values())) > 1:
        print(f"  aviso: direcoes com contagens diferentes, usando {fases} fases")

    for d, quadros in por_direcao.items():
        for q in quadros:
            if q.size != (64, 64):
                raise SystemExit(f"{d}: os sprites de outfit precisam ser 64x64")

    ordenados = []
    for fase in range(fases):
        for d in DIRECOES:
            ordenados.append(por_direcao[d][fase])
    return ordenados, fases


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("pasta", help="pasta com <direcao>_<quadro>.png")
    p.add_argument("--assets", required=True)
    p.add_argument("--dat-servidor")
    p.add_argument("--id", type=int, required=True, help="looktype do outfit")
    args = p.parse_args()

    pasta_assets = Path(args.assets)
    if not (pasta_assets / "catalog-content.json").is_file():
        raise SystemExit(f"{pasta_assets} nao parece uma pasta de assets")

    quadros, fases = carregar(Path(args.pasta))

    catalogo = ta.Catalogo(pasta_assets)
    entrada = next(e for e in catalogo.entradas if e.get("type") == "appearances")
    existentes = ta.Appearances(pasta_assets / entrada["file"]).ids("outfit")
    if args.id in existentes:
        raise SystemExit(f"o looktype {args.id} ja existe — livres a partir de "
                         f"{max(existentes) + 1}")

    # a mascara de cor vai vazia: o outfit sai com as cores que voce pintou,
    # sem responder ao seletor de cores do jogo
    vazio = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    print(f"outfit {args.id}: 4 direcoes x {fases} fases, 2 camadas "
          f"= {len(quadros) * 2} sprites")
    ids = gravar_assets(pasta_assets, quadros + [vazio], 64)
    id_mascara = ids[-1]

    andando = []
    for i in range(len(quadros)):
        andando += [ids[i], id_mascara]
    parado = andando[:8]                   # a primeira fase serve de pose parada

    def aplicar(ap: ta.Appearances):
        ap.adicionar_outfit(args.id, parado, andando, fases)

    atualizar_dat(pasta_assets, aplicar)

    if args.dat_servidor:
        ap = ta.Appearances(args.dat_servidor)
        aplicar(ap)
        ap.salvar()
        print(f"  appearances do servidor -> {args.dat_servidor}")

    print(f"\npronto. no Lua: creature:setOutfit({{lookType = {args.id}}})")
    print(f"      ou em data/XML/outfits.xml, para virar opcao no jogo")
    return 0


if __name__ == "__main__":
    sys.exit(main())
