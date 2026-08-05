#!/usr/bin/env python3
"""Gera o atlas do mapa inteiro para o mapeador de hunts.

O mapa tem ~34000x34000 tiles em 16 andares. Renderizar isso num PNG unico e'
impossivel (1,1 bilhao de pixels). Mas o mapa e' ESPARSO: existem so ~1171 nos
de area de 256x256. Entao sai um PNG por no de area, 256x256 pixels, 1 pixel
por tile -- algumas centenas de KB no total, e o navegador carrega so os que
estao na tela.

Saida:

    atlas/
      tiles/<z>/<ax>_<ay>.png    um por no de area (ax, ay ja divididos por 256)
      dados.js                   areas, monstros e catalogo de hunts

dados.js e' .js e nao .json de proposito: o navegador bloqueia fetch() em
file://, mas <script src> funciona. Assim o mapeador roda com dois cliques,
sem servidor.

    python3 gerar_atlas.py <mapa.otbm> --saida atlas [--planilha x.xlsx]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from PIL import Image

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
sys.path.insert(0, str(AQUI))

from gerar_minimapa import ITEM_VAZIO, ler_atributos
from otbm import Mapa

LADO = 256

RE_BLOCO = re.compile(
    rb'<monster\s+centerx="(\d+)"\s+centery="(\d+)"\s+centerz="(\d+)"'
    rb'(?:\s+radius="(\d+)")?\s*>(.*?)</monster>', re.DOTALL)
RE_FILHO = re.compile(
    rb'<monster\s+name="([^"]+)"\s+x="(-?\d+)"\s+y="(-?\d+)"\s+z="(\d+)"')


def cor_rgb(c: int) -> tuple[int, int, int]:
    """Cor de 216 do automapa -> RGB."""
    return ((c // 36) * 51, ((c // 6) % 6) * 51, (c % 6) * 51)


def gerar_tiles(mapa: Mapa, attrs, destino: Path) -> list[dict]:
    """Um PNG por no de area. Devolve o indice."""
    indice = []
    bases = sorted(mapa.areas())
    print(f"{len(bases)} nos de area")

    # o mesmo (x,y,z) pode aparecer em varios nos: o editor reemite o cabecalho
    por_base = defaultdict(list)
    for b in bases:
        por_base[b].append(b)

    feitos = 0
    for base in sorted(por_base):
        bx, by, bz = base
        im = Image.new("RGBA", (LADO, LADO), (0, 0, 0, 0))
        px = im.load()
        vazio = True

        for t in mapa.tiles_da_area(base):
            cor = None
            # de cima para baixo, ignorando o que e' solto no chao -- mesmo
            # criterio do Tile::getMinimapColorByte
            for iid in [i for i, _, _ in t.itens][::-1] + ([t.chao] if t.chao else []):
                it = attrs.get(iid, ITEM_VAZIO)
                if it.estrutura and it.cor is not None:
                    cor = it.cor
                    break
            if cor is None:
                continue
            r, g, b = cor_rgb(cor)
            px[t.x - bx, t.y - by] = (r, g, b, 255)
            vazio = False

        mapa.esquecer_area(base)   # senao a memoria cresce ate estourar

        if vazio:
            continue
        pasta = destino / "tiles" / str(bz)
        pasta.mkdir(parents=True, exist_ok=True)
        im.save(pasta / f"{bx // LADO}_{by // LADO}.png", optimize=True)
        indice.append({"z": bz, "ax": bx // LADO, "ay": by // LADO})
        feitos += 1
        if feitos % 100 == 0:
            print(f"  {feitos} tiles gerados")

    print(f"{feitos} PNGs de area")
    return indice


def ler_monstros(caminho: Path) -> dict:
    """{ "z": [[x, y, nome], ...] } -- agrupado por andar para o viewer."""
    if not caminho.exists():
        print(f"AVISO: {caminho} nao existe, sem monstros no atlas")
        return {}
    dados = caminho.read_bytes()
    por_andar = defaultdict(list)
    nomes: dict[str, int] = {}
    lista_nomes: list[str] = []
    total = 0
    for m in RE_BLOCO.finditer(dados):
        cx, cy = int(m.group(1)), int(m.group(2))
        for f in RE_FILHO.finditer(m.group(5)):
            nome = f.group(1).decode(errors="replace")
            if nome not in nomes:
                nomes[nome] = len(lista_nomes)
                lista_nomes.append(nome)
            x, y, z = cx + int(f.group(2)), cy + int(f.group(3)), int(f.group(4))
            # indice do nome em vez do nome: o arquivo cai para menos da metade
            por_andar[z].append([x, y, nomes[nome]])
            total += 1
    print(f"{total} spawns, {len(lista_nomes)} tipos")
    return {"nomes": lista_nomes,
            "porAndar": {str(k): v for k, v in sorted(por_andar.items())}}


def ler_planilha(caminho: Path) -> list[dict]:
    """ID e nome de cada hunt, da aba Catalogo_Hunts."""
    if not caminho or not caminho.exists():
        return []
    try:
        import openpyxl
    except ImportError:
        print("AVISO: openpyxl ausente, catalogo de hunts vazio")
        return []
    wb = openpyxl.load_workbook(caminho, read_only=True, data_only=True)
    if "Catalogo_Hunts" not in wb.sheetnames:
        print("AVISO: aba Catalogo_Hunts nao encontrada")
        return []
    ws = wb["Catalogo_Hunts"]
    hunts, cabecalho = [], None
    for row in ws.iter_rows(values_only=True):
        if cabecalho is None:
            if row and row[0] == "ID":
                cabecalho = row
            continue
        if not row or row[0] is None:
            continue
        try:
            hid = int(row[0])
        except (TypeError, ValueError):
            continue
        hunts.append({
            "id": hid,
            "nome": str(row[1]) if len(row) > 1 and row[1] else f"hunt {hid}",
            "classe": str(row[27]) if len(row) > 27 and row[27] else "",
            "prioridade": str(row[29]) if len(row) > 29 and row[29] else "",
        })
    print(f"{len(hunts)} hunts no catalogo")
    return hunts


# A hunt dos ciclopes, ja mapeada. Serve de exemplo e de conferencia: abrir o
# mapeador e ver o desenho certo prova que o atlas e as coordenadas batem.
CICLOPES = {
    "id": 0,
    "nome": "Ciclopes de Thais (ja mapeada)",
    "obelisco": {"x": 32454, "y": 32116, "z": 7},
    "inicio": {"x": 32464, "y": 32085, "z": 7},
    "limites": {},          # preenchido abaixo
}


def limites_ciclopes() -> dict:
    """Retangulo da hunt, por andar, como o catalogo.lua define hoje."""
    x0, y0 = 32384 + 16, 32016 + 16
    x1, y1 = 32384 + 152, 32016 + 104
    saida = {}
    for z in (5, 6, 7, 8, 9):
        saida[str(z)] = [[x, y] for x in range(x0, x1 + 1)
                         for y in range(y0, y1 + 1)]
    return saida


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("mapa")
    p.add_argument("--saida", default="atlas")
    p.add_argument("--spawns",
                   default=str(RAIZ / "data-otservbr-global/world/otservbr-monster.xml"))
    p.add_argument("--planilha")
    p.add_argument("--dat", default=str(RAIZ / "data/items/appearances.dat"))
    args = p.parse_args()

    destino = Path(args.saida)
    destino.mkdir(parents=True, exist_ok=True)

    print("lendo aparencias...")
    attrs = ler_atributos(Path(args.dat))

    print("lendo mapa...")
    m = Mapa(args.mapa)
    indice = gerar_tiles(m, attrs, destino)
    del m

    monstros = ler_monstros(Path(args.spawns))
    hunts = ler_planilha(Path(args.planilha) if args.planilha else None)

    ciclopes = dict(CICLOPES)
    ciclopes["limites"] = limites_ciclopes()

    js = destino / "dados.js"
    with js.open("w", encoding="utf-8") as f:
        f.write("// GERADO por tools/mapa/gerar_atlas.py -- nao editar a mao.\n")
        f.write(f"const ATLAS_AREAS = {json.dumps(indice, separators=(',', ':'))};\n")
        f.write(f"const ATLAS_MONSTROS = {json.dumps(monstros, separators=(',', ':'))};\n")
        f.write(f"const ATLAS_HUNTS = {json.dumps(hunts, ensure_ascii=False, separators=(',', ':'))};\n")
        f.write(f"const ATLAS_EXEMPLO = {json.dumps(ciclopes, ensure_ascii=False, separators=(',', ':'))};\n")

    mb = js.stat().st_size / 1024 / 1024
    print(f"\n{destino}/dados.js  ({mb:.1f} MB)")
    print(f"{destino}/tiles/     ({len(indice)} PNGs)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
