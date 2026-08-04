#!/usr/bin/env python3
"""Recorta uma regiao do OTBM num arquivo novo, pronto pra Game.loadMapChunk.

Etapa 0 / 1 da spec de hunt instanciada.

DOIS PONTOS QUE NAO SAO OBVIOS
------------------------------

1. COORDENADA REBASEADA. O carregador soma o offset ao que esta no arquivo:

       x = base_x + tileCoordsX + pos.x     (src/io/iomap.cpp:154)

   Se o recorte guardasse as coordenadas absolutas (32384...) e fosse carregado
   em 36864, daria 69248 -- estouro do uint16 e mapa corrompido em silencio.
   Por isso x/y saem REBASEADOS pra origem 0. O z fica ABSOLUTO (o andar da
   hunt continua sendo o 5..9), entao carregue sempre com pos.z = 0.

2. ESCAPE NA ESCRITA. Todo byte de dado que valha FD/FE/FF precisa de 0xFD na
   frente, senao vira marcador de no e a arvore inteira e' lida errada dali pra
   frente. E' o mesmo bug que existia no trocar_chao (ver testar_otbm.py).

O QUE E' REMOVIDO
-----------------
- towns e waypoints: sao parseados SEM offset e sobrescreveriam os globais
  quando o mesmo chunk e' carregado N vezes (spec 6.2);
- item com TELE_DEST: teleportaria pro mapa global, furando o InstanceManager;
- item com DEPOT_ID: daria acesso ao depot de dentro da instancia;
- atributo ACTION_ID: pode disparar script global -- inclusive teleport de
  quest em Lua, que NAO aparece como TELE_DEST (caso do aid 48063);
- atributo UNIQUE_ID: duplicar quebra a unicidade;
- atributo HOUSEDOORID e a associacao de casa: casas nao sao carregadas pelo
  loadMapChunk, a porta ficaria orfa. O item da porta e' MANTIDO, so perde o
  vinculo -- vira porta comum, e nao um buraco na parede.

    python3 recortar.py <origem.otbm> <destino.otbm> x0 y0 x1 y1 z0 z1
"""
from __future__ import annotations

import struct
import sys
from collections import defaultdict
from pathlib import Path

INICIO, FIM, ESCAPA = 0xFE, 0xFF, 0xFD
NO_RAIZ, NO_MAP_DATA = 0x00, 0x02
NO_AREA, NO_TILE, NO_ITEM, NO_CASA = 0x04, 0x05, 0x06, 0x0E
NO_ZONA = 19          # OTBM_TILE_ZONE -- filho de tile, nao de item
NO_TOWNS, NO_WAYPOINTS = 0x0C, 0x0F

A_ACTION, A_UNIQUE, A_TELE, A_DEPOT, A_HOUSEDOOR = 4, 5, 8, 10, 14

# tamanho fixo de cada atributo; None = string com prefixo u16
TAM = {
    1: None, 3: 4, 4: 2, 5: 2, 6: None, 7: None, 8: 5, 9: 2, 10: 2,
    12: 1, 14: 1, 15: 1, 16: 4, 17: 1, 18: 4, 19: None, 20: 4, 21: 4, 22: 2,
}

# atributos jogados fora (o item fica, o vinculo perigoso some)
ATTR_REMOVIDOS = {A_ACTION, A_UNIQUE, A_HOUSEDOOR}
# atributos que condenam o item inteiro
ATTR_MATA_ITEM = {A_TELE, A_DEPOT}


def escapar(dados: bytes) -> bytes:
    saida = bytearray()
    for b in dados:
        if b in (ESCAPA, INICIO, FIM):
            saida.append(ESCAPA)
        saida.append(b)
    return bytes(saida)


class Leitor:
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

    def u8(self):
        return self.byte()

    def u16(self):
        return struct.unpack("<H", self.bytes(2))[0]

    def u32(self):
        return struct.unpack("<I", self.bytes(4))[0]

    def espia(self) -> int:
        return self.d[self.i]


def ler_atributos(f: Leitor):
    """Devolve ([(attr, bruto)], matar_item) ou None se nao entendeu."""
    attrs, matar = [], False
    while True:
        b = f.espia()
        if b in (INICIO, FIM):
            return attrs, matar
        attr = f.u8()
        if attr not in TAM:
            return None
        tam = TAM[attr]
        if tam is None:
            n = f.u16()
            bruto = f.bytes(n)
            attrs.append((attr, struct.pack("<H", n) + bruto))
            continue
        bruto = f.bytes(tam)
        if attr in ATTR_MATA_ITEM:
            matar = True
        elif attr not in ATTR_REMOVIDOS:
            attrs.append((attr, bruto))


def emitir_attrs(attrs) -> bytes:
    saida = bytearray()
    for attr, bruto in attrs:
        saida.append(attr)              # o codigo do atributo nao e' escapado
        saida += escapar(bruto)
    return bytes(saida)


def ler_item(f: Leitor, dados: bytes):
    """Le um no de item, ja com o FE 06 consumido.

    Item pode ter FILHOS -- container guarda o conteudo como nos de item
    aninhados (BasicItem::unserializeItemNode, src/map/mapcache.cpp:502).
    Ignorar isso desalinha o parser e o recorte sai corrompido.

    Devolve (id, attrs, filhos, matar) ou None se nao entendeu.
    """
    iid = f.u16()
    lido = ler_atributos(f)
    if lido is None:
        return None
    attrs, matar = lido

    filhos = []
    while f.i < len(dados) and dados[f.i] == INICIO:
        f.i += 1
        if f.u8() != NO_ITEM:           # dentro de item so cabe item
            return None
        sub = ler_item(f, dados)
        if sub is None:
            return None
        filhos.append(sub)

    if f.i < len(dados) and dados[f.i] == FIM:
        f.i += 1
    return (iid, attrs, filhos, matar)


def emitir_item(item) -> bytes:
    iid, attrs, filhos, _ = item
    saida = bytearray([INICIO, NO_ITEM])
    saida += escapar(struct.pack("<H", iid))
    saida += emitir_attrs(attrs)
    for sub in filhos:
        saida += emitir_item(sub)
    saida.append(FIM)
    return bytes(saida)


def pular_zona(f: Leitor, dados: bytes) -> bool:
    """Consome um no OTBM_TILE_ZONE e o descarta.

    Zona e' vinculo GLOBAL: herdar a associacao do mapa original colocaria os
    tiles da instancia dentro de uma zona do mundo (PZ, boss, etc). A spec cria
    as zonas por Lua, uma por slot (secao 8.4). Aqui so precisa consumir os
    bytes certos pra nao desalinhar.
    """
    n = f.u16()
    for _ in range(n):
        f.u16()
    if f.i < len(dados) and dados[f.i] == FIM:
        f.i += 1
        return True
    return False


def recortar(dados: bytes, alvo):
    x0, y0, x1, y1, z0, z1 = alvo
    # (z, bx, by) -> [bytes de cada tile]
    areas: dict[tuple[int, int, int], list[bytes]] = defaultdict(list)
    stats = dict(tiles=0, itens=0, mortos=0, casas=0, zonas=0, parciais=0)

    prefixo = bytes([INICIO, NO_AREA])
    pos = -1
    while True:
        pos = dados.find(prefixo, pos + 1)
        if pos < 0:
            break
        if pos > 0 and dados[pos - 1] == ESCAPA:
            continue
        f = Leitor(dados, pos + 2)
        try:
            bx, by, bz = f.u16(), f.u16(), f.u8()
        except IndexError:
            continue
        if f.i >= len(dados) or dados[f.i] != INICIO:
            continue
        if not (z0 <= bz <= z1 and bx <= x1 and bx + 255 >= x0
                and by <= y1 and by + 255 >= y0):
            continue

        while f.i < len(dados) and dados[f.i] == INICIO:
            f.i += 1
            tipo = f.u8()
            if tipo not in (NO_TILE, NO_CASA):
                break
            dx, dy = f.u8(), f.u8()
            tx, ty = bx + dx, by + dy
            if tipo == NO_CASA:
                f.u32()                       # id da casa: descartado
                stats["casas"] += 1
            dentro = (x0 <= tx <= x1 and y0 <= ty <= y1)

            lido = ler_atributos(f)
            if lido is None:
                stats["parciais"] += 1
                break
            tattrs, _ = lido

            itens = []
            ok = True
            while f.i < len(dados) and dados[f.i] == INICIO:
                f.i += 1
                tipo_filho = f.u8()
                if tipo_filho == NO_ITEM:
                    item = ler_item(f, dados)
                    if item is None:
                        stats["parciais"] += 1
                        ok = False
                        break
                    if dentro:
                        if item[3]:                 # matar: teleport/depot
                            stats["mortos"] += 1
                        else:
                            itens.append(item)
                            stats["itens"] += 1
                elif tipo_filho == NO_ZONA:
                    if not pular_zona(f, dados):
                        stats["parciais"] += 1
                        ok = False
                        break
                    if dentro:
                        stats["zonas"] += 1
                else:
                    stats["parciais"] += 1          # no desconhecido: aborta
                    ok = False
                    break
            if not ok:
                break

            if dentro:
                nx, ny = tx - x0, ty - y0     # rebase pra origem 0
                corpo = bytearray([INICIO, NO_TILE])
                corpo += escapar(bytes([nx & 0xFF, ny & 0xFF]))
                corpo += emitir_attrs(tattrs)
                for item in itens:
                    corpo += emitir_item(item)
                corpo.append(FIM)
                areas[(bz, nx & 0xFF00, ny & 0xFF00)].append(bytes(corpo))
                stats["tiles"] += 1

            if f.i < len(dados) and dados[f.i] == FIM:
                f.i += 1

    return areas, stats


def attr_string(codigo: int, texto: bytes) -> bytes:
    return bytes([codigo]) + escapar(struct.pack("<H", len(texto)) + texto)


def montar(areas, larg: int, alt: int) -> bytes:
    corpo = bytearray()

    # Atributos do MAP_DATA. Um chunk que carrega (fury_gates/carlin.otbm) traz
    # DESCRIPTION aqui; emitir no mesmo formato evita depender do caminho de
    # "atributo ausente" do parseMapDataAttributes.
    corpo += attr_string(1, b"Recorte gerado por tools/mapa/recortar.py")
    corpo += attr_string(1, b"Hunt instanciada - sem towns, waypoints ou casas")

    # NAO emitimos EXT_SPAWN_MONSTER_FILE / EXT_HOUSE_FILE / EXT_SPAWN_NPC_FILE:
    # apontariam pra XMLs que nao existem. O loadMapChunk nao carrega nada
    # disso mesmo (loadMonsters/Houses/Npcs/Zones vem false).

    for (z, bx, by) in sorted(areas):
        corpo += bytes([INICIO, NO_AREA])
        corpo += escapar(struct.pack("<HHB", bx, by, z))
        for t in areas[(z, bx, by)]:
            corpo += t
        corpo.append(FIM)

    # TOWNS e WAYPOINTS VAZIOS. O parseTowns/parseWaypoints roda logo apos o
    # tile area; o chunk oficial traz os dois nos vazios. Vazio nao sobrescreve
    # nada global -- o que a spec 6.2 proibe e' town/waypoint COM conteudo.
    corpo += bytes([INICIO, NO_TOWNS, FIM])
    corpo += bytes([INICIO, NO_WAYPOINTS, FIM])

    mapdata = bytes([INICIO, NO_MAP_DATA]) + bytes(corpo) + bytes([FIM])
    raiz = (bytes([INICIO, NO_RAIZ])
            + escapar(struct.pack("<IHHII", 4, larg, alt, 4, 4))
            + mapdata + bytes([FIM]))
    return b"\0\0\0\0" + raiz


def main() -> int:
    if len(sys.argv) < 9:
        print(__doc__)
        return 2
    origem, destino = Path(sys.argv[1]), Path(sys.argv[2])
    x0, y0, x1, y1, z0, z1 = (int(v) for v in sys.argv[3:9])

    print(f"origem : {origem}")
    print(f"regiao : x {x0}-{x1}  y {y0}-{y1}  z {z0}-{z1}")
    print(f"         {x1 - x0 + 1} x {y1 - y0 + 1}, {z1 - z0 + 1} andares")

    dados = origem.read_bytes()
    areas, st = recortar(dados, (x0, y0, x1, y1, z0, z1))
    del dados

    if st["parciais"]:
        print(f"\nAVISO: {st['parciais']} no(s) nao reconhecido(s)."
              f" O recorte esta INCOMPLETO -- nao use sem investigar.")

    saida = montar(areas, x1 - x0 + 1, y1 - y0 + 1)
    destino.write_bytes(saida)

    print(f"\ntiles gravados      : {st['tiles']}")
    print(f"itens gravados      : {st['itens']}")
    print(f"itens removidos     : {st['mortos']}  (teleport/depot)")
    print(f"tiles de casa       : {st['casas']}  (vinculo removido)")
    print(f"nos de zona         : {st['zonas']}  (descartados)")
    print(f"areas geradas       : {len(areas)}")
    print(f"\ndestino: {destino}  ({len(saida) / 1024:.0f} KB)")
    print("\ncoordenadas REBASEADAS pra origem 0 em x/y; z mantido absoluto.")
    print(f"carregue com:  Game.loadMapChunk(caminho, Position(OX, OY, 0))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
