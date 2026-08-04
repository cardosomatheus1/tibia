#!/usr/bin/env python3
"""Acha os clusters geograficos de spawn de um monstro e da o bounding box.

Serve pra Etapa 0 da spec de hunt instanciada: descobrir os limites REAIS da
hunt antes de recortar o chunk. O tamanho do recorte governa tempo de carga e
memoria por instancia, entao chutar a area pra mais e' caro -- e chutar pra
menos corta spawn.

No otservbr-monster.xml o x/y do <monster> e' OFFSET do centerx/centery do
<spawn> que o contem. Ler o x/y cru da o lugar errado.

    python3 achar_hunt.py <spawn.xml> <nome do monstro> [raio_do_cluster]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Formato OTServBR: o bloco de spawn tambem se chama <monster>, e os monstros
# de dentro sao self-closing -- entao o </monster> so fecha o bloco externo.
#   <monster centerx="32616" centery="31414" centerz="2" radius="2">
#       <monster name="Cyclops" x="1" y="2" z="2" spawntime="90" />
#   </monster>
RE_SPAWN = re.compile(
    rb'<monster\s+centerx="(\d+)"\s+centery="(\d+)"\s+centerz="(\d+)"'
    rb'(?:\s+radius="(\d+)")?\s*>(.*?)</monster>',
    re.DOTALL)
# <monster name="Cyclops" x="-1" y="2" z="7" spawntime="60"/>
RE_MONSTRO = re.compile(
    rb'<monster\s+name="([^"]+)"\s+x="(-?\d+)"\s+y="(-?\d+)"\s+z="(\d+)"'
    rb'(?:\s+spawntime="(\d+)")?')


def coletar(caminho: Path, alvo: str) -> list[tuple[int, int, int, int]]:
    """Devolve [(x, y, z, spawntime)] absolutos dos monstros que casam."""
    dados = caminho.read_bytes()
    alvo_b = alvo.lower().encode()
    achados = []

    for m in RE_SPAWN.finditer(dados):
        cx, cy, _cz = int(m.group(1)), int(m.group(2)), int(m.group(3))
        corpo = m.group(5)
        for mm in RE_MONSTRO.finditer(corpo):
            nome = mm.group(1).lower()
            if alvo_b not in nome:
                continue
            # x/y sao offsets do centro; z e' absoluto
            x = cx + int(mm.group(2))
            y = cy + int(mm.group(3))
            z = int(mm.group(4))
            st = int(mm.group(5)) if mm.group(5) else 0
            achados.append((x, y, z, st))
    return achados


def clusterizar(pontos, raio: int):
    """Agrupa por proximidade em 3D.

    O z entra na chave e so conecta andares ADJACENTES (dz de -1 a 1). Sem
    isso, um agrupamento 2D funde uma hunt de superficie com outra que por
    acaso fica no subterraneo profundo embaixo dela -- no caso dos ciclopes,
    isso juntava os andares 5-9 com o 14-15 e inflava o recorte em 24x.

    Andares contiguos SIM se conectam, porque uma hunt de verdade se espalha
    por escadas entre andares vizinhos.
    """
    celulas: dict[tuple[int, int, int], list] = {}
    for p in pontos:
        celulas.setdefault((p[0] // raio, p[1] // raio, p[2]), []).append(p)

    visto, grupos = set(), []
    for chave in celulas:
        if chave in visto:
            continue
        fila, grupo = [chave], []
        visto.add(chave)
        while fila:
            cx, cy, cz = fila.pop()
            grupo.extend(celulas[(cx, cy, cz)])
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for dz in (-1, 0, 1):
                        viz = (cx + dx, cy + dy, cz + dz)
                        if viz in celulas and viz not in visto:
                            visto.add(viz)
                            fila.append(viz)
        grupos.append(grupo)
    return sorted(grupos, key=len, reverse=True)


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2

    caminho = Path(sys.argv[1])
    alvo = sys.argv[2]
    raio = int(sys.argv[3]) if len(sys.argv) > 3 else 50

    pontos = coletar(caminho, alvo)
    print(f"spawns de '{alvo}': {len(pontos)}")
    if not pontos:
        return 1

    grupos = clusterizar(pontos, raio)
    print(f"clusters (raio {raio}): {len(grupos)}\n")

    # ancora opcional pra ordenar por distancia (ex: centro de Thais)
    ancora = None
    if len(sys.argv) > 5:
        ancora = (int(sys.argv[4]), int(sys.argv[5]))

    # Custo de memoria: o mapa aloca por SETOR de 16x16, e dentro dele um
    # Floor por andar usado. Numeros medidos das structs:
    #   Floor    ~6.2 KB (grid 16x16 de shared_ptr + grid de BasicTile* + mutex)
    #   MapSector ~0.7 KB
    KB_FLOOR, KB_SETOR, SETOR = 6.2, 0.7, 16

    def custo_kb(larg: int, alt: int, andares: int) -> float:
        setores = ((larg + SETOR - 1) // SETOR) * ((alt + SETOR - 1) // SETOR)
        return setores * (KB_SETOR + andares * KB_FLOOR)

    def dist(g) -> int:
        if not ancora:
            return 0
        cx = sum(p[0] for p in g) // len(g)
        cy = sum(p[1] for p in g) // len(g)
        return max(abs(cx - ancora[0]), abs(cy - ancora[1]))

    ordenados = sorted(grupos[:12], key=dist) if ancora else grupos[:12]

    for i, g in enumerate(ordenados, 1):
        xs = [p[0] for p in g]
        ys = [p[1] for p in g]
        zs = sorted({p[2] for p in g})
        sts = sorted({p[3] for p in g})
        larg, alt = max(xs) - min(xs) + 1, max(ys) - min(ys) + 1
        # andares CONTIGUOS pesam menos que o span total: o Floor so existe
        # para o z usado, entao o que conta e' len(zs), nao max-min.
        kb = custo_kb(larg, alt, len(zs))
        print(f"cluster {i}: {len(g)} spawns" +
              (f"   distancia da ancora: {dist(g)} tiles" if ancora else ""))
        print(f"  x {min(xs)}-{max(xs)}  y {min(ys)}-{max(ys)}  "
              f"({larg}x{alt} tiles)")
        print(f"  andares: {zs}  ({len(zs)} usados, span {max(zs) - min(zs) + 1})")
        print(f"  spawntime: {sts}")
        print(f"  custo estimado: {kb:.0f} KB/copia  ->  "
              f"6 copias = {6 * kb / 1024:.1f} MB  |  "
              f"100 copias = {100 * kb / 1024:.0f} MB")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
