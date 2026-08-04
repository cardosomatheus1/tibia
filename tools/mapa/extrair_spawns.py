#!/usr/bin/env python3
"""Extrai os spawns de uma regiao como posicoes RELATIVAS, em Lua.

Etapa 3 da spec de hunt instanciada. A instancia nao pode reusar os spawns XML
globais: eles tem coordenada absoluta e o SpawnsMonster::loadFromXML nao aceita
offset (spawn_monster.cpp:47). Entao o respawn vira Lua, e precisa da lista.

Sai relativo a origem do recorte, para `posicao real = origem do slot + isto`.

    python3 extrair_spawns.py <spawn.xml> x0 y0 x1 y1 z0 z1 --rebase X0 Y0
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

RE_BLOCO = re.compile(
    rb'<monster\s+centerx="(\d+)"\s+centery="(\d+)"\s+centerz="(\d+)"'
    rb'(?:\s+radius="(\d+)")?\s*>(.*?)</monster>', re.DOTALL)
RE_FILHO = re.compile(
    rb'<monster\s+name="([^"]+)"\s+x="(-?\d+)"\s+y="(-?\d+)"\s+z="(\d+)"'
    rb'(?:\s+spawntime="(\d+)")?')


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("xml")
    p.add_argument("coords", nargs=6, type=int,
                   metavar=("X0", "Y0", "X1", "Y1", "Z0", "Z1"))
    p.add_argument("--rebase", nargs=2, type=int, required=True,
                   metavar=("RX", "RY"))
    p.add_argument("--filtro", help="so monstros cujo nome contem isto")
    p.add_argument("--saida", help="arquivo Lua de saida")
    args = p.parse_args()

    x0, y0, x1, y1, z0, z1 = args.coords
    rx, ry = args.rebase
    dados = Path(args.xml).read_bytes()

    achados = []
    for m in RE_BLOCO.finditer(dados):
        cx, cy = int(m.group(1)), int(m.group(2))
        raio = int(m.group(4)) if m.group(4) else 1
        for f in RE_FILHO.finditer(m.group(5)):
            x = cx + int(f.group(2))
            y = cy + int(f.group(3))
            z = int(f.group(4))
            if not (x0 <= x <= x1 and y0 <= y <= y1 and z0 <= z <= z1):
                continue
            nome = f.group(1).decode(errors="replace")
            if args.filtro and args.filtro.lower() not in nome.lower():
                continue
            # spawntime vem em SEGUNDOS no XML
            st = int(f.group(5)) if f.group(5) else 60
            achados.append((nome, x - rx, y - ry, z, st, raio))

    if not achados:
        print("nenhum spawn na regiao", file=sys.stderr)
        return 1

    tipos = Counter(a[0] for a in achados)
    print(f"{len(achados)} spawns, {len(tipos)} tipos")
    for nome, n in tipos.most_common(20):
        print(f"  {n:>4}  {nome}")
    tempos = Counter(a[4] for a in achados)
    print(f"spawntime (s): {dict(tempos)}")

    achados.sort(key=lambda a: (a[3], a[2], a[1]))
    linhas = ["-- GERADO por tools/mapa/extrair_spawns.py -- nao editar a mao.",
              "-- Posicoes RELATIVAS a origem do recorte; some a origem do slot.",
              f"-- Origem do recorte: ({rx}, {ry}). Regiao: x {x0}-{x1} "
              f"y {y0}-{y1} z {z0}-{z1}.",
              f"-- {len(achados)} spawns.",
              "",
              "HuntInstanceSpawns = HuntInstanceSpawns or {}",
              "HuntInstanceSpawns.thais_cyclops = {"]
    for nome, x, y, z, st, raio in achados:
        linhas.append(f'\t{{ nome = "{nome}", x = {x}, y = {y}, z = {z}, '
                      f'respawnMs = {st * 1000} }},')
    linhas.append("}")
    texto = "\n".join(linhas) + "\n"

    if args.saida:
        Path(args.saida).write_text(texto, encoding="utf-8")
        print(f"\nescrito em {args.saida}")
    else:
        print("\n" + texto)
    return 0


if __name__ == "__main__":
    sys.exit(main())
