#!/usr/bin/env python3
"""Valida um OTBM imitando EXATAMENTE o leitor do Canary.

O parser do otbm.py e' tolerante; o do servidor nao e'. Quando o servidor diz
so "missing or corrupted" (ele engole o e.what(), src/map/map.cpp:153), este
script reproduz o mesmo caminho de leitura e diz em que byte quebrou.

Espelha: FileStream::startNode/endNode/isProp/getU8 (escape so quando
m_nodes>0), IOMap::loadMap, parseMapDataAttributes, parseTileArea e
BasicItem::unserializeItemNode.

    python3 validar_otbm.py <arquivo.otbm>
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

START, END, ESCAPE = 0xFE, 0xFF, 0xFD
MAP_DATA, TILE_AREA, TILE, ITEM, HOUSETILE, TILE_ZONE = 2, 4, 5, 6, 14, 19
ATTR_TILE_FLAGS, ATTR_ITEM = 3, 9


class Erro(Exception):
    pass


class Fluxo:
    """Copia fiel do FileStream do Canary."""

    def __init__(self, d: bytes, ini: int):
        self.d, self.pos, self.nodes = d, ini, 0

    def _escapado(self) -> int:
        if self.pos >= len(self.d):
            raise Erro(f"leitura alem do fim em {self.pos}")
        if self.d[self.pos] == ESCAPE:
            self.pos += 1
            if self.pos >= len(self.d):
                raise Erro(f"escape truncado em {self.pos}")
        v = self.d[self.pos]
        self.pos += 1
        return v

    def u8(self) -> int:
        if self.nodes > 0:
            return self._escapado()
        if self.pos >= len(self.d):
            raise Erro("fim inesperado")
        v = self.d[self.pos]
        self.pos += 1
        return v

    def _n(self, n: int) -> int:
        return int.from_bytes(bytes(self.u8() for _ in range(n)), "little")

    def u16(self):
        return self._n(2)

    def u32(self):
        return self._n(4)

    def back(self, n: int = 1):
        self.pos -= n

    def skip(self, n: int):
        self.pos += n

    def start(self, tipo: int = 0) -> bool:
        p = self.pos
        if self.u8() == START:
            if tipo == 0:
                self.nodes += 1
                return True
            if self.u8() == tipo:
                self.nodes += 1
                return True
        self.pos = p                    # o Canary faz back() duas vezes
        return False

    def end(self) -> bool:
        p = self.pos
        if self.u8() == END:
            self.nodes -= 1
            return True
        self.pos = p
        return False

    def prop(self, alvo: int) -> bool:
        p = self.pos
        if self.u8() == alvo:
            return True
        self.pos = p
        return False

    def string(self) -> bytes:
        n = self.u16()
        if n >= 8192:
            raise Erro(f"string grande demais ({n}) em {self.pos}")
        s = self.d[self.pos:self.pos + n]      # o Canary le CRU aqui
        self.pos += n
        return s


TAM_ATTR = {1: None, 3: 4, 4: 2, 5: 2, 6: None, 7: None, 8: 5, 9: 2, 10: 2,
            12: 1, 14: 1, 15: 1, 16: 4, 17: 1, 18: 4, 19: None, 20: 4,
            21: 4, 22: 2}


def ler_attrs_item(f: Fluxo):
    """Espelha BasicItem::readAttr -- para no primeiro nao-atributo."""
    while True:
        p = f.pos
        b = f.u8()
        if b in (START, END):
            f.pos = p
            return
        if b not in TAM_ATTR:
            raise Erro(f"atributo de item desconhecido {b} em {p}")
        t = TAM_ATTR[b]
        if t is None:
            f.string()
        else:
            for _ in range(t):
                f.u8()


def ler_item(f: Fluxo, prof: int = 0):
    if prof > 20:
        raise Erro("aninhamento de item profundo demais")
    f.u16()                                    # id
    if f.prop(END):
        f.back()
        return
    ler_attrs_item(f)
    while f.start():
        if f.u8() != ITEM:
            raise Erro(f"filho de item nao e' item, em {f.pos}")
        ler_item(f, prof + 1)
        if not f.end():
            raise Erro(f"item filho nao fecha, em {f.pos}")


def validar(d: bytes) -> dict:
    f = Fluxo(d, 4)                            # pula o identificador de 4 bytes
    if not f.start():
        raise Erro("no raiz nao abre")
    f.skip(1)                                  # byte de tipo
    versao, larg, alt = f.u32(), f.u16(), f.u16()
    major, _minor = f.u32(), f.u32()
    if versao > 5:
        raise Erro(f"versao OTBM desconhecida: {versao}")
    if major < 3:
        raise Erro(f"majorVersionItems={major} < 3 -- mapa precisa ser "
                   f"atualizado no editor")

    st = dict(versao=versao, larg=larg, alt=alt, major=major,
              areas=0, tiles=0, itens=0, zonas=0)

    if f.start(MAP_DATA):
        # parseMapDataAttributes: consome atributos ate um desconhecido
        while True:
            p = f.pos
            b = f.u8()
            if b in (1, 11, 13, 23, 24):
                f.string()
                continue
            f.pos = p
            break

        while f.start(TILE_AREA):
            st["areas"] += 1
            f.u16(), f.u16(), f.u8()           # base x, y, z
            while f.start():
                tipo = f.u8()
                if tipo not in (TILE, HOUSETILE):
                    raise Erro(f"tipo de tile invalido {tipo} em {f.pos}")
                st["tiles"] += 1
                f.u8(), f.u8()                 # dx, dy
                if tipo == HOUSETILE:
                    f.u32()
                if f.prop(ATTR_TILE_FLAGS):
                    f.u32()
                if f.prop(ATTR_ITEM):
                    f.u16()
                while f.start():
                    t = f.u8()
                    if t == ITEM:
                        st["itens"] += 1
                        ler_item(f)
                    elif t == TILE_ZONE:
                        st["zonas"] += 1
                        n = f.u16()
                        for _ in range(n):
                            if f.u16() == 0:
                                raise Erro("zone id invalido")
                    else:
                        raise Erro(f"no de item/zona invalido {t} em {f.pos}")
                    if not f.end():
                        raise Erro(f"no filho nao fecha em {f.pos}")
                if not f.end():
                    raise Erro(f"tile nao fecha em {f.pos}")
            if not f.end():
                raise Erro(f"area nao fecha em {f.pos}")
        if not f.end():
            raise Erro(f"map data nao fecha em {f.pos}")
    return st


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    caminho = Path(sys.argv[1])
    d = caminho.read_bytes()
    print(f"{caminho}  ({len(d) / 1024:.0f} KB)")
    try:
        st = validar(d)
    except Erro as e:
        print(f"\nREJEITADO: {e}")
        return 1
    print(f"\nACEITO pelo caminho de leitura do Canary")
    print(f"  versao={st['versao']}  {st['larg']}x{st['alt']}  major={st['major']}")
    print(f"  areas={st['areas']}  tiles={st['tiles']}  "
          f"itens={st['itens']}  zonas={st['zonas']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
