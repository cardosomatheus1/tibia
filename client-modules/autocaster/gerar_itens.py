#!/usr/bin/env python3
"""Gera a lista de potions e runas do client a partir do datapack do servidor.

Mesma ideia do gerar_spells.py: quem sabe o que existe de verdade é o servidor.
Sem esta lista, o slot de item do AutoCaster caía no seletor genérico do
client, que pede o **id numérico** e aceita qualquer coisa — dava para arrastar
uma espada para o slot de potion e o módulo tentava beber a espada.

Fontes:
  potions -> data/scripts/actions/items/potions.lua  (tabela `local potions`)
  runas   -> data/scripts/spells/conjuring/*.lua     (creature:conjureItem)
  nomes   -> data/items/items.xml

Uso (a partir da raiz do repositório):

    python3 client-modules/autocaster/gerar_itens.py
"""
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
ARQ_POTIONS = RAIZ / "data" / "scripts" / "actions" / "items" / "potions.lua"
PASTA_CONJURE = RAIZ / "data" / "scripts" / "spells" / "conjuring"
ARQ_ITEMS = RAIZ / "data" / "items" / "items.xml"
SAIDA = Path(__file__).parent / "itens_servidor.lua"


def nomes_de_itens():
    """id -> nome, lido do items.xml."""
    nomes = {}
    texto = ARQ_ITEMS.read_text(encoding="utf-8", errors="replace")
    for m in re.finditer(r'<item id="(\d+)"[^>]*name="([^"]+)"', texto):
        nomes[int(m.group(1))] = m.group(2)
    return nomes


def ler_potions(nomes):
    """Extrai a tabela `local potions = { [id] = {...} }`."""
    texto = ARQ_POTIONS.read_text(encoding="utf-8", errors="replace")
    ini = texto.find("local potions = {")
    if ini < 0:
        return []
    corpo = texto[ini:]

    potions = []
    # cada entrada começa com [id] = { ... na própria linha
    for m in re.finditer(r"^\t\[(\d+)\]\s*=\s*\{(.*)$", corpo, re.M):
        item_id, resto = int(m.group(1)), m.group(2)

        tem_hp = "health = {" in resto
        tem_mp = "mana = {" in resto
        if tem_hp and tem_mp:
            tipo = "ambos"
        elif tem_hp:
            tipo = "hp"
        elif tem_mp:
            tipo = "mp"
        else:
            # antidoto, berserk, mastermind... não servem para auto-heal
            tipo = "outro"

        mlvl = re.search(r"level\s*=\s*(\d+)", resto)
        potions.append({
            "id": item_id,
            "nome": nomes.get(item_id, "item %d" % item_id),
            "tipo": tipo,
            "level": int(mlvl.group(1)) if mlvl else 0,
        })

    potions.sort(key=lambda p: (p["tipo"], p["level"], p["id"]))
    return potions


def ler_runas(nomes):
    """Runas saem das magias de conjuração: conjureItem(branca, runa, qtd)."""
    if not PASTA_CONJURE.is_dir():
        return []

    runas, vistos = [], set()
    for caminho in sorted(PASTA_CONJURE.glob("*.lua")):
        c = caminho.read_text(encoding="utf-8", errors="replace")

        m = re.search(r"conjureItem\(\s*(\d+)\s*,\s*(\d+)", c)
        if not m:
            continue
        rune_id = int(m.group(2))
        if rune_id in vistos:
            continue

        nome = nomes.get(rune_id)
        if not nome or "rune" not in nome.lower():
            # conjuração de munição (flecha, spear) não é runa
            continue

        palavras = re.search(r'spell:words\(\s*"([^"]+)"', c)
        vistos.add(rune_id)
        runas.append({
            "id": rune_id,
            "nome": nome,
            "magia": palavras.group(1) if palavras else "",
        })

    runas.sort(key=lambda r: r["nome"])
    return runas


def main():
    faltando = [p for p in (ARQ_POTIONS, ARQ_ITEMS) if not p.is_file()]
    if faltando:
        for p in faltando:
            print("não encontrei %s" % p, file=sys.stderr)
        return 1

    nomes = nomes_de_itens()
    potions = ler_potions(nomes)
    runas = ler_runas(nomes)

    if not potions:
        print("nenhuma potion extraída — o formato de potions.lua mudou?", file=sys.stderr)
        return 1

    linhas = [
        "-- GERADO POR gerar_itens.py — não edite à mão.",
        "-- Fontes: data/scripts/actions/items/potions.lua, data/scripts/spells/",
        "-- conjuring/ e data/items/items.xml do próprio servidor.",
        "-- tipo da potion: hp, mp, ambos ou outro (outro = não serve para auto-heal)",
        "ItensServidor = {",
        "  potions = {",
    ]
    for p in potions:
        linhas.append(
            '    { id = %d, nome = "%s", tipo = "%s", level = %d },'
            % (p["id"], p["nome"].replace('"', ""), p["tipo"], p["level"])
        )
    linhas.append("  },")
    linhas.append("  runas = {")
    for r in runas:
        linhas.append(
            '    { id = %d, nome = "%s", magia = "%s" },'
            % (r["id"], r["nome"].replace('"', ""), r["magia"].replace('"', ""))
        )
    linhas.append("  },")
    linhas.append("}")
    SAIDA.write_text("\n".join(linhas) + "\n", encoding="utf-8")

    por_tipo = {}
    for p in potions:
        por_tipo[p["tipo"]] = por_tipo.get(p["tipo"], 0) + 1
    print("%d potions e %d runas -> %s" % (len(potions), len(runas), SAIDA.name))
    print("  potions por tipo: " + ", ".join(
        "%s %d" % (k, v) for k, v in sorted(por_tipo.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
