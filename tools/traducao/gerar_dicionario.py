#!/usr/bin/env python3
"""Transforma o catalogo JSON no dicionario Lua que o servidor carrega.

    python3 tools/traducao/gerar_dicionario.py

So entram as linhas que ja tem traducao. O que estiver em branco fica de
fora, e a camada de idioma devolve o texto em ingles — nunca uma frase
vazia no meio da conversa.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def escapar(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--catalogo", default="tools/traducao/catalogo.json")
    p.add_argument("--saida", default="data/npclib/npc_system/idiomas/pt_br.lua")
    p.add_argument("--codigo", default="pt")
    p.add_argument("--nome", default="Portugues")
    p.add_argument("--bandeira", default="br")
    args = p.parse_args()

    cat = json.loads(Path(args.catalogo).read_text())
    textos = {k: v["pt"] for k, v in cat.get("textos", {}).items()
              if v.get("pt") and not v.get("obsoleto")}
    palavras = {k: v["pt"] for k, v in cat.get("palavras", {}).items()
                if v.get("pt") and not v.get("obsoleto")}

    linhas = [
        "-- GERADO POR tools/traducao/gerar_dicionario.py — nao edite a mao.",
        "-- Para traduzir, mexa no catalogo e gere de novo:",
        "--   python3 tools/traducao/extrair.py         (recolhe o que falta)",
        "--   python3 tools/traducao/gerar_dicionario.py",
        "",
        'Idioma.registrar("%s", {' % escapar(args.codigo),
        '\tnome = "%s",' % escapar(args.nome),
        '\tbandeira = "%s",' % escapar(args.bandeira),
        "",
        "\t-- palavras que o jogador digita. A traducao vale nos dois sentidos:",
        "\t-- sai traduzida entre chaves e volta a ser o termo em ingles quando",
        "\t-- o jogador digita ou clica.",
        "\tpalavras = {",
    ]
    for k in sorted(palavras):
        linhas.append('\t\t["%s"] = "%s",' % (escapar(k), escapar(palavras[k])))
    linhas += ["\t},", "", "\t-- falas dos NPCs", "\ttextos = {"]
    for k in sorted(textos):
        linhas.append('\t\t["%s"] = "%s",' % (escapar(k), escapar(textos[k])))
    linhas += ["\t},", "})", ""]

    saida = Path(args.saida)
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text("\n".join(linhas))

    total = sum(v["n"] for v in cat.get("textos", {}).values() if not v.get("obsoleto"))
    feito = sum(v["n"] for v in cat.get("textos", {}).values()
                if v.get("pt") and not v.get("obsoleto"))
    print(f"{saida}: {len(palavras)} palavras, {len(textos)} textos")
    if total:
        print(f"  cobertura das falas ditas: {feito / total * 100:.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
