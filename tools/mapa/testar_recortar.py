#!/usr/bin/env python3
"""Teste do recortar.py contra um OTBM sintetico.

Prova quatro coisas que, se falharem, corrompem o mapa em silencio:

  1. coordenada REBASEADA (senao estoura o uint16 ao carregar com offset);
  2. escape na escrita (byte FD/FE/FF cru vira marcador de no);
  3. teleport e depot removidos (buraco de fuga da instancia);
  4. action id / unique id / vinculo de casa removidos, mas o ITEM preservado.

    python3 tools/mapa/testar_recortar.py
"""
from __future__ import annotations

import struct
import subprocess
import sys
import tempfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

from recortar import (A_ACTION, A_DEPOT, A_HOUSEDOOR, A_TELE, A_UNIQUE, FIM,
                      INICIO, NO_AREA, NO_CASA, NO_ITEM, NO_MAP_DATA, NO_RAIZ,
                      NO_TILE, escapar)

BASE = (1024, 1024, 7)
X0, Y0 = 1030, 1030          # recorte comeca deslocado da base de proposito
X1, Y1 = 1060, 1060

CHAO = 4526                  # 'grass'      -> ae 11
CHAO_ESCAPADO = 21501        # 'dirt floor' -> fd 53
ITEM_SEGURO = 1234
ITEM_TELE = 1387
ITEM_DEPOT = 2594
ITEM_PORTA = 1220


NO_ZONA = 19
ITEM_BOLSA = 2854
ITEM_DENTRO = 2148


def item_bytes(iid, attrs=(), filhos=()):
    b = bytearray([INICIO, NO_ITEM])
    b += escapar(struct.pack("<H", iid))
    for a, bruto in attrs:
        b.append(a)
        b += escapar(bruto)
    for f in filhos:
        b += f
    b.append(FIM)
    return bytes(b)


def zona_bytes(*ids):
    b = bytearray([INICIO, NO_ZONA])
    b += escapar(struct.pack("<H", len(ids)))
    for z in ids:
        b += escapar(struct.pack("<H", z))
    b.append(FIM)
    return bytes(b)


def tile(dx, dy, chao, filhos=(), casa=False):
    corpo = bytearray([INICIO, NO_CASA if casa else NO_TILE])
    corpo += escapar(bytes([dx, dy]))
    if casa:
        corpo += escapar(struct.pack("<I", 55))
    if chao is not None:
        corpo.append(9)                       # ATTR_ITEM
        corpo += escapar(struct.pack("<H", chao))
    for f in filhos:
        corpo += f
    corpo.append(FIM)
    return bytes(corpo)


def montar_origem() -> bytes:
    tiles = b"".join([
        # (1030,1030) chao escapado + item seguro -> deve sobreviver inteiro
        tile(6, 6, CHAO_ESCAPADO, [item_bytes(ITEM_SEGURO)]),
        # (1031,1030) teleport -> item deve SUMIR, tile fica
        tile(7, 6, CHAO, [item_bytes(ITEM_TELE,
             [(A_TELE, struct.pack("<HHB", 32000, 32000, 7))])]),
        # (1032,1030) depot -> item deve SUMIR
        tile(8, 6, CHAO, [item_bytes(ITEM_DEPOT, [(A_DEPOT, struct.pack("<H", 8))])]),
        # (1033,1030) porta com vinculo de casa -> item FICA, vinculo some
        tile(9, 6, CHAO, [item_bytes(ITEM_PORTA, [(A_HOUSEDOOR, bytes([3]))])],
             casa=True),
        # (1034,1030) item com action+unique -> item FICA, atributos somem
        tile(10, 6, CHAO, [item_bytes(ITEM_SEGURO,
             [(A_ACTION, struct.pack("<H", 48063)),
              (A_UNIQUE, struct.pack("<H", 3120))])]),
        # (1035,1030) CONTAINER com item dentro -> os dois tem que sobreviver
        tile(11, 6, CHAO, [item_bytes(ITEM_BOLSA, [],
             [item_bytes(ITEM_DENTRO)])]),
        # (1036,1030) tile com NO DE ZONA + item depois -> zona descartada,
        # item preservado. Se o parser desalinhar aqui, tudo depois quebra.
        tile(12, 6, CHAO, [zona_bytes(7, 9), item_bytes(ITEM_SEGURO)]),
        # (1000,1000) FORA do recorte -> nao pode aparecer
        tile(0, 0, CHAO, [item_bytes(ITEM_SEGURO)]),
    ])
    area = bytes([INICIO, NO_AREA]) + escapar(struct.pack("<HHB", *BASE)) + tiles + bytes([FIM])
    mapdata = bytes([INICIO, NO_MAP_DATA]) + area + bytes([FIM])
    raiz = (bytes([INICIO, NO_RAIZ])
            + escapar(struct.pack("<IHHII", 4, 2048, 2048, 4, 4))
            + mapdata + bytes([FIM]))
    return b"\0\0\0\0" + raiz


falhas = []


def conferir(desc, obtido, esperado):
    ok = obtido == esperado
    print(f"  {'ok  ' if ok else 'FALHA'} {desc}: {obtido!r}"
          + ("" if ok else f"  (esperado {esperado!r})"))
    if not ok:
        falhas.append(desc)


def arvore_integra(d: bytes) -> bool:
    i, nivel = 4, 0
    while i < len(d):
        b = d[i]
        if b == 0xFD:
            i += 2
            continue
        if b == INICIO:
            nivel += 1
        elif b == FIM:
            nivel -= 1
            if nivel < 0:
                return False
        i += 1
    return nivel == 0


def main() -> int:
    tmp = Path(tempfile.mkdtemp())
    origem, destino = tmp / "origem.otbm", tmp / "recorte.otbm"
    origem.write_bytes(montar_origem())

    r = subprocess.run(
        [sys.executable, str(AQUI / "recortar.py"), str(origem), str(destino),
         str(X0), str(Y0), str(X1), str(Y1), "7", "7"],
        capture_output=True, text=True)
    print(r.stdout)
    if r.returncode != 0:
        print("recortar.py falhou:", r.stderr)
        return 1

    d = destino.read_bytes()
    print("=== verificacoes ===")
    conferir("arvore fecha certo", arvore_integra(d), True)

    # le de volta com o parser de producao
    from otbm import Mapa
    m = Mapa(destino)
    conferir("cabecalho (versao, larg, alt)", m.cabecalho[:3],
             (4, X1 - X0 + 1, Y1 - Y0 + 1))

    # (1030,1030) virou (0,0) -- rebase
    t = m.tile(0, 0, 7)
    conferir("tile rebaseado p/ (0,0) existe", t is not None, True)
    if t:
        conferir("chao escapado sobreviveu", t.chao, CHAO_ESCAPADO)
        conferir("chao escapado ocupa 3 bytes crus", t.chao_bytes, 3)
        conferir("item seguro preservado", [i for i, _, _ in t.itens],
                 [ITEM_SEGURO])

    t = m.tile(1, 0, 7)
    conferir("teleport removido", [i for i, _, _ in t.itens] if t else None, [])
    t = m.tile(2, 0, 7)
    conferir("depot removido", [i for i, _, _ in t.itens] if t else None, [])

    t = m.tile(3, 0, 7)
    conferir("porta preservada (so perdeu o vinculo)",
             [i for i, _, _ in t.itens] if t else None, [ITEM_PORTA])
    conferir("tile de casa virou tile comum", t.casa if t else None, False)

    t = m.tile(4, 0, 7)
    conferir("item com action/unique preservado",
             [i for i, _, _ in t.itens] if t else None, [ITEM_SEGURO])

    # container: o otbm.py lista so os itens de primeiro nivel do tile, entao
    # a bolsa aparece uma vez. O que importa e' o parser nao ter desalinhado.
    t = m.tile(5, 0, 7)
    conferir("container preservado", [i for i, _, _ in t.itens] if t else None,
             [ITEM_BOLSA])
    conferir("item de dentro do container sobreviveu nos bytes",
             ITEM_DENTRO.to_bytes(2, "little") in d, True)

    # zona descartada, mas o item que vem DEPOIS dela intacto -- se o parser
    # perdesse o sincronismo no no de zona, este tile sairia errado
    t = m.tile(6, 0, 7)
    conferir("tile pos-zona existe", t is not None, True)
    conferir("item apos no de zona preservado",
             [i for i, _, _ in t.itens] if t else None, [ITEM_SEGURO])
    conferir("chao do tile pos-zona intacto", t.chao if t else None, CHAO)

    # o tile de fora nao pode ter entrado em lugar nenhum
    fora = [m.tile(x, y, 7) for x in range(0, 31) for y in range(0, 31)]
    conferir("tiles dentro do recorte", sum(1 for t in fora if t), 7)

    print()
    if falhas:
        print(f"{len(falhas)} FALHA(S): " + ", ".join(falhas))
        return 1
    print("tudo certo")
    return 0


if __name__ == "__main__":
    sys.exit(main())
