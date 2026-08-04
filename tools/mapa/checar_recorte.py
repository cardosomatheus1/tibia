#!/usr/bin/env python3
"""Diz TUDO que existe dentro de um retangulo do mapa, alem do que se espera.

Serve pra Etapa 0 da spec de hunt instanciada: antes de recortar o chunk, saber
o que vai junto sem querer. Duplicar uma copia da hunt N vezes duplica junto
qualquer NPC, casa ou spawn alheio que esteja dentro do recorte -- e a spec
proibe explicitamente casas, quest chests e unique IDs globais na instancia.

    python3 checar_recorte.py <dir do world> x0 y0 x1 y1 [z0 z1]
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

# Formato OTServBR: o bloco externo tambem se chama <monster>/<npc>, e os
# filhos sao self-closing.
RE_BLOCO = re.compile(
    rb'<(monster|npc)\s+centerx="(\d+)"\s+centery="(\d+)"\s+centerz="(\d+)"'
    rb'(?:\s+radius="(\d+)")?\s*>(.*?)</\1>',
    re.DOTALL)
RE_FILHO = re.compile(
    rb'<(?:monster|npc)\s+name="([^"]+)"\s+x="(-?\d+)"\s+y="(-?\d+)"\s+z="(\d+)"')
RE_CASA = re.compile(
    rb'<house[^>]*name="([^"]+)"[^>]*entryx="(\d+)"\s+entryy="(\d+)"\s+'
    rb'entryz="(\d+)"', re.DOTALL)


def dentro(x, y, z, cx0, cy0, cx1, cy1, cz0, cz1) -> bool:
    return cx0 <= x <= cx1 and cy0 <= y <= cy1 and cz0 <= z <= cz1


def main() -> int:
    if len(sys.argv) < 6:
        print(__doc__)
        return 2

    base = Path(sys.argv[1])
    x0, y0, x1, y1 = (int(v) for v in sys.argv[2:6])
    z0 = int(sys.argv[6]) if len(sys.argv) > 6 else 0
    z1 = int(sys.argv[7]) if len(sys.argv) > 7 else 15

    print(f"recorte: x {x0}-{x1}  y {y0}-{y1}  z {z0}-{z1}")
    print(f"         {x1 - x0 + 1} x {y1 - y0 + 1} tiles, {z1 - z0 + 1} andares\n")

    # ---- criaturas (monstros e npcs) ----
    for arquivo, rotulo in (("otservbr-monster.xml", "MONSTROS"),
                            ("otservbr-npc.xml", "NPCS")):
        caminho = base / arquivo
        if not caminho.exists():
            print(f"{rotulo}: arquivo ausente ({caminho})")
            continue
        dados = caminho.read_bytes()
        contagem: Counter[str] = Counter()
        por_andar: dict[int, Counter[str]] = {}
        for m in RE_BLOCO.finditer(dados):
            cx, cy = int(m.group(2)), int(m.group(3))
            for f in RE_FILHO.finditer(m.group(6)):
                x, y = cx + int(f.group(2)), cy + int(f.group(3))
                z = int(f.group(4))
                if dentro(x, y, z, x0, y0, x1, y1, z0, z1):
                    nome = f.group(1).decode(errors="replace")
                    contagem[nome] += 1
                    por_andar.setdefault(z, Counter())[nome] += 1
        total = sum(contagem.values())
        print(f"{rotulo} dentro do recorte: {total}")
        for nome, n in contagem.most_common(40):
            print(f"    {n:>5}  {nome}")
        if len(contagem) > 40:
            print(f"    ... e mais {len(contagem) - 40} tipos")

        # Extensao vertical: a hunt precisa levar os andares de cima e de baixo,
        # nao so o principal. Andar sem spawn NO MEIO do intervalo ainda faz
        # parte da hunt (escada, corredor) e nao pode ser pulado.
        if por_andar:
            print(f"  -- {rotulo.lower()} por andar --")
            for z in range(min(por_andar), max(por_andar) + 1):
                c = por_andar.get(z)
                if not c:
                    print(f"    z={z:>2}: (nenhum spawn -- provavel ligacao/escada,"
                          f" INCLUIR no recorte)")
                    continue
                top = ", ".join(f"{n}x {nm}" for nm, n in c.most_common(3))
                print(f"    z={z:>2}: {sum(c.values()):>4} spawns   {top}")
        print()

    # ---- casas (proibidas na instancia) ----
    caminho = base / "otservbr-house.xml"
    if caminho.exists():
        dados = caminho.read_bytes()
        achadas = []
        for m in RE_CASA.finditer(dados):
            x, y, z = int(m.group(2)), int(m.group(3)), int(m.group(4))
            if dentro(x, y, z, x0, y0, x1, y1, z0, z1):
                achadas.append((m.group(1).decode(errors="replace"), x, y, z))
        print(f"CASAS dentro do recorte: {len(achadas)}"
              + ("   <-- PROIBIDO pela spec, remover do chunk" if achadas else ""))
        for nome, x, y, z in achadas[:20]:
            print(f"    {nome}  ({x},{y},{z})")
        print()

    print("Lembretes da spec (secao 6.2), nao verificaveis por XML:")
    print("  - o OTBM do chunk nao pode ter TOWNS nem WAYPOINTS")
    print("    (sao parseados sem offset e sobrescrevem os globais)")
    print("  - remover quest chests, teleports de missao e unique IDs globais")
    return 0


if __name__ == "__main__":
    sys.exit(main())
