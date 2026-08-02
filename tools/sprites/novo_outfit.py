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

# as quatro cores que o client procura na mascara, na ordem em que ele as
# multiplica: cabeca, corpo, pernas, pes
MASCARA = {
    "cabeca": (255, 255, 0),
    "corpo": (255, 0, 0),
    "pernas": (0, 255, 0),
    "pes": (0, 0, 255),
}
# faixas verticais do personagem, em fracao da altura, de cima pra baixo
FAIXAS = (("cabeca", 0.00, 0.34), ("corpo", 0.34, 0.60),
          ("pernas", 0.60, 0.88), ("pes", 0.88, 1.01))


def _matiz(r, g, b):
    """Matiz em graus, ou None se o pixel for cinza demais para ter cor."""
    maior, menor = max(r, g, b), min(r, g, b)
    if maior - menor < 22 or maior < 44:
        return None
    d = maior - menor
    if maior == r:
        h = ((g - b) / d) % 6
    elif maior == g:
        h = (b - r) / d + 2
    else:
        h = (r - g) / d + 4
    return h * 60


def matiz_dominante(quadros) -> float:
    """O matiz que mais aparece — quase sempre o da roupa do personagem."""
    conta = {}
    for q in quadros:
        px = q.load()
        for y in range(q.height):
            for x in range(q.width):
                r, g, b, a = px[x, y]
                if a == 0:
                    continue
                h = _matiz(r, g, b)
                if h is not None:
                    conta[round(h / 10) * 10] = conta.get(round(h / 10) * 10, 0) + 1
    return max(conta, key=conta.get) if conta else 0.0


def template_de_cor(img: Image.Image, matiz_alvo: float, tolerancia: float = 15):
    """Separa o sprite em base cinza + mascara de cor.

    O client multiplica a cor escolhida pelo jogador sobre os pixels
    marcados na mascara, entao a base precisa entregar esses pixels em tom
    de cinza — a cor sai do produto.

    So entra na mascara o que estiver perto do matiz da roupa. O resto
    (cajado, chama, pele, filete dourado) fica de fora e mantem a cor
    original, que e o que se espera: trocar a cor do personagem nao deve
    trocar a cor da tocha.
    """
    base = img.copy()
    mascara = Image.new("RGBA", img.size, (0, 0, 0, 0))
    bp, mp, op = base.load(), mascara.load(), img.load()

    caixa = img.getbbox()
    if not caixa:
        return base, mascara
    topo, alt = caixa[1], caixa[3] - caixa[1]

    for y in range(img.height):
        for x in range(img.width):
            r, g, b, a = op[x, y]
            if a == 0:
                continue
            h = _matiz(r, g, b)
            if h is None:
                continue
            dist = abs((h - matiz_alvo + 180) % 360 - 180)
            if dist > tolerancia:
                continue                      # nao e a roupa: deixa como esta
            fracao = (y - topo) / alt
            for nome, ini, fim in FAIXAS:
                if ini <= fracao < fim:
                    mp[x, y] = MASCARA[nome] + (255,)
                    break
            # a base guarda so o brilho; a cor vem da multiplicacao
            luz = int(0.30 * r + 0.59 * g + 0.11 * b)
            luz = min(255, int(luz * 1.45) + 55)   # clareia, senao sai escuro
            bp[x, y] = (luz, luz, luz, a)
    return base, mascara


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
    p.add_argument("--colorizavel", action="store_true",
                   help="gera a mascara de cor: o outfit passa a responder ao "
                        "seletor de cores do jogo (base vira tom de cinza)")
    p.add_argument("--matiz", type=float,
                   help="matiz da roupa em graus (0 vermelho, 120 verde, 240 azul). "
                        "Sem isso, usa o matiz que mais aparece no sprite")
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

    print(f"outfit {args.id}: 4 direcoes x {fases} fases, 2 camadas "
          f"= {len(quadros) * 2} sprites")

    if args.colorizavel:
        # base em cinza + mascara marcando cabeca/corpo/pernas/pes: o outfit
        # passa a responder ao seletor de cores do jogo
        matiz = args.matiz if args.matiz is not None else matiz_dominante(quadros)
        print(f"  matiz da roupa: {matiz:.0f} graus")
        pares = [template_de_cor(q, matiz) for q in quadros]
        todos = [im for par in pares for im in par]
        ids = gravar_assets(pasta_assets, todos, 64)
        andando = list(ids)                # ja sai intercalado base, mascara
        print("  colorizavel: a cor sai do seletor do jogo")
    else:
        # mascara vazia: o outfit sai com as cores que voce pintou e as
        # passadas de cor do client nao pintam nada
        vazio = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
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
