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

import re
import struct
from array import array
from dataclasses import dataclass, field
from pathlib import Path

INICIO, FIM, ESCAPA = 0xFE, 0xFF, 0xFD

# Bytes que nunca podem aparecer crus dentro de um dado, porque o carregador
# os leria como marcador de no.
MARCADORES = (ESCAPA, INICIO, FIM)

# Os mesmos tres bytes como classe de regex: serve para pular de marcador em
# marcador sem olhar byte por byte em Python (ver _fim_do_no).
_MARCADOR = re.compile(rb"[\xfd\xfe\xff]")


def escapar(dados: bytes) -> bytes:
    """Poe o 0xFD na frente de todo byte de dado que valha FD/FE/FF.

    E' o inverso do _ler_dados. Quem grava PRECISA passar por aqui: um id como
    21501 ('dirt floor') vira `fd 53` em u16, e gravar esse FD cru injeta um
    escape no meio do fluxo — dali em diante a arvore inteira e' lida errada.
    Dos 14147 itens do items.xml, 160 (1,1%) tem essa forma.
    """
    saida = bytearray()
    for b in dados:
        if b in MARCADORES:
            saida.append(ESCAPA)
        saida.append(b)
    return bytes(saida)


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
    chao_bytes: int = 0   # quantos bytes CRUS o id do chao ocupa (2, 3 ou 4)
    itens: list[tuple[int, int, int]] = field(default_factory=list)
    # (id, offset_do_no, offset_do_fim)


class _IndiceArea:
    """Onde comeca cada tile de uma area 256x256, em arrays paralelos.

    Guardar isso como dicionario de (dx, dy) -> tupla custava 17 MB por area.
    Como a area e' uma grade fixa de 256x256, um indice calculado
    (dy << 8 | dx) sobre quatro arrays de tipo primitivo diz o mesmo em
    0,8 MB. Offset 0 significa "nao existe": o byte 0 do arquivo e' o
    cabecalho, nunca um tile.
    """

    __slots__ = ("ini", "fim", "tipo", "apos", "n")

    def __init__(self):
        vazio = array("i", bytes(4 * 65536))
        self.ini = vazio
        self.fim = array("i", bytes(4 * 65536))
        self.apos = array("i", bytes(4 * 65536))
        self.tipo = array("b", bytes(65536))
        self.n = 0


class Mapa:
    def __init__(self, caminho: str | Path, *, cache_tiles: bool = True,
                 limite_areas: int = 24, mapear: bool = False):
        """`cache_tiles` guarda o Tile ja lido; `limite_areas` e' o teto do
        indice de areas; `mapear` le o arquivo por mmap.

        Quem so desenha (o servidor do mapeador) le cada tile uma vez por
        bloco e nao ganha nada em guardar: eram 35 MB por area, e explorar o
        mapa levava o processo a varios GB. Quem edita costuma voltar no
        mesmo tile e mantem o cache, que e' o padrao.

        Com `mapear`, os 176 MB do mapa ficam em paginas do sistema em vez de
        na memoria do processo -- o sistema descarta o que nao esta em uso.
        Em troca o arquivo fica preso enquanto o objeto viver, entao quem
        edita e grava no mesmo caminho nao deve usar.
        """
        self.caminho = Path(caminho)
        self._arquivo = self._mapa_mm = None
        if mapear:
            import mmap as _mmap
            self._arquivo = open(self.caminho, "rb")
            self._mapa_mm = _mmap.mmap(self._arquivo.fileno(), 0,
                                       access=_mmap.ACCESS_READ)
            self.dados = self._mapa_mm
        else:
            self.dados = self.caminho.read_bytes()
        self.cache_tiles = cache_tiles
        self.limite_areas = limite_areas
        self._areas: dict[tuple[int, int, int], list[int]] = {}
        # offsets crus por area (barato) e tiles ja lidos (caro, sob demanda)
        self._cruas: dict[tuple[int, int, int], _IndiceArea] = {}
        self._tiles: dict[tuple[int, int, int], dict[int, Tile]] = {}
        self._edicoes: list[tuple[int, int, bytes]] = []   # (offset, apaga, insere)

    # ---------------------------------------------------------- estrutura

    @property
    def cabecalho(self):
        """(versao, largura, altura, major_items, minor_items)."""
        return struct.unpack("<IHHII", self.dados[6:22])

    def _fim_do_no(self, i: int) -> int:
        """Offset do 0xFF que fecha o no aberto em i.

        Pula de marcador em marcador em vez de andar byte a byte: quase todo
        byte de um no e' dado comum, e a busca em Python custava 30% do tempo
        de desenhar uma regiao. O regex varre em C e so devolve o que importa.
        """
        d = self.dados
        j, nivel = i + 1, 1
        busca = _MARCADOR.search
        while True:
            m = busca(d, j)
            if m is None:
                raise ValueError(f"no em {i} nao fecha")
            j = m.start()
            b = d[j]
            if b == ESCAPA:                    # 0xFD protege o byte seguinte
                j += 2
                continue
            if b == INICIO:
                nivel += 1
            else:                              # FIM
                nivel -= 1
                if nivel == 0:
                    return j
            j += 1

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

    def _ler_dados(self, i: int, n: int) -> tuple[bytes, int]:
        """Le n bytes de conteudo a partir de i, desfazendo o escape.

        O OTBM escapa com 0xFD qualquer byte de dado que valha FD/FE/FF. Ler
        cru faz as coordenadas 253-255 de cada area sairem erradas — e como
        area tem 256x256, isso apagava as ultimas linhas e colunas de cada
        area, formando uma grade de buracos a cada 256 tiles.

        Devolve (conteudo, proximo offset cru).
        """
        d = self.dados
        # atalho: sem 0xFD nos proximos n bytes, o conteudo e' a fatia crua.
        # Escape e' raro (1,1% dos ids do items.xml), entao esse e' o caminho
        # normal, e a fatia sai em C em vez de byte a byte.
        bloco = d[i:i + n]
        if ESCAPA not in bloco:
            return bloco, i + n
        out = bytearray()
        while len(out) < n:
            if d[i] == ESCAPA:
                i += 1
            out.append(d[i])
            i += 1
        return bytes(out), i

    def _indexar(self, base: tuple[int, int, int]) -> _IndiceArea:
        """Onde comeca cada tile de uma area 256x256.

        NAO le o conteudo do tile. Ler custa caro (percorre atributos e cada
        no de item) e a area tem 65536 tiles, mas quem pede uma regiao de
        128x128 so usa um quarto deles. Antes isso gastava 1,9 s por area; o
        conteudo agora sai no `tile()`, um tile por vez.
        """
        idx = self._cruas.get(base)
        if idx is not None:
            self._cruas[base] = self._cruas.pop(base)      # marca como recente
            return idx

        d = self.dados
        idx = _IndiceArea()
        a_ini, a_fim, a_apos, a_tipo = idx.ini, idx.fim, idx.apos, idx.tipo
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
                    (dx, dy), apos = self._ler_dados(i + 2, 2)
                    k = (dy << 8) | dx
                    if not a_ini[k]:
                        idx.n += 1
                    a_ini[k], a_fim[k], a_apos[k], a_tipo[k] = i, fim, apos, tipo
                i = fim + 1

        self._cruas[base] = idx
        while len(self._cruas) > self.limite_areas:
            velha, _ = next(iter(self._cruas.items()))
            self._cruas.pop(velha)
            self._tiles.pop(velha, None)
            self._areas.pop(velha, None)
        return idx

    def _ler_tile(self, ini, fim, tipo, x, y, z, apos_coords) -> Tile:
        d = self.dados
        casa = tipo == NO_CASA
        j = apos_coords                        # ja passou pelas coordenadas
        if casa:
            _, j = self._ler_dados(j, 4)       # tile de casa traz o id da casa
        chao_off = chao = None
        chao_bytes = 0
        itens: list[tuple[int, int, int]] = []
        while j < fim:
            b = d[j]
            if b == INICIO:
                if d[j + 1] == NO_ITEM:
                    f = self._fim_do_no(j)
                    ident, _ = self._ler_dados(j + 2, 2)
                    itens.append((struct.unpack("<H", ident)[0], j, f))
                    j = f + 1
                    continue
                j = self._fim_do_no(j) + 1
                continue
            if b == ATTR_ITEM:
                chao_off = j + 1
                ident, j = self._ler_dados(j + 1, 2)
                chao = struct.unpack("<H", ident)[0]
                # guarda o tamanho CRU, que passa de 2 quando o id vem
                # escapado. Sem isso o trocar_chao apagaria 2 bytes de um
                # campo de 3 e deixaria um byte orfao no lugar.
                chao_bytes = j - chao_off
            elif b == ATTR_FLAGS:
                _, j = self._ler_dados(j + 1, 4)
            else:                              # atributo desconhecido: para aqui
                break
        return Tile(x, y, z, ini, fim, casa, chao_off, chao, chao_bytes, itens)

    # ------------------------------------------------------------ leitura

    def tile(self, x: int, y: int, z: int) -> Tile | None:
        base = (x & 0xFF00, y & 0xFF00, z)
        chave = ((y & 0xFF) << 8) | (x & 0xFF)
        if self.cache_tiles:
            prontos = self._tiles.get(base)
            if prontos is None:
                prontos = self._tiles[base] = {}
            elif chave in prontos:
                return prontos[chave]
        idx = self._indexar(base)
        ini = idx.ini[chave]
        if not ini:
            return None
        t = self._ler_tile(ini, idx.fim[chave], idx.tipo[chave], x, y, z,
                           idx.apos[chave])
        if self.cache_tiles:
            self._tiles[base][chave] = t
        return t

    def regiao(self, x1, y1, x2, y2, z):
        for y in range(y1, y2 + 1):
            for x in range(x1, x2 + 1):
                t = self.tile(x, y, z)
                if t:
                    yield t

    def areas(self) -> list[tuple[int, int, int]]:
        """Todas as bases (x, y, z) de area 256x256 presentes no arquivo.

        Serve para varrer o mapa inteiro sem saber as coordenadas de antemao —
        o `tile()` e o `regiao()` exigem saber onde procurar. Usa o mesmo
        criterio do _offsets_de_area: o byte seguinte a base tem de ser INICIO,
        porque area so tem filhos e nunca atributo.
        """
        d, n = self.dados, len(self.dados)
        assinatura = bytes([INICIO, NO_AREA])
        bases, pos = set(), -1
        while True:
            pos = d.find(assinatura, pos + 1)
            if pos < 0:
                break
            if pos + 8 > n or d[pos + 7] != INICIO:
                continue
            bases.add(struct.unpack_from("<HHB", d, pos + 2))
        return sorted(bases)

    def tiles_da_area(self, base: tuple[int, int, int]):
        """Tiles de uma area inteira, lidos um a um."""
        bx, by, bz = base
        ini = self._indexar(base).ini
        for k in range(65536):
            if ini[k]:
                t = self.tile(bx + (k & 0xFF), by + (k >> 8), bz)
                if t:
                    yield t

    def esquecer_area(self, base: tuple[int, int, int]) -> None:
        """Descarta o cache de uma area.

        O _indexar guarda os tiles de toda area lida, o que e' o certo para uso
        pontual mas impede varrer o mapa inteiro: sao ~10 milhoes de objetos
        vivos ao mesmo tempo. Quem varre deve chamar isto ao terminar cada area.
        """
        self._tiles.pop(base, None)
        self._cruas.pop(base, None)
        self._areas.pop(base, None)

    # ------------------------------------------------------------- edicao

    def trocar_chao(self, x, y, z, item_id: int) -> bool:
        """Troca o chao do tile.

        Apaga o campo pelo tamanho CRU que ele ocupa (`chao_bytes`, que e' 3 ou
        4 quando o id antigo vinha escapado) e grava o novo ja escapado. O campo
        pode mudar de tamanho, e tudo bem: o `salvar` aplica de tras pra frente,
        entao um deslocamento aqui nao invalida as edicoes anteriores.
        """
        t = self.tile(x, y, z)
        if not t or t.chao_off is None:
            return False
        self._edicoes.append(
            (t.chao_off, t.chao_bytes, escapar(struct.pack("<H", item_id))))
        return True

    def adicionar_item(self, x, y, z, item_id: int) -> bool:
        """Poe um item no topo da pilha do tile."""
        t = self.tile(x, y, z)
        if not t:
            return False
        # INICIO/FIM e o tipo do no vao crus — sao a moldura do no, nao dado.
        # So o id passa pelo escape.
        no = (bytes([INICIO, NO_ITEM])
              + escapar(struct.pack("<H", item_id))
              + bytes([FIM]))
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
        self._cruas.clear()
        self._tiles.clear()
        self._edicoes.clear()
        return destino
