#!/usr/bin/env python3
"""Leitura e edicao do mapa OTBM, direto nos bytes.

O OTBM e uma arvore de nos com marcadores no meio do fluxo de bytes:

    0xFE  comeca um no, seguido do byte de tipo
    0xFF  fecha o no
    0xFD  escapa o proximo byte (para quando o dado vale FD/FE/FF)

A hierarquia que interessa e ``raiz > map data > tile area > tile > item``.
Cada **tile area** cobre 256x256 e traz a posicao base (x, y, z); dentro
dela cada **tile** guarda so o deslocamento de 1 byte em x e y. O chao
costuma vir como atributo do tile (``0x09`` seguido do id em u16) e o resto
empilhado como nos de item.

O mapa global tem 177 MB, entao nada aqui percorre o arquivo inteiro: a
gente acha os nos de area pela assinatura de bytes (busca em C, rapida) e
so entao percorre esses pedacos. Reparar que o **mesmo par (x, y, z) de
base aparece em varios nos de area** — o editor de mapa reemite o
cabecalho conforme escreve, e o carregador simplesmente processa todos.

As edicoes sao acumuladas e aplicadas de tras pra frente, senao a primeira
insercao invalidaria o deslocamento de todas as seguintes.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path

INICIO, FIM, ESCAPA = 0xFE, 0xFF, 0xFD

NO_RAIZ, NO_MAP_DATA = 0x00, 0x02
NO_AREA, NO_TILE, NO_ITEM = 0x04, 0x05, 0x06
NO_CASA = 0x0E

ATTR_ITEM = 0x09          # chao do tile: 0x09 + id em u16
ATTR_FLAGS = 0x03         # flags do tile: 0x03 + u32


@dataclass
class Tile:
    x: int
    y: int
    z: int
    inicio: int           # offset do 0xFE do no
    fim: int              # offset do 0xFF que fecha
    casa: bool
    chao_off: int | None  # offset do id do chao (u16), se houver
    chao: int | None
    itens: list[tuple[int, int, int]] = field(default_factory=list)
    # (id, offset_do_no, offset_do_fim)


class Mapa:
    def __init__(self, caminho: str | Path):
        self.caminho = Path(caminho)
        self.dados = self.caminho.read_bytes()
        self._areas: dict[tuple[int, int, int], list[int]] = {}
        self._tiles: dict[tuple[int, int, int], dict[tuple[int, int], Tile]] = {}
        self._edicoes: list[tuple[int, int, bytes]] = []   # (offset, apaga, insere)

    # ---------------------------------------------------------- estrutura

    @property
    def cabecalho(self):
        """(versao, largura, altura, major_items, minor_items)."""
        return struct.unpack("<IHHII", self.dados[6:22])

    def _fim_do_no(self, i: int) -> int:
        d, n = self.dados, len(self.dados)
        j, nivel = i + 1, 1
        while j < n:
            b = d[j]
            if b == ESCAPA:
                j += 2
                continue
            if b == INICIO:
                nivel += 1
            elif b == FIM:
                nivel -= 1
                if nivel == 0:
                    return j
            j += 1
        raise ValueError(f"no em {i} nao fecha")

    def _offsets_de_area(self, base: tuple[int, int, int]) -> list[int]:
        if base in self._areas:
            return self._areas[base]
        assinatura = bytes([INICIO, NO_AREA]) + struct.pack("<HHB", *base)
        achados, pos = [], -1
        d = self.dados
        while True:
            pos = d.find(assinatura, pos + 1)
            if pos < 0:
                break
            if d[pos + 7] == INICIO:      # area so tem filhos, nunca atributo
                achados.append(pos)
        self._areas[base] = achados
        return achados

    def _indexar(self, base: tuple[int, int, int]) -> dict[tuple[int, int], Tile]:
        """Mapeia (dx, dy) -> Tile para uma area 256x256 inteira."""
        if base in self._tiles:
            return self._tiles[base]

        d = self.dados
        bx, by, bz = base
        tiles: dict[tuple[int, int], Tile] = {}
        for pos in self._offsets_de_area(base):
            limite = self._fim_do_no(pos)
            i = pos + 7
            while i < limite:
                if d[i] != INICIO:
                    i += 1
                    continue
                tipo = d[i + 1]
                fim = self._fim_do_no(i)
                if tipo in (NO_TILE, NO_CASA):
                    dx, dy = d[i + 2], d[i + 3]
                    tiles[(dx, dy)] = self._ler_tile(i, fim, tipo, bx + dx, by + dy, bz)
                i = fim + 1
        self._tiles[base] = tiles
        return tiles

    def _ler_tile(self, ini, fim, tipo, x, y, z) -> Tile:
        d = self.dados
        casa = tipo == NO_CASA
        j = ini + 4 + (4 if casa else 0)      # tile de casa traz o id da casa
        chao_off = chao = None
        itens: list[tuple[int, int, int]] = []
        while j < fim:
            b = d[j]
            if b == INICIO:
                if d[j + 1] == NO_ITEM:
                    f = self._fim_do_no(j)
                    itens.append((struct.unpack("<H", d[j + 2:j + 4])[0], j, f))
                    j = f + 1
                    continue
                j = self._fim_do_no(j) + 1
                continue
            if b == ATTR_ITEM:
                chao_off = j + 1
                chao = struct.unpack("<H", d[j + 1:j + 3])[0]
                j += 3
            elif b == ATTR_FLAGS:
                j += 5
            else:                              # atributo desconhecido: para aqui
                break
        return Tile(x, y, z, ini, fim, casa, chao_off, chao, itens)

    # ------------------------------------------------------------ leitura

    def tile(self, x: int, y: int, z: int) -> Tile | None:
        base = (x & 0xFF00, y & 0xFF00, z)
        return self._indexar(base).get((x & 0xFF, y & 0xFF))

    def regiao(self, x1, y1, x2, y2, z):
        for y in range(y1, y2 + 1):
            for x in range(x1, x2 + 1):
                t = self.tile(x, y, z)
                if t:
                    yield t

    # ------------------------------------------------------------- edicao

    def trocar_chao(self, x, y, z, item_id: int) -> bool:
        """Troca o chao no lugar — mesmo tamanho, sem mexer nos offsets."""
        t = self.tile(x, y, z)
        if not t or t.chao_off is None:
            return False
        self._edicoes.append((t.chao_off, 2, struct.pack("<H", item_id)))
        return True

    def adicionar_item(self, x, y, z, item_id: int) -> bool:
        """Poe um item no topo da pilha do tile."""
        t = self.tile(x, y, z)
        if not t:
            return False
        no = bytes([INICIO, NO_ITEM]) + struct.pack("<H", item_id) + bytes([FIM])
        self._edicoes.append((t.fim, 0, no))     # antes do 0xFF que fecha o tile
        return True

    def limpar_itens(self, x, y, z) -> int:
        """Tira tudo que esta em cima do chao."""
        t = self.tile(x, y, z)
        if not t:
            return 0
        for _, ini, fim in t.itens:
            self._edicoes.append((ini, fim - ini + 1, b""))
        return len(t.itens)

    @property
    def pendentes(self) -> int:
        return len(self._edicoes)

    def salvar(self, destino: str | Path | None = None) -> Path:
        """Aplica as edicoes de tras pra frente e grava."""
        d = bytearray(self.dados)
        for offset, apaga, insere in sorted(self._edicoes, key=lambda e: -e[0]):
            d[offset:offset + apaga] = insere
        destino = Path(destino) if destino else self.caminho
        destino.write_bytes(bytes(d))
        self.dados = bytes(d)
        self._areas.clear()
        self._tiles.clear()
        self._edicoes.clear()
        return destino
