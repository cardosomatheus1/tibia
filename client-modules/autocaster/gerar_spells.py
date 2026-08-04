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

# SpellGroup_t completo, de src/creatures/creatures_definitions.hpp. Precisamos
# dele porque o servidor manda o cooldown de grupo por id numérico (pacote
# 0xA5), e uma magia pode pertencer a dois grupos ao mesmo tempo — por exemplo
# spell:group("attack", "focus").
GRUPOS_CD = {
    "none": 0,
    "attack": 1,
    "healing": 2,
    "support": 3,
    "special": 4,
    "conjure": 5,
    "crippling": 6,
    "focus": 7,
    "ultimatestrikes": 8,
    "burstsofnature": 9,
    "greatbeams": 10,
    "virtue": 11,
}

# Bits de PlayerStates (modules/gamelib/player.lua do otclient) por tipo de
# condição. Serve para saber se um buff AINDA está ativo sem depender só do
# cronômetro. Só algumas condições têm bit; CONDITION_ATTRIBUTES (utito tempo e
# afins) não tem nenhum, e para essas a duração é a única pista disponível.
BIT_ESTADO = {
    "CONDITION_HASTE": 64,
    "CONDITION_MANASHIELD": 16,
    "CONDITION_PARALYZE": 32,
    "CONDITION_DRUNK": 8,
}


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

    # Buff: duração do efeito, que NÃO é o cooldown. utani hur tem cooldown de
    # 2 s e dura 30 s — recastar pelo cooldown desperdiça mana e trava o ciclo.
    # Pega a condição da variável chamada exatamente "condition", que é o padrão
    # do datapack; assim não confunde com blocos auxiliares (ex.: FamiliarHaste).
    # Buffs de familiar não contam: o FamiliarHaste dura 33 s e é do bicho, não
    # do jogador — foi exatamente essa confusão que fez o utani hur parecer 33 s.
    # Fora isso a condição pode estar indentada (magic_shield declara dentro de
    # uma função), então não dá para ancorar no início da linha.
    duracao, bit_estado = 0, 0
    for mc in re.finditer(r"local (\w+) = Condition\((CONDITION_[A-Z_]+)\)", c):
        var, tipo = mc.group(1), mc.group(2)
        if "familiar" in var.lower():
            continue
        ticks = numero_de(
            r"%s:setParameter\(\s*CONDITION_PARAM_TICKS\s*,\s*([0-9*+ ]+)\s*\)" % re.escape(var),
            c,
        )
        if ticks is None:
            # alguns scripts usam uma constante local (ex.: spellDuration)
            mv = re.search(
                r"%s:setParameter\(\s*CONDITION_PARAM_TICKS\s*,\s*(\w+)\s*\)" % re.escape(var), c
            )
            if mv:
                ticks = numero_de(
                    r"local %s\s*=\s*([0-9*+ ]+)" % re.escape(mv.group(1)), c
                )
        if ticks:
            # a primeira condição com duração é a que vale; as demais são
            # camadas extras da mesma magia (skill + regeneração, por exemplo)
            duracao = duracao or ticks
            bit_estado = bit_estado or BIT_ESTADO.get(tipo, 0)

    # todos os grupos declarados, para casar com o cooldown de grupo (0xA5)
    grupos_cd = []
    mg = re.search(r"spell:group\(([^)]*)\)", c)
    if mg:
        for g in re.findall(r'"([^"]+)"', mg.group(1)):
            n = GRUPOS_CD.get(g.strip().lower())
            if n is not None and n not in grupos_cd:
                grupos_cd.append(n)
    if not grupos_cd:
        grupos_cd = [grupo]

    vocs = []
    m = re.search(r"spell:vocation\(([^)]*)\)", c, re.S)
    if m:
        for v in re.findall(r'"([^"]+)"', m.group(1)):
            vocs.append(v.split(";")[0].strip().lower())

    return {
        "nome": nome,
        "palavras": palavras,
        "grupo": grupo,
        "gruposCd": grupos_cd,
        # id do spell: é o que vem no pacote 0xA4 (cooldown individual)
        "id": numero_de(r"spell:id\(\s*([0-9*+ ]+)\s*\)", c) or 0,
        "level": numero_de(r"spell:level\(\s*([0-9*+ ]+)\s*\)", c) or 0,
        "mana": numero_de(r"spell:mana\(\s*([0-9*+ ]+)\s*\)", c) or 0,
        "cd": numero_de(r"spell:cooldown\(\s*([0-9*+ ]+)\s*\)", c) or 0,
        "cdGrupo": numero_de(r"spell:groupCooldown\(\s*([0-9*+ ]+)\s*\)", c) or 0,
        "duracao": duracao,
        "bitEstado": bit_estado,
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
        "-- grupo: 1 = ataque, 2 = cura, 3 = suporte (categoria da interface)",
        "-- id/gruposCd/cd/cdGrupo: usados para saber o cooldown REAL do servidor",
        "-- (pacotes 0xA4 por magia e 0xA5 por grupo).",
        "SpellsServidor = {",
    ]
    for m in magias:
        vocs = ", ".join('"%s"' % v for v in m["vocacoes"])
        gcd = ", ".join(str(g) for g in m["gruposCd"])
        linhas.append(
            '  { nome = "%s", palavras = "%s", grupo = %d, id = %d, level = %d, mana = %d, '
            'cd = %d, cdGrupo = %d, duracao = %d, bitEstado = %d, gruposCd = { %s }, vocacoes = { %s } },'
            % (m["nome"].replace('"', ""), m["palavras"].replace('"', ""),
               m["grupo"], m["id"], m["level"], m["mana"],
               m["cd"], m["cdGrupo"], m["duracao"], m["bitEstado"], gcd, vocs)
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
