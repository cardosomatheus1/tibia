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


import re


def tolerante(texto: str) -> str:
    """Mesma normalizacao do Idioma.chave_tolerante, do lado do Lua."""
    t = re.sub(r"\s+", " ", texto.lower())
    return re.sub(r"[^\w{}|]+$", "", re.sub(r"^[^\w{}|]+", "", t))


# O extrator pega o texto **como esta escrito no .lua**, com as barras
# invertidas cruas. O que chega no `Npc:say` e o que o Lua ja resolveu: a
# frase quebrada em tres linhas com `\z` chega inteira, numa linha so.
# Sem desfazer isso aqui, a chave do dicionario nunca casaria com a fala —
# 116 frases sairiam em ingles sem ninguem entender por que.
ESCAPES_LUA = {"n": "\n", "t": "\t", "r": "\r", "a": "\a", "b": "\b",
               "f": "\f", "v": "\v", "\\": "\\", '"': '"', "'": "'"}


def como_o_lua_le(texto: str) -> str:
    saida, i = [], 0
    while i < len(texto):
        c = texto[i]
        if c != "\\" or i + 1 >= len(texto):
            saida.append(c)
            i += 1
            continue
        prox = texto[i + 1]
        if prox == "z":
            # `\z` engole todo o espaco em branco que vem depois
            i += 2
            while i < len(texto) and texto[i].isspace():
                i += 1
        elif prox in ESCAPES_LUA:
            saida.append(ESCAPES_LUA[prox])
            i += 2
        else:
            saida.append(c)
            i += 1
    return "".join(saida)


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
    # Traducao feita a mao nunca e descartada, nem a de frase que sumiu do
    # datapack: guardar custa uma linha e, se a frase voltar, ja funciona.
    # Descartar custa o trabalho de uma pessoa.
    textos = {como_o_lua_le(k): v["pt"]
              for k, v in cat.get("textos", {}).items() if v.get("pt")}
    palavras = {k: v["pt"] for k, v in cat.get("palavras", {}).items() if v.get("pt")}
    apelidos = {k: v["pt"] for k, v in cat.get("apelidos", {}).items() if v.get("pt")}

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
    linhas += [
        "\t},",
        "",
        "\t-- nome de magia, cidade e bencao: valem so na entrada. O jogador",
        "\t-- pode dizer o nome em portugues, mas o NPC continua dizendo o",
        "\t-- original, que e como aparece na spellbook, na hotkey e no mapa.",
        "\tapelidos = {",
    ]
    for k in sorted(apelidos):
        linhas.append('\t\t["%s"] = "%s",' % (escapar(k), escapar(apelidos[k])))
    linhas += ["\t},", "", "\t-- falas dos NPCs", "\ttextos = {"]
    for k in sorted(textos):
        linhas.append('\t\t["%s"] = "%s",' % (escapar(k), escapar(textos[k])))
    linhas += [
        "\t},",
        "",
        "\t-- Mesma traducao indexada por chave tolerante (minuscula, espaco",
        "\t-- colapsado, pontuacao de borda fora). E o que impede a traducao de",
        "\t-- se perder calada quando o upstream mexe numa virgula.",
        "\ttolerantes = {",
    ]
    vistas = {}
    for k in sorted(textos):
        chave = tolerante(k)
        if chave and chave != k and chave not in vistas:
            vistas[chave] = textos[k]
            linhas.append('\t\t["%s"] = "%s",' % (escapar(chave), escapar(textos[k])))
    linhas += ["\t},", "})", ""]

    saida = Path(args.saida)
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text("\n".join(linhas))

    total = sum(v["n"] for v in cat.get("textos", {}).values() if not v.get("obsoleto"))
    feito = sum(v["n"] for v in cat.get("textos", {}).values()
                if v.get("pt") and not v.get("obsoleto"))
    print(f"{saida}: {len(palavras)} palavras, {len(apelidos)} apelidos, "
          f"{len(textos)} textos")
    if total:
        print(f"  cobertura das falas ditas: {feito / total * 100:.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
