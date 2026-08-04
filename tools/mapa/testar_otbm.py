#!/usr/bin/env python3
"""Teste do escape na escrita do OTBM.

Monta um OTBM minimo em memoria, edita e le de volta. O que se quer provar e'
que id com byte FD/FE/FF sobrevive a ida e volta -- tanto ao ser gravado quanto
ao ser substituido.

Roda sem o mapa de verdade de proposito: o global tem 177 MB e uma escrita
errada la e' irreversivel na pratica.

    python3 tools/mapa/testar_otbm.py
"""
from __future__ import annotations

import struct
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from otbm import (ATTR_ITEM, FIM, INICIO, NO_AREA, NO_ITEM, NO_MAP_DATA,
                  NO_RAIZ, NO_TILE, Mapa, escapar)

BASE = (1024 & 0xFF00, 1024 & 0xFF00, 7)

# ids escolhidos para exercitar o escape:
CHAO_ESCAPADO = 21501   # 'dirt floor'  -> fd 53  (3 bytes crus)
CHAO_SIMPLES = 4526     # 'grass'       -> ae 11  (2 bytes crus)
CHAO_PERIGOSO = 24317   # 'cut grass'   -> fd 5e  (3 bytes crus)
ITEM_PERIGOSO = 12287   # 'magic tile'  -> ff 2f  (3 bytes crus)


def tile(dx: int, dy: int, chao: int | None) -> bytes:
    """No de tile: coordenadas + (opcional) atributo de chao."""
    corpo = bytes([INICIO, NO_TILE]) + escapar(bytes([dx, dy]))
    if chao is not None:
        corpo += bytes([ATTR_ITEM]) + escapar(struct.pack("<H", chao))
    return corpo + bytes([FIM])


def montar() -> bytes:
    tiles = (tile(0, 0, CHAO_ESCAPADO)     # (1024,1024) chao ja escapado
             + tile(1, 0, CHAO_SIMPLES)    # (1025,1024) chao normal
             + tile(2, 0, CHAO_SIMPLES)    # (1026,1024) alvo do adicionar_item
             + tile(253, 254, CHAO_SIMPLES))  # coordenadas que exigem escape
    area = (bytes([INICIO, NO_AREA]) + struct.pack("<HHB", *BASE)
            + tiles + bytes([FIM]))
    mapdata = bytes([INICIO, NO_MAP_DATA]) + area + bytes([FIM])
    raiz = (bytes([INICIO, NO_RAIZ])
            + struct.pack("<IHHII", 2, 2048, 2048, 3, 60)
            + mapdata + bytes([FIM]))
    return b"\0\0\0\0" + raiz


falhas: list[str] = []


def conferir(desc: str, obtido, esperado) -> None:
    ok = obtido == esperado
    print(f"  {'ok  ' if ok else 'FALHA'} {desc}: {obtido!r}"
          + ("" if ok else f"  (esperado {esperado!r})"))
    if not ok:
        falhas.append(desc)


def arvore_integra(dados: bytes) -> bool:
    """Percorre a arvore inteira respeitando o escape e confere que fecha."""
    i, nivel = 4, 0
    while i < len(dados):
        b = dados[i]
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
    tmp = Path(tempfile.mkdtemp()) / "teste.otbm"
    tmp.write_bytes(montar())

    print("=== leitura do mapa sintetico ===")
    m = Mapa(tmp)
    conferir("cabecalho (versao, larg, alt)", m.cabecalho[:3], (2, 2048, 2048))
    conferir("areas encontradas", m.areas(), [BASE])

    t = m.tile(1024, 1024, 7)
    conferir("chao escapado lido", t.chao, CHAO_ESCAPADO)
    conferir("chao escapado ocupa 3 bytes crus", t.chao_bytes, 3)
    conferir("chao simples ocupa 2 bytes crus",
             m.tile(1025, 1024, 7).chao_bytes, 2)
    conferir("tile em coordenada escapada (253,254)",
             m.tile(1024 + 253, 1024 + 254, 7).chao, CHAO_SIMPLES)

    print("\n=== BUG B: trocar um chao que estava escapado ===")
    m.trocar_chao(1024, 1024, 7, CHAO_SIMPLES)

    print("=== BUG A: gravar um chao que precisa de escape ===")
    m.trocar_chao(1025, 1024, 7, CHAO_PERIGOSO)

    print("=== BUG A: adicionar item que precisa de escape ===")
    m.adicionar_item(1026, 1024, 7, ITEM_PERIGOSO)

    saida = m.salvar(tmp.with_name("saida.otbm"))

    print("\n=== releitura ===")
    dados = saida.read_bytes()
    conferir("arvore fecha certo", arvore_integra(dados), True)

    m2 = Mapa(saida)
    conferir("areas ainda encontradas", m2.areas(), [BASE])
    conferir("(1024,1024) trocado p/ simples", m2.tile(1024, 1024, 7).chao,
             CHAO_SIMPLES)
    conferir("(1024,1024) agora ocupa 2 bytes", m2.tile(1024, 1024, 7).chao_bytes, 2)
    conferir("(1025,1024) recebeu id perigoso", m2.tile(1025, 1024, 7).chao,
             CHAO_PERIGOSO)
    conferir("(1025,1024) agora ocupa 3 bytes", m2.tile(1025, 1024, 7).chao_bytes, 3)
    conferir("(1026,1024) ganhou o item",
             [i for i, _, _ in m2.tile(1026, 1024, 7).itens], [ITEM_PERIGOSO])
    conferir("(1026,1024) manteve o chao", m2.tile(1026, 1024, 7).chao,
             CHAO_SIMPLES)
    conferir("tile distante intacto apos as edicoes",
             m2.tile(1024 + 253, 1024 + 254, 7).chao, CHAO_SIMPLES)

    print()
    if falhas:
        print(f"{len(falhas)} FALHA(S): " + ", ".join(falhas))
        return 1
    print("tudo certo")
    return 0


if __name__ == "__main__":
    sys.exit(main())
