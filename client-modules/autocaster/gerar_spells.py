#!/usr/bin/env python3
"""Gera a lista de magias do client a partir dos scripts do servidor.

O SpellInfo que vem no OTClient é uma tabela fixa e desatualizada: não tem
as vocações novas (Monk) nem as magias adicionadas depois. Como o servidor
é quem define o que existe de verdade, este script lê
`data/scripts/spells/**/*.lua` e gera `spells_servidor.lua`, que o módulo
carrega no lugar da tabela do client.

Uso (a partir da raiz do repositório):

    python3 client-modules/autocaster/gerar_spells.py

Rode de novo sempre que adicionar ou mudar magias no datapack.
"""
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
PASTA_SPELLS = RAIZ / "data" / "scripts" / "spells"
SAIDA = Path(__file__).parent / "spells_servidor.lua"

# grupos que interessam ao semibot (o resto é conjuração, party, casa...)
GRUPOS = {"attack": 1, "healing": 2, "support": 3}


def texto_de(padrao, conteudo):
    m = re.search(padrao, conteudo)
    return m.group(1) if m else None


def numero_de(padrao, conteudo):
    m = re.search(padrao, conteudo)
    if not m:
        return None
    try:
        # aceita expressões simples do tipo "4 * 1000"
        return int(eval(m.group(1), {"__builtins__": {}}, {}))
    except Exception:
        return None


def ler_magia(caminho):
    c = caminho.read_text(encoding="utf-8", errors="replace")

    nome = texto_de(r'spell:name\(\s*"([^"]+)"', c)
    palavras = texto_de(r'spell:words\(\s*"([^"]+)"', c)
    if not nome or not palavras:
        return None
    # magias de monstro usam "###123" como palavra
    if palavras.startswith("###"):
        return None

    grupo_txt = texto_de(r'spell:group\(\s*"([^"]+)"', c)
    # se o script não declara, usa a pasta (attack/healing/support/...)
    if not grupo_txt:
        grupo_txt = caminho.parent.name
    grupo = GRUPOS.get(grupo_txt)
    if not grupo:
        return None

    vocs = []
    m = re.search(r"spell:vocation\(([^)]*)\)", c, re.S)
    if m:
        for v in re.findall(r'"([^"]+)"', m.group(1)):
            vocs.append(v.split(";")[0].strip().lower())

    return {
        "nome": nome,
        "palavras": palavras,
        "grupo": grupo,
        "level": numero_de(r"spell:level\(\s*([0-9*+ ]+)\s*\)", c) or 0,
        "mana": numero_de(r"spell:mana\(\s*([0-9*+ ]+)\s*\)", c) or 0,
        "vocacoes": vocs,
    }


def main():
    if not PASTA_SPELLS.is_dir():
        print(f"não encontrei {PASTA_SPELLS}", file=sys.stderr)
        return 1

    magias = []
    for caminho in sorted(PASTA_SPELLS.rglob("*.lua")):
        try:
            m = ler_magia(caminho)
        except Exception as e:
            print(f"  aviso: {caminho.name}: {e}", file=sys.stderr)
            continue
        if m:
            magias.append(m)

    magias.sort(key=lambda m: (m["grupo"], m["level"], m["nome"]))

    linhas = [
        "-- GERADO POR gerar_spells.py — não edite à mão.",
        "-- Fonte: data/scripts/spells/ do próprio servidor.",
        "-- grupo: 1 = ataque, 2 = cura, 3 = suporte",
        "SpellsServidor = {",
    ]
    for m in magias:
        vocs = ", ".join('"%s"' % v for v in m["vocacoes"])
        linhas.append(
            '  { nome = "%s", palavras = "%s", grupo = %d, level = %d, mana = %d, vocacoes = { %s } },'
            % (m["nome"].replace('"', ""), m["palavras"].replace('"', ""),
               m["grupo"], m["level"], m["mana"], vocs)
        )
    linhas.append("}")
    SAIDA.write_text("\n".join(linhas) + "\n", encoding="utf-8")

    por_grupo = {}
    vocacoes = set()
    for m in magias:
        por_grupo[m["grupo"]] = por_grupo.get(m["grupo"], 0) + 1
        vocacoes.update(m["vocacoes"])
    print(f"{len(magias)} magias -> {SAIDA.name}")
    print(f"  ataque {por_grupo.get(1,0)} | cura {por_grupo.get(2,0)} | suporte {por_grupo.get(3,0)}")
    print(f"  vocações encontradas: {', '.join(sorted(vocacoes))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
