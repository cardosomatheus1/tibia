#!/usr/bin/env python3
"""Monta os ícones de categoria a partir das ofertas da própria seção.

Os Category_*.png são arte exclusiva da loja: não existem no appearances.dat
(não são objeto nem criatura) e a TibiaWiki também não os tem. Em vez de deixar
um quadrado vazio no menu, cada categoria passa a mostrar um item que de fato
pertence a ela — a seção "Camas" mostra uma cama, "Poções" mostra uma poção.

Como funciona: cada arquivo do catálogo declara o ícone da categoria no topo e
as ofertas logo abaixo. Este script casa um com o outro e copia o primeiro
ícone de oferta que já tenha desenho.

Uso (depois do gerar_icones.py):

    python3 tools/loja/icones_categoria.py --saida tools/loja/saida
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

from PIL import Image

RAIZ = Path(__file__).resolve().parents[2]
CATALOGO = RAIZ / "data" / "modules" / "scripts" / "gamestore" / "catalog"


def e_placeholder(caminho: Path, referencia: bytes | None) -> bool:
    """True se a imagem for o quadrado neutro (ou não existir)."""
    if not caminho.is_file():
        return True
    if referencia is None:
        return False
    try:
        return Image.open(caminho).convert("RGBA").tobytes() == referencia
    except Exception:
        return True


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--saida", required=True, help="pasta com os ícones já gerados")
    args = p.parse_args()

    saida = Path(args.saida)

    # a assinatura do placeholder sai de um que sabidamente não tem desenho
    referencia = None
    for candidato in saida.glob("Category_*.png"):
        try:
            referencia = Image.open(candidato).convert("RGBA").tobytes()
            break
        except Exception:
            continue

    trocados, sem_jeito = 0, []

    for arquivo in sorted(CATALOGO.glob("*.lua")):
        texto = arquivo.read_text(encoding="utf-8", errors="replace")

        # o ícone da categoria é o primeiro "icons = { ... }" do arquivo,
        # antes de qualquer bloco de oferta
        cabecalho = texto.split("offers", 1)[0]
        cat = re.search(r'"([A-Za-z0-9_. -]+\.png)"', cabecalho)
        if not cat:
            continue
        nome_cat = cat.group(1)
        destino = saida / nome_cat
        if not e_placeholder(destino, referencia):
            continue                      # já tem desenho, não mexe

        # procura, entre as ofertas do MESMO arquivo, a primeira com desenho
        escolhido = None
        for nome in re.findall(r'"([A-Za-z0-9_. -]+\.png)"', texto):
            if nome == nome_cat:
                continue
            candidato = saida / nome
            if not e_placeholder(candidato, referencia):
                escolhido = candidato
                break

        if escolhido:
            shutil.copyfile(escolhido, destino)
            trocados += 1
            print(f"  {nome_cat}  <-  {escolhido.name}")
        else:
            sem_jeito.append(nome_cat)

    print(f"\ncategorias com ícone: {trocados}")
    if sem_jeito:
        print(f"seguem neutras: {len(sem_jeito)}")
        for n in sem_jeito:
            print(f"   {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
