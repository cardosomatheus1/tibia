#!/usr/bin/env python3
"""Leitura e escrita dos assets de sprite do Tibia 12+/15.

Cobre as três peças que um sprite novo precisa tocar:

* **folhas de sprite** — arquivos ``sprites-<sha>.bmp.lzma``: um BMP de
  384x384 em BGRA, comprimido em LZMA1 cru dentro de um cabeçalho de 32
  bytes da CipSoft;
* **``catalog-content.json``** — diz ao client qual folha guarda qual faixa
  de ``spriteid``;
* **``appearances.dat``** — protobuf que descreve objetos, outfits, efeitos
  e missiles em cima desses spriteids.

Nada aqui depende do ``protoc``: o appearances.dat é lido e escrito no
formato de fio do protobuf direto, porque só precisamos *acrescentar*
mensagens no fim do arquivo — que é exatamente o que o protobuf permite
fazer com campos repetidos.
"""
from __future__ import annotations

import hashlib
import json
import lzma
import struct
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

# ---------------------------------------------------------------- folhas

LADO_FOLHA = 384
MARCA_CIP = bytes([0x70, 0x0A, 0xFA, 0x80, 0x24])
TAM_CABECALHO_CIP = 32

# spritetype do catálogo -> tamanho do sprite em pixels
TAMANHOS = {0: (32, 32), 1: (32, 64), 2: (64, 32), 3: (64, 64)}


def sprites_por_folha(spritetype: int) -> int:
    larg, alt = TAMANHOS[spritetype]
    return (LADO_FOLHA // larg) * (LADO_FOLHA // alt)


def _varint(n: int) -> bytes:
    saida = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        saida.append(b | (0x80 if n else 0))
        if not n:
            return bytes(saida)


def ler_folha(caminho: str | Path) -> Image.Image:
    """Descomprime uma folha .bmp.lzma e devolve uma imagem RGBA 384x384."""
    d = Path(caminho).read_bytes()

    i = 0
    while d[i] == 0x00:                       # padding de nulos
        i += 1
    i += 1                                    # 0x70
    if d[i - 1:i + 4] != MARCA_CIP:
        raise ValueError(f"{caminho}: cabeçalho CIP inesperado")
    i += 4                                    # 0A FA 80 24
    while d[i] & 0x80:                        # tamanho em 7-bit
        i += 1
    i += 1

    props = d[i]
    dicionario = struct.unpack("<I", d[i + 1:i + 5])[0]
    filtros = [{
        "id": lzma.FILTER_LZMA1,
        "lc": props % 9,
        "lp": (props // 9) % 5,
        "pb": (props // 9) // 5,
        "dict_size": dicionario,
    }]
    # os 8 bytes seguintes são o "tamanho comprimido" da CIP, não o do LZMA
    bruto = lzma.LZMADecompressor(format=lzma.FORMAT_RAW,
                                  filters=filtros).decompress(d[i + 13:])

    deslocamento = struct.unpack("<I", bruto[10:14])[0]
    pixels = bruto[deslocamento:deslocamento + LADO_FOLHA * LADO_FOLHA * 4]

    img = Image.frombytes("RGBA", (LADO_FOLHA, LADO_FOLHA), pixels)
    b, g, r, a = img.split()                  # BGRA -> RGBA
    img = Image.merge("RGBA", (r, g, b, a))
    return img.transpose(Image.FLIP_TOP_BOTTOM)   # BMP é de baixo pra cima


# cabeçalho BMP de 122 bytes (BITMAPV4HEADER, 32bpp com máscaras) — o mesmo
# que a CipSoft usa, então o offset de pixels cai em 122 como no original
def _cabecalho_bmp() -> bytes:
    tam_pixels = LADO_FOLHA * LADO_FOLHA * 4
    arquivo = struct.pack("<2sIHHI", b"BM", 122 + tam_pixels, 0, 0, 122)
    info = struct.pack(
        "<IiiHHIIiiII", 108, LADO_FOLHA, LADO_FOLHA, 1, 32, 3,
        tam_pixels, 2835, 2835, 0, 0)
    mascaras = struct.pack("<IIII", 0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000)
    return arquivo + info + mascaras + b"BGRs" + bytes(108 - 40 - 16 - 4)


def escrever_folha(caminho: str | Path, img: Image.Image) -> None:
    """Grava uma imagem RGBA 384x384 como folha .bmp.lzma no formato da CIP."""
    if img.size != (LADO_FOLHA, LADO_FOLHA):
        raise ValueError(f"a folha precisa ser {LADO_FOLHA}x{LADO_FOLHA}")

    img = img.convert("RGBA").transpose(Image.FLIP_TOP_BOTTOM)
    r, g, b, a = img.split()
    pixels = Image.merge("RGBA", (b, g, r, a)).tobytes()   # RGBA -> BGRA
    bmp = _cabecalho_bmp() + pixels

    # LZMA1: o FORMAT_ALONE do Python já escreve props + dict + 8 bytes e
    # emite o marcador de fim, que é o que o decodificador cru do client
    # espera. Só trocamos o campo de 8 bytes pelo tamanho comprimido, como
    # a CipSoft faz.
    corpo = bytearray(lzma.compress(
        bmp, format=lzma.FORMAT_ALONE,
        filters=[{"id": lzma.FILTER_LZMA1, "preset": 6, "dict_size": 1 << 25}]))
    corpo[5:13] = struct.pack("<Q", len(corpo) - 13)

    tamanho = _varint(len(corpo))
    enchimento = TAM_CABECALHO_CIP - len(MARCA_CIP) - len(tamanho)
    if enchimento < 0:
        raise ValueError("cabeçalho CIP não cabe em 32 bytes")

    Path(caminho).write_bytes(bytes(enchimento) + MARCA_CIP + tamanho + bytes(corpo))


def nome_de_folha(caminho_temporario: str | Path) -> str:
    """Nome final da folha: ``sprites-<sha256 do conteúdo>.bmp.lzma``."""
    sha = hashlib.sha256(Path(caminho_temporario).read_bytes()).hexdigest()
    return f"sprites-{sha}.bmp.lzma"


# --------------------------------------------------------------- catálogo

class Catalogo:
    """O ``catalog-content.json`` da pasta de assets."""

    def __init__(self, pasta: str | Path):
        self.pasta = Path(pasta)
        self.caminho = self.pasta / "catalog-content.json"
        self.entradas = json.loads(self.caminho.read_text())

    @property
    def folhas(self) -> list[dict]:
        return [e for e in self.entradas if e.get("type") == "sprite"]

    def proximo_spriteid(self) -> int:
        return max(e["lastspriteid"] for e in self.folhas) + 1

    def folha_de(self, spriteid: int) -> dict | None:
        for e in self.folhas:
            if e["firstspriteid"] <= spriteid <= e["lastspriteid"]:
                return e
        return None

    def adicionar_folha(self, arquivo: str, spritetype: int,
                        primeiro: int, ultimo: int) -> None:
        self.entradas.append({
            "type": "sprite",
            "file": arquivo,
            "spritetype": spritetype,
            "firstspriteid": primeiro,
            "lastspriteid": ultimo,
            "area": 0,
        })

    def salvar(self) -> None:
        self.caminho.write_text(json.dumps(self.entradas, separators=(",", ":")))


# ----------------------------------------------------------- appearances

CATEGORIAS = {1: "object", 2: "outfit", 3: "effect", 4: "missile"}


def _campos(b: bytes, ini: int = 0, fim: int | None = None):
    i, fim = ini, len(b) if fim is None else fim
    while i < fim:
        chave = 0
        s = 0
        while True:
            x = b[i]
            i += 1
            chave |= (x & 0x7F) << s
            s += 7
            if not (x & 0x80):
                break
        n, t = chave >> 3, chave & 7
        if t == 0:
            v = 0
            s = 0
            while True:
                x = b[i]
                i += 1
                v |= (x & 0x7F) << s
                s += 7
                if not (x & 0x80):
                    break
            yield n, v
        elif t == 2:
            ln = 0
            s = 0
            while True:
                x = b[i]
                i += 1
                ln |= (x & 0x7F) << s
                s += 7
                if not (x & 0x80):
                    break
            yield n, (i, i + ln)
            i += ln
        elif t == 5:
            yield n, int.from_bytes(b[i:i + 4], "little")
            i += 4
        elif t == 1:
            yield n, int.from_bytes(b[i:i + 8], "little")
            i += 8
        else:
            raise ValueError(f"wire type {t} não suportado")


def _var(campo: int, valor: int) -> bytes:
    return _varint(campo << 3) + _varint(valor)


def _bloco(campo: int, dados: bytes) -> bytes:
    return _varint((campo << 3) | 2) + _varint(len(dados)) + dados


@dataclass
class Aparencia:
    categoria: str
    id: int


class Appearances:
    """O ``appearances.dat``.

    Só lê o índice (id + categoria de cada mensagem) e acrescenta mensagens
    novas no fim do arquivo. Como as categorias são campos *repeated* da
    mensagem raiz, acrescentar no fim é equivalente a inserir no meio para
    qualquer leitor de protobuf — inclusive o do próprio servidor.
    """

    def __init__(self, caminho: str | Path):
        self.caminho = Path(caminho)
        self.dados = bytearray(self.caminho.read_bytes())
        self.novas = bytearray()

    def listar(self) -> list[Aparencia]:
        saida = []
        for n, v in _campos(self.dados):
            if n in CATEGORIAS and isinstance(v, tuple):
                for n2, v2 in _campos(self.dados, *v):
                    if n2 == 1 and isinstance(v2, int):
                        saida.append(Aparencia(CATEGORIAS[n], v2))
                        break
        return saida

    def ids(self, categoria: str) -> list[int]:
        return sorted(a.id for a in self.listar() if a.categoria == categoria)

    def sprite_ids(self, categoria: str, ident: int) -> list[int]:
        campo = next(k for k, v in CATEGORIAS.items() if v == categoria)
        for n, v in _campos(self.dados):
            if n != campo or not isinstance(v, tuple):
                continue
            achou, ids = False, []
            for n2, v2 in _campos(self.dados, *v):
                if n2 == 1 and v2 == ident:
                    achou = True
                if n2 == 2 and isinstance(v2, tuple):          # frame_group
                    for n3, v3 in _campos(self.dados, *v2):
                        if n3 == 3 and isinstance(v3, tuple):  # sprite_info
                            for n4, v4 in _campos(self.dados, *v3):
                                if n4 == 5:
                                    ids.append(v4)
            if achou:
                return ids
        return []

    # ------------------------------------------------------------ escrita

    @staticmethod
    def _sprite_info(sprite_ids: list[int], largura: int, altura: int,
                     animacao: bytes | None, quadrado: int | None,
                     camadas: int = 1, profundidade: int = 1,
                     caixas: int | None = None) -> bytes:
        b = (_var(1, largura) + _var(2, altura) + _var(3, profundidade)
             + _var(4, camadas))
        for s in sprite_ids:
            b += _var(5, s)
        if animacao:
            b += _bloco(6, animacao)
        if quadrado is not None:
            b += _var(7, quadrado)
        b += _var(8, 0)                                     # is_opaque
        caixa = _var(1, 0) + _var(2, 0) + _var(3, 31) + _var(4, 31)
        # bounding_box_per_direction e' por DIRECAO: os outfits oficiais tem 4,
        # mesmo com pattern 4x3x2. O padrao aqui mantem o que efeito e missile
        # ja usavam; quem precisa de outra contagem passa `caixas`.
        if caixas is None:
            caixas = largura * altura if largura > 1 else 1
        for _ in range(caixas):
            b += _bloco(9, caixa)
        return b

    @staticmethod
    def _animacao(duracoes_ms: list[int]) -> bytes:
        b = _var(2, 0) + _var(4, 1) + _var(5, 1)            # sync, loop, count
        for ms in duracoes_ms:
            b += _bloco(6, _var(1, ms) + _var(2, ms))
        return b

    def adicionar_efeito(self, ident: int, sprite_ids: list[int],
                         duracao_ms: int = 100, sprite_64: bool = False) -> None:
        """Cria um magic effect novo: 1 tile, N quadros animados."""
        info = self._sprite_info(
            sprite_ids, 1, 1,
            self._animacao([duracao_ms] * len(sprite_ids)),
            32 if sprite_64 else None)
        grupo = _var(1, 2) + _var(2, 2) + _bloco(3, info)
        ap = _var(1, ident) + _bloco(2, grupo) + _bloco(3, b"")
        self.novas += _bloco(3, ap)

    def adicionar_outfit(self, ident: int, parado: list[int],
                         andando: list[int], fases: int,
                         quadrado: int = 46, camadas: int = 2) -> None:
        """Cria um outfit novo com os dois frame groups.

        Todo outfit do Tibia tem **duas camadas**: o desenho e a mascara que
        diz quais pixels recebem a cor escolhida pelo jogador. O client de
        fato conta com isso, entao um outfit de uma camada so nao desenha
        direito — se voce nao quer outfit colorizavel, mande uma mascara
        vazia, que as passadas de cor nao pintam nada.

        Os ids vem intercalados: para cada (fase, direcao), primeiro o
        desenho e depois a mascara.

            indice = (fase * 4 + direcao) * camadas + camada
        """
        if len(parado) != 4 * camadas:
            raise ValueError(f"o grupo parado precisa de {4 * camadas} sprites")
        if len(andando) != 4 * fases * camadas:
            raise ValueError(f"o grupo andando precisa de {4 * fases * camadas} sprites")

        # Os outfits oficiais declaram pattern 4x3x2: 4 direcoes, 3 posicoes de
        # ADDON e 2 de MONTARIA. Publicar 4x1x1 quebra a tela de Customize, que
        # desenha o personagem com addon e montado -- o client indexa um slot
        # que nao existe e le fora da faixa (ThingType::getSpriteIndex so tem
        # assert, que nao roda em release). Como este outfit nao tem arte de
        # addon nem de montaria, os mesmos sprites sao repetidos nesses slots:
        # ele fica igual em qualquer combinacao, mas o indice sempre existe.
        ADDONS, MONTARIAS = 3, 2

        def grupo(fixo: int, base: list[int], fases_grupo: int) -> bytes:
            # ordem do client: fase -> montaria(z) -> addon(y) -> direcao(x) -> camada
            ids: list[int] = []
            for a in range(fases_grupo):
                for _z in range(MONTARIAS):
                    for _y in range(ADDONS):
                        for x in range(4):
                            for l in range(camadas):
                                ids.append(base[(a * 4 + x) * camadas + l])
            info = self._sprite_info(ids, 4, ADDONS, None, quadrado, camadas,
                                     profundidade=MONTARIAS, caixas=4)
            return _var(1, fixo) + _var(2, fixo) + _bloco(3, info)

        ap = (_var(1, ident)
              + _bloco(2, grupo(0, parado, 1))
              + _bloco(2, grupo(1, andando, fases))
              + _bloco(3, b""))
        self.novas += _bloco(2, ap)

    def adicionar_missile(self, ident: int, sprite_ids: list[int]) -> None:
        """Cria um distance effect novo: 9 sprites, um por direção (3x3)."""
        if len(sprite_ids) != 9:
            raise ValueError("um missile precisa de exatamente 9 sprites "
                             "(NO, N, NE, O, centro, L, SO, S, SE)")
        info = self._sprite_info(sprite_ids, 3, 3, None, None)
        grupo = _var(1, 2) + _var(2, 2) + _bloco(3, info)
        ap = _var(1, ident) + _bloco(2, grupo) + _bloco(3, b"")
        self.novas += _bloco(4, ap)

    def salvar(self, destino: str | Path | None = None) -> Path:
        destino = Path(destino) if destino else self.caminho
        destino.write_bytes(bytes(self.dados) + bytes(self.novas))
        return destino
