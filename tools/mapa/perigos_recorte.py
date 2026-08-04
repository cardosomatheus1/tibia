#!/usr/bin/env python3
"""Acha, dentro de uma regiao do OTBM, o que NAO pode ser duplicado.

Etapa 0 da spec de hunt instanciada. O `Game.loadMapChunk` carrega SO TERRENO
(loadHouses/Monsters/Npcs/Zones vem false), entao spawn e npc do XML global nao
entram na copia. O que entra e' o que esta nos tiles:

  ACTION_ID (4)  alavanca/porta de quest -- dispara script global
  UNIQUE_ID (5)  id global unico -- duplicar quebra a unicidade
  TELE_DEST (8)  teleport -- mandaria o jogador pras coordenadas ORIGINAIS,
                 furando o InstanceManager (spec 11.3)
  DEPOT_ID  (10) depot dentro da instancia
  HOUSEDOORID(14) porta de casa

Tambem lista towns e waypoints, que sao parseados SEM offset e sobrescrevem os
globais quando o mesmo chunk e' carregado N vezes (spec 6.2).

    python3 perigos_recorte.py <mapa.otbm> x0 y0 x1 y1 [z0 z1]
"""
from __future__ import annotations

import struct
import sys
from collections import Counter
from pathlib import Path

INICIO, FIM, ESCAPA = 0xFE, 0xFF, 0xFD
NO_AREA, NO_TILE, NO_ITEM, NO_TOWNS, NO_WAYPOINTS = 0x04, 0x05, 0x06, 0x0C, 0x0F

A_DESCRICAO, A_FLAGS, A_ACTION, A_UNIQUE = 1, 3, 4, 5
A_TEXT, A_DESC, A_TELE, A_ITEM, A_DEPOT = 6, 7, 8, 9, 10
A_HOUSEDOOR, A_COUNT, A_CHARGES = 14, 15, 22

# tamanho fixo em bytes de cada atributo; None = string com prefixo u16
TAM = {
    A_DESCRICAO: None, A_FLAGS: 4, A_ACTION: 2, A_UNIQUE: 2,
    A_TEXT: None, A_DESC: None, A_TELE: 5, A_ITEM: 2, A_DEPOT: 2,
    12: 1, A_HOUSEDOOR: 1, A_COUNT: 1, 16: 4, 17: 1,
    18: 4, 19: None, 20: 4, 21: 4, A_CHARGES: 2,
}


class Fluxo:
    """Le o OTBM desfazendo o escape 0xFD."""

    def __init__(self, dados: bytes, i: int):
        self.d, self.i = dados, i

    def byte(self) -> int:
        b = self.d[self.i]
        if b == ESCAPA:
            self.i += 2
            return self.d[self.i - 1]
        self.i += 1
        return b

    def bytes(self, n: int) -> bytes:
        return bytes(self.byte() for _ in range(n))

    def u8(self) -> int:
        return self.byte()

    def u16(self) -> int:
        return struct.unpack("<H", self.bytes(2))[0]

    def u32(self) -> int:
        return struct.unpack("<I", self.bytes(4))[0]

    def espia(self) -> int:
        return self.d[self.i]


def ler_atributos(f: Fluxo, achados: dict, x: int, y: int, z: int,
                  item_id: int | None, dentro: bool) -> bool:
    """Consome atributos ate encontrar um no ou o fim. False se nao entendeu.

    `dentro` diz se o tile cai na regiao pedida. Precisa consumir os bytes de
    qualquer jeito (senao o parser desalinha), mas so REGISTRA se estiver
    dentro -- uma area do OTBM cobre 256x256 e quase sempre extrapola a regiao.
    """
    while True:
        b = f.espia()
        if b in (INICIO, FIM):
            return True
        attr = f.u8()
        if attr not in TAM:
            return False                      # atributo desconhecido: aborta
        tam = TAM[attr]
        if tam is None:                       # string
            n = f.u16()
            f.bytes(n)
            continue
        bruto = f.bytes(tam)
        if not dentro:
            continue
        if attr == A_ACTION:
            achados["action"].append((x, y, z, item_id,
                                      struct.unpack("<H", bruto)[0]))
        elif attr == A_UNIQUE:
            achados["unique"].append((x, y, z, item_id,
                                      struct.unpack("<H", bruto)[0]))
        elif attr == A_TELE:
            dx, dy, dz = struct.unpack("<HHB", bruto)
            achados["tele"].append((x, y, z, item_id, dx, dy, dz))
        elif attr == A_DEPOT:
            achados["depot"].append((x, y, z, item_id,
                                     struct.unpack("<H", bruto)[0]))
        elif attr == A_HOUSEDOOR:
            achados["porta"].append((x, y, z, item_id, bruto[0]))


def varrer(dados: bytes, alvo) -> dict:
    x0, y0, x1, y1, z0, z1 = alvo
    achados = {k: [] for k in ("action", "unique", "tele", "depot", "porta")}
    achados["itens"] = Counter()
    achados["tiles"] = 0
    achados["parciais"] = 0

    prefixo = bytes([INICIO, NO_AREA])
    pos = -1
    while True:
        pos = dados.find(prefixo, pos + 1)
        if pos < 0:
            break
        if pos > 0 and dados[pos - 1] == ESCAPA:
            continue
        f = Fluxo(dados, pos + 2)
        try:
            bx, by, bz = f.u16(), f.u16(), f.u8()
        except IndexError:
            continue
        if f.i >= len(dados) or dados[f.i] != INICIO:
            continue
        # a area cobre 256x256 a partir da base
        if not (bz is not None and z0 <= bz <= z1
                and bx <= x1 and bx + 255 >= x0
                and by <= y1 and by + 255 >= y0):
            continue

        # percorre os tiles da area
        while f.i < len(dados) and dados[f.i] == INICIO:
            f.i += 1
            tipo = f.u8()
            if tipo not in (NO_TILE, 0x0E):        # tile ou house tile
                break
            dx, dy = f.u8(), f.u8()
            tx, ty, tz = bx + dx, by + dy, bz
            if tipo == 0x0E:
                f.u32()                            # id da casa
            dentro = (x0 <= tx <= x1 and y0 <= ty <= y1)
            if dentro:
                achados["tiles"] += 1
            if not ler_atributos(f, achados, tx, ty, tz, None, dentro):
                achados["parciais"] += 1
                break
            # itens do tile
            while f.i < len(dados) and dados[f.i] == INICIO:
                f.i += 1
                if f.u8() != NO_ITEM:
                    break
                iid = f.u16()
                if dentro:
                    achados["itens"][iid] += 1
                if not ler_atributos(f, achados, tx, ty, tz, iid, dentro):
                    achados["parciais"] += 1
                    break
                if f.i < len(dados) and dados[f.i] == FIM:
                    f.i += 1
            if f.i < len(dados) and dados[f.i] == FIM:
                f.i += 1
    return achados


def main() -> int:
    if len(sys.argv) < 6:
        print(__doc__)
        return 2
    caminho = Path(sys.argv[1])
    x0, y0, x1, y1 = (int(v) for v in sys.argv[2:6])
    z0 = int(sys.argv[6]) if len(sys.argv) > 6 else 0
    z1 = int(sys.argv[7]) if len(sys.argv) > 7 else 15

    print(f"regiao: x {x0}-{x1} y {y0}-{y1} z {z0}-{z1}")
    dados = caminho.read_bytes()
    a = varrer(dados, (x0, y0, x1, y1, z0, z1))
    del dados

    print(f"tiles lidos na regiao: {a['tiles']}")
    if a["parciais"]:
        print(f"AVISO: {a['parciais']} no(s) com atributo nao reconhecido "
              f"-- leitura incompleta, trate o resultado como PISO minimo")

    def secao(chave, rotulo, fmt):
        itens = a[chave]
        print(f"\n{rotulo}: {len(itens)}")
        for v in itens[:25]:
            print("    " + fmt(v))
        if len(itens) > 25:
            print(f"    ... e mais {len(itens) - 25}")

    secao("tele", "TELEPORTS (mandariam o jogador pro mapa global)",
          lambda v: f"({v[0]},{v[1]},{v[2]}) item {v[3]} -> destino ({v[4]},{v[5]},{v[6]})")
    secao("action", "ACTION IDs (disparam scripts globais)",
          lambda v: f"({v[0]},{v[1]},{v[2]}) item {v[3]} aid={v[4]}")
    secao("unique", "UNIQUE IDs (duplicar quebra a unicidade)",
          lambda v: f"({v[0]},{v[1]},{v[2]}) item {v[3]} uid={v[4]}")
    secao("depot", "DEPOTS", lambda v: f"({v[0]},{v[1]},{v[2]}) depot={v[4]}")
    secao("porta", "PORTAS DE CASA", lambda v: f"({v[0]},{v[1]},{v[2]}) door={v[4]}")

    # ---- cruzar action ids com os scripts do datapack ----
    # Um action id pode ser um teleport em Lua (movements), que NAO aparece
    # como TELE_DEST no OTBM. Foi o caso do aid 48063 (Heart of Destruction),
    # que teleporta pro mapa global e passaria batido so olhando os tiles.
    aids = sorted({v[4] for v in a["action"]})
    if aids:
        raiz = Path(__file__).resolve().parents[2]
        alvos = [raiz / "data-otservbr-global", raiz / "data"]
        print(f"\n=== o que cada ACTION ID dispara (grep no datapack) ===")
        for aid in aids:
            achou = []
            for base in alvos:
                if not base.exists():
                    continue
                for lua in base.rglob("*.lua"):
                    try:
                        txt = lua.read_text(encoding="utf-8", errors="ignore")
                    except OSError:
                        continue
                    for linha in txt.splitlines():
                        if str(aid) in linha:
                            achou.append(
                                f"{lua.relative_to(raiz)}: {linha.strip()[:90]}")
                            break
                    if len(achou) >= 3:
                        break
            print(f"\n  aid {aid}:")
            if achou:
                for l in achou[:3]:
                    print(f"    {l}")
            else:
                print("    (nao encontrado no datapack -- pode ser inofensivo)")

    print(f"\nitens distintos na regiao: {len(a['itens'])}"
          f"  (total {sum(a['itens'].values())})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
