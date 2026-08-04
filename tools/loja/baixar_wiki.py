#!/usr/bin/env python3
"""Baixa da TibiaWiki os ícones de loja que não têm sprite no jogo.

O gerar_icones.py desenha ~94% do catálogo a partir do appearances.dat. O que
sobra são ícones de categoria e de ofertas de sistema (Premium Time, Prey Slot,
Blessings, XP Boost): não são objeto nem criatura, então não existe sprite deles
no jogo. Esses só podem vir de fora.

A TibiaWiki (tibia.fandom.com) hospeda essas imagens abertamente e expõe uma API
pública que devolve a URL do arquivo — sem bloqueio de bot, ao contrário da CDN
da CipSoft. É de lá que este script busca.

O nome do arquivo no catálogo quase sempre bate com o da wiki trocando "_" por
espaço (XP_Boost.png -> "File:XP Boost.png"). Quando não bate, o script tenta
algumas variações antes de desistir, e lista o que não achou.

Uso:

    python3 tools/loja/baixar_wiki.py --saida tools/loja/saida --faltantes lista.txt
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

API = "https://tibia.fandom.com/api.php"
UA = "Mozilla/5.0 (compatible; icon-fetch/1.0)"
LADO = 64


def _pedir(url: str, binario: bool = False):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read() if binario else json.loads(r.read().decode("utf-8"))


def url_do_arquivo(nome_wiki: str) -> str | None:
    """Consulta a API e devolve a URL direta da imagem, ou None."""
    consulta = urllib.parse.urlencode({
        "action": "query",
        "titles": f"File:{nome_wiki}",
        "prop": "imageinfo",
        "iiprop": "url",
        "format": "json",
    })
    try:
        dados = _pedir(f"{API}?{consulta}")
    except Exception:
        return None
    paginas = dados.get("query", {}).get("pages", {})
    for _, pagina in paginas.items():
        if "missing" in pagina:
            continue
        info = pagina.get("imageinfo")
        if info:
            return info[0].get("url")
    return None


def variacoes(nome_png: str):
    """Nomes prováveis na wiki para um ícone do catálogo."""
    base = nome_png[:-4]                      # tira .png
    yield base.replace("_", " ") + ".png"     # XP_Boost -> XP Boost
    yield base + ".png"                       # exato
    if base.startswith("Category_"):
        # Category_UsefulThings -> "Useful Things"
        resto = base[len("Category_"):]
        espacado = "".join(
            (" " + c if i and c.isupper() and not resto[i - 1].isupper() else c)
            for i, c in enumerate(resto)
        )
        yield espacado.replace("_", " ").strip() + ".png"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--saida", required=True, help="pasta dos ícones (será complementada)")
    p.add_argument("--faltantes", required=True,
                   help="arquivo com um nome de PNG por linha")
    p.add_argument("--pausa", type=float, default=0.4,
                   help="segundos entre requisições, para não martelar a wiki")
    args = p.parse_args()

    saida = Path(args.saida)
    saida.mkdir(parents=True, exist_ok=True)
    nomes = [l.strip() for l in Path(args.faltantes).read_text(encoding="utf-8").splitlines()
             if l.strip()]

    baixados, nao_achados = 0, []
    for i, nome in enumerate(nomes, 1):
        url = None
        for tentativa in variacoes(nome):
            url = url_do_arquivo(tentativa)
            if url:
                break
            time.sleep(args.pausa)

        if not url:
            nao_achados.append(nome)
            print(f"  [{i}/{len(nomes)}] {nome}: nao achado")
            continue

        try:
            bruto = _pedir(url, binario=True)
            img = Image.open(io.BytesIO(bruto)).convert("RGBA")
            # a wiki serve em WebP; normaliza para PNG 64x64 como a loja espera
            if img.size != (LADO, LADO):
                tela = Image.new("RGBA", (LADO, LADO), (0, 0, 0, 0))
                img.thumbnail((LADO, LADO), Image.LANCZOS)
                tela.alpha_composite(img, ((LADO - img.width) // 2,
                                           (LADO - img.height) // 2))
                img = tela
            img.save(saida / nome)
            baixados += 1
            print(f"  [{i}/{len(nomes)}] {nome}: ok")
        except Exception as e:
            nao_achados.append(nome)
            print(f"  [{i}/{len(nomes)}] {nome}: falhou ({e})")

        time.sleep(args.pausa)

    print(f"\nbaixados: {baixados} de {len(nomes)}")
    if nao_achados:
        print(f"sem imagem na wiki: {len(nao_achados)}")
        for n in nao_achados:
            print(f"   {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
