#!/usr/bin/env python3
"""Enumera os nos de area do OTBM e diz que regioes do mapa estao ocupadas.

Serve pra Etapa 0 da spec de hunt instanciada: provar que a faixa escolhida
pras copias esta REALMENTE vazia no mapa de producao, e nao so nos XMLs.

Nao percorre o arquivo tile a tile. Procura a assinatura do no de area
(0xFE 0x04 + x:u16 + y:u16 + z:u8, seguido de 0xFE) com bytes.find, que roda
em C. Cada area cobre 256x256 tiles.

Cuidado com o escape: o OTBM poe 0xFD na frente de todo byte de dado que valha
FD/FE/FF, entao uma area cuja coordenada contenha esses bytes nao casa com a
busca crua. Isso e' contabilizado e reportado -- pra faixa 5000-6200 nenhum
byte cai nesse caso, entao nao afeta a conclusao.

    python3 scan_ocupacao.py <mapa.otbm> [x0 y0 x1 y1]
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

INICIO, FIM, NO_AREA = 0xFE, 0xFF, 0x04
ESCAPA = 0xFD
LADO = 256          # cada no de area cobre 256x256


def _ler_cru(dados: bytes, i: int, n: int) -> tuple[bytes, int] | None:
    """Le n bytes de conteudo a partir de i desfazendo o escape 0xFD.

    Sem isso, uma base cuja coordenada contenha FD/FE/FF (ex: x=4861 -> FD 12)
    e' lida errada e a area cai na faixa errada do relatorio.
    """
    saida = bytearray()
    j, fim = i, len(dados)
    while len(saida) < n:
        if j >= fim:
            return None
        b = dados[j]
        if b == ESCAPA:
            j += 1
            if j >= fim:
                return None
            saida.append(dados[j])
        elif b in (INICIO, FIM):
            return None          # marcador cru no meio do dado: nao e' area
        else:
            saida.append(b)
        j += 1
    return bytes(saida), j


def enumerar_areas(dados: bytes) -> tuple[set[tuple[int, int, int]], int]:
    """Devolve {(x, y, z) das bases} e quantos candidatos foram descartados."""
    bases: set[tuple[int, int, int]] = set()
    prefixo = bytes([INICIO, NO_AREA])
    pos, descartados = -1, 0

    while True:
        pos = dados.find(prefixo, pos + 1)
        if pos < 0:
            break
        # o 0xFE precisa ser marcador de no, nao dado escapado
        if pos > 0 and dados[pos - 1] == ESCAPA:
            descartados += 1
            continue
        lido = _ler_cru(dados, pos + 2, 5)
        if lido is None:
            descartados += 1
            continue
        bruto, prox = lido
        # area so tem filhos (nos), nunca atributo: tem que abrir um no logo apos
        if prox >= len(dados) or dados[prox] != INICIO:
            descartados += 1
            continue
        x, y, z = struct.unpack("<HHB", bruto)
        if z > 15:                      # MAP_MAX_LAYERS
            descartados += 1
            continue
        bases.add((x, y, z))

    return bases, descartados


def contar_escapes_suspeitos(dados: bytes) -> int:
    """Areas cuja coordenada foi escapada nao casam com a busca crua.

    Conta ocorrencias de 0xFE 0x04 precedidas de 0xFD (ou seja, o proprio
    0xFE era dado escapado, nao marcador) so pra dimensionar o erro.
    """
    prefixo = bytes([INICIO, NO_AREA])
    pos, n = -1, 0
    while True:
        pos = dados.find(prefixo, pos + 1)
        if pos < 0:
            break
        if pos > 0 and dados[pos - 1] == ESCAPA:
            n += 1
    return n


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2

    caminho = Path(sys.argv[1])
    alvo = None
    if len(sys.argv) >= 6:
        alvo = tuple(int(v) for v in sys.argv[2:6])   # x0 y0 x1 y1

    print(f"lendo {caminho} ({caminho.stat().st_size / 1024 / 1024:.1f} MB)")
    dados = caminho.read_bytes()

    versao, larg, alt = struct.unpack("<IHH", dados[6:14])
    print(f"cabecalho: versao={versao} declarado={larg}x{alt}")

    bases, descartados = enumerar_areas(dados)
    escapadas = contar_escapes_suspeitos(dados)
    del dados                                   # libera os 184 MB antes de agregar

    print(f"nos de area validos: {len(bases)}  (descartados: {descartados})")
    print(f"assinaturas precedidas de escape (nao enumeradas): {escapadas}")

    xs = [b[0] for b in bases]
    ys = [b[1] for b in bases]
    zs = sorted({b[2] for b in bases})
    print(f"\nbounding box das bases: x {min(xs)}-{max(xs)}  y {min(ys)}-{max(ys)}")
    print(f"andares usados: {zs}")

    # ---- clusters em X, pra enxergar os vazios ----
    print("\nocupacao por faixa de 1000 em X (areas distintas):")
    faixas: dict[int, int] = {}
    for x, _y, _z in bases:
        faixas[x // 1000] = faixas.get(x // 1000, 0) + 1
    for k in sorted(faixas):
        print(f"  x {k * 1000:>6}-{k * 1000 + 999:<6} {faixas[k]:>5} areas")

    # ---- a pergunta que importa ----
    if alvo:
        x0, y0, x1, y1 = alvo
        print(f"\n=== faixa alvo: x {x0}-{x1} / y {y0}-{y1} ===")
        # uma area em (bx, by) cobre bx..bx+255 -- ela colide com o alvo se
        # os intervalos se cruzarem em ambos os eixos.
        colisoes = [
            (bx, by, bz) for bx, by, bz in bases
            if bx + LADO - 1 >= x0 and bx <= x1
            and by + LADO - 1 >= y0 and by <= y1
        ]
        if colisoes:
            print(f"OCUPADA -- {len(colisoes)} area(s) colidem:")
            for c in sorted(colisoes)[:40]:
                print(f"    base {c}  cobre x {c[0]}-{c[0] + 255} y {c[1]}-{c[1] + 255}")
            if len(colisoes) > 40:
                print(f"    ... e mais {len(colisoes) - 40}")
        else:
            print("LIVRE -- nenhum no de area toca essa faixa")

        # margem: qual o vizinho mais proximo?
        def dist(b):
            dx = max(x0 - (b[0] + LADO - 1), b[0] - x1, 0)
            dy = max(y0 - (b[1] + LADO - 1), b[1] - y1, 0)
            return max(dx, dy)

        vizinhos = sorted(bases, key=dist)[:5]
        print("\n  vizinhos mais proximos:")
        for v in vizinhos:
            print(f"    base {v}  distancia {dist(v)} tiles")

    # ---- avaliar layouts concretos de pool ----
    def folga(x0: int, y0: int, x1: int, y1: int) -> int:
        """Menor distancia em tiles entre o retangulo e qualquer area do mapa."""
        melhor = 1 << 30
        for bx, by, _bz in bases:
            dx = max(x0 - (bx + LADO - 1), bx - x1, 0)
            dy = max(y0 - (by + LADO - 1), by - y1, 0)
            melhor = min(melhor, max(dx, dy))
            if melhor == 0:
                return 0
        return melhor

    # A regiao alem do maior x/y usado esta totalmente virgem: e' onde um pool
    # grande cabe sem chegar perto de nada do mapa oficial.
    maxx, maxy = max(xs) + LADO, max(ys) + LADO
    print(f"\n=== espaco livre alem do mapa oficial ===")
    print(f"  maior coordenada usada: x {maxx}  y {maxy}")
    print(f"  teto do tipo Position (uint16): 65535")
    print(f"  sobra: {65535 - maxx} tiles em x, {65535 - maxy} em y")

    LARGURA, PASSO = 256, 512
    print(f"\n=== layouts de pool (slots de {LARGURA}x{LARGURA}, "
          f"espacados {PASSO}) ===")
    for ox, oy, slots in [(20480, 20480, 6), (36864, 20480, 6),
                          (36864, 36864, 6), (36864, 36864, 100)]:
        cols = min(slots, 32)
        linhas = (slots + cols - 1) // cols
        x1 = ox + (cols - 1) * PASSO + LARGURA - 1
        y1 = oy + (linhas - 1) * PASSO + LARGURA - 1
        cabe = x1 <= 65535 and y1 <= 65535
        f = folga(ox, oy, x1, y1) if cabe else -1
        marca = ("ESTOURA uint16" if not cabe
                 else "LIVRE" if f > 0 else "OCUPADA")
        print(f"  {slots:>3} slots em ({ox},{oy}) -> x {ox}-{x1} y {oy}-{y1}: "
              f"{marca}" + (f", folga {f} tiles" if cabe else ""))

    # ---- teto de escala ----
    print("\n=== teto de escala (grade alinhada, sem tocar o mapa oficial) ===")
    livre_x = (65535 - maxx) // PASSO
    livre_y = (65535 - maxy) // PASSO
    print(f"  grade de {livre_x} x {livre_y} = {livre_x * livre_y} slots de "
          f"{LARGURA}x{LARGURA} cabem depois do mapa oficial")
    for andares, mb in ((3, 3.3), (8, 8.5)):
        print(f"  custo so de geometria, {andares} andares: "
              f"{mb:.1f} MB/copia -> 6 copias={6 * mb:.0f} MB, "
              f"100={100 * mb:.0f} MB, {livre_x * livre_y}={livre_x * livre_y * mb / 1024:.1f} GB")

    return 0


if __name__ == "__main__":
    sys.exit(main())
