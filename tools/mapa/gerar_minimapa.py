#!/usr/bin/env python3
"""Gera o minimapa completo (.otmm) a partir do OTBM do servidor.

No Tibia o minimapa e' revelado andando. Servidores como o RubinOT entregam um
arquivo pronto para o jogador comecar com o mapa todo aberto. Este script produz
esse arquivo direto do `otservbr.otbm`, sem precisar percorrer o mapa em jogo.

De onde sai cada coisa:

    posicao e chao de cada tile -> data-otservbr-global/world/otservbr.otbm
    cor, bloqueio e velocidade  -> data/items/appearances.dat (protobuf)

O formato .otmm esta em src/client/minimap.h do otclient:

    u32  assinatura 0x4D4D544F ("OTMM")
    u16  offset onde comecam os blocos
    u16  versao = 1
    u32  flags = 0
    str  descricao (u16 de tamanho + bytes)

    por andar, por bloco de 64x64:
      u16 x, u16 y, u8 z     (canto do bloco)
      u16 tamanho comprimido
      zlib(64*64 tiles de 3 bytes: flags, color, speed)

    u16 0, u16 0, u8 0       (fim)

Uso (a partir da raiz do repositorio):

    python3 tools/mapa/gerar_minimapa.py

O arquivo sai em tools/mapa/minimap.otmm. O preparar_mehah.ps1 copia ele para
dentro do client montado, e o modulo game_minimap do otclient o carrega sozinho
no login (ele procura /minimap.otmm na raiz dos recursos).
"""
import argparse
import struct
import sys
import zlib
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))

from otbm import Mapa                      # noqa: E402


def _campos(b: bytes, ini: int = 0, fim: int | None = None):
    """Percorre campos de protobuf: devolve (numero, valor).

    Valor e' um inteiro para varint/fixed, ou o par (inicio, fim) para blocos.

    O tools/sprites/tibia_assets.py tem um leitor equivalente, mas ele importa
    Pillow no topo do modulo -- e este script precisa rodar tambem no servidor,
    onde o mapa de 176 MB fica e onde nao ha motivo para instalar Pillow.
    """
    i, fim = ini, len(b) if fim is None else fim
    while i < fim:
        chave, s = 0, 0
        while True:
            x = b[i]
            i += 1
            chave |= (x & 0x7F) << s
            s += 7
            if not (x & 0x80):
                break
        numero, tipo = chave >> 3, chave & 7

        if tipo == 0:                       # varint
            v, s = 0, 0
            while True:
                x = b[i]
                i += 1
                v |= (x & 0x7F) << s
                s += 7
                if not (x & 0x80):
                    break
            yield numero, v
        elif tipo == 2:                     # bloco
            ln, s = 0, 0
            while True:
                x = b[i]
                i += 1
                ln |= (x & 0x7F) << s
                s += 7
                if not (x & 0x80):
                    break
            yield numero, (i, i + ln)
            i += ln
        elif tipo == 5:
            yield numero, int.from_bytes(b[i:i + 4], "little")
            i += 4
        elif tipo == 1:
            yield numero, int.from_bytes(b[i:i + 8], "little")
            i += 8
        else:
            raise ValueError(f"wire type {tipo} nao suportado")

# --- formato .otmm (src/client/minimap.h) -----------------------------------
OTMM_SIGNATURE = 0x4D4D544F
OTMM_VERSION = 1
MMBLOCK_SIZE = 64
TILES_POR_BLOCO = MMBLOCK_SIZE * MMBLOCK_SIZE
BYTES_POR_TILE = 3            # struct MinimapTile: flags, color, speed (packed)
BLOCO_BYTES = TILES_POR_BLOCO * BYTES_POR_TILE
NIVEL_ZLIB = 3                # COMPRESS_LEVEL do saveOtmm

# enum MinimapTileFlags
FLAG_VISTO = 1
FLAG_SEM_ROTA = 2
FLAG_SEM_PASSAGEM = 4

# valores do MinimapTile "vazio", que e' o padrao do struct
COR_VAZIA = 255
VEL_PADRAO = 10

# --- campos do appearances.proto --------------------------------------------
CAMPO_OBJETO = 1              # Appearances.object
CAMPO_ID = 1                  # Appearance.id
CAMPO_FLAGS = 3               # Appearance.flags
FLAG_BANK = 1                 # AppearanceFlags.bank      -> waypoints = velocidade
FLAG_CLIP = 2                 # AppearanceFlags.clip      -> borda de chao
FLAG_BOTTOM = 3               # AppearanceFlags.bottom    -> parede, muro
FLAG_TOP = 4                  # AppearanceFlags.top       -> fica por cima
FLAG_UNPASS = 13              # AppearanceFlags.unpass    -> bloqueia passagem
FLAG_AUTOMAP = 30             # AppearanceFlags.automap   -> color
CAMPO_COR = 1                 # AppearanceFlagAutomap.color
CAMPO_WAYPOINTS = 1           # AppearanceFlagBank.waypoints


class Item:
    """O que o minimapa precisa saber de um item."""
    __slots__ = ("cor", "bloqueia", "velocidade", "estrutura")

    def __init__(self, cor, bloqueia, velocidade, estrutura):
        self.cor = cor                  # cor do automapa, ou None
        self.bloqueia = bloqueia        # unpass: impede andar
        self.velocidade = velocidade    # waypoints do bank (so chao tem)
        self.estrutura = estrutura      # conta para a cor do tile?


ITEM_VAZIO = Item(None, False, 0, False)


def ler_atributos(caminho_dat: Path) -> dict[int, Item]:
    """id do item -> Item.

    `estrutura` reproduz o filtro do Tile::getMinimapColorByte, que percorre os
    things de cima para baixo e ignora os `isCommon()` -- isto e', os itens
    soltos que a pessoa larga no chao. Sobram chao, borda de chao, parede
    (bottom) e coisas on-top, que sao o que de fato pinta o minimapa.
    """
    b = caminho_dat.read_bytes()
    attrs: dict[int, Item] = {}

    for campo, valor in _campos(b):
        if campo != CAMPO_OBJETO or not isinstance(valor, tuple):
            continue
        ini, fim = valor

        ident, cor, bloqueia, velocidade = None, None, False, 0
        estrutura = False
        for c2, v2 in _campos(b, ini, fim):
            if c2 == CAMPO_ID and not isinstance(v2, tuple):
                ident = v2
            elif c2 == CAMPO_FLAGS and isinstance(v2, tuple):
                fi, ff = v2
                for c3, v3 in _campos(b, fi, ff):
                    if c3 == FLAG_AUTOMAP and isinstance(v3, tuple):
                        ai, af = v3
                        for c4, v4 in _campos(b, ai, af):
                            if c4 == CAMPO_COR and not isinstance(v4, tuple):
                                cor = v4
                    elif c3 == FLAG_UNPASS and not isinstance(v3, tuple):
                        bloqueia = bool(v3)
                    elif c3 == FLAG_BANK and isinstance(v3, tuple):
                        estrutura = True
                        bi, bf = v3
                        for c4, v4 in _campos(b, bi, bf):
                            if c4 == CAMPO_WAYPOINTS and not isinstance(v4, tuple):
                                velocidade = v4
                    elif c3 in (FLAG_CLIP, FLAG_BOTTOM, FLAG_TOP) and v3:
                        estrutura = True

        if ident is not None:
            attrs[ident] = Item(cor, bloqueia, velocidade, estrutura)

    return attrs


def _escrever_string(saida: bytearray, texto: str) -> None:
    """String do otclient: u16 de tamanho seguido dos bytes."""
    dados = texto.encode("latin-1")
    saida += struct.pack("<H", len(dados))
    saida += dados


def gerar(mapa: Mapa, attrs: dict, andares: range, verboso: bool):
    """Monta os blocos do minimapa. Devolve (blocos, contagem de tiles)."""
    # (z, bx, by) -> bytearray com 64*64 tiles
    blocos: dict[tuple[int, int, int], bytearray] = {}
    vazio = bytes([0, COR_VAZIA, VEL_PADRAO]) * TILES_POR_BLOCO

    contados, sem_cor = 0, 0
    areas = [a for a in mapa.areas() if a[2] in andares]
    if verboso:
        print(f"  {len(areas)} areas de 256x256 nos andares {andares.start}-{andares.stop - 1}")

    for i, base in enumerate(areas, 1):
        for t in mapa.tiles_da_area(base):
            # Nao exige chao: parede de predio costuma ocupar um tile em que a
            # parede E' o tile, sem piso embaixo. Pulando esses, o contorno dos
            # predios ficava preto -- o getMinimapColorByte tambem nao exige
            # chao, ele so procura o primeiro thing com cor.
            chao = attrs.get(t.chao, ITEM_VAZIO) if t.chao is not None else ITEM_VAZIO

            # Cor: mesma regra do Tile::getMinimapColorByte -- de cima para
            # baixo, o primeiro item de estrutura que tenha cor. So se nenhum
            # tiver e' que vale a cor do chao. Usar so o chao (como eu fiz na
            # primeira versao) apaga predios e paredes: fica so verde e cinza.
            cor = None
            for iid, _, _ in reversed(t.itens):
                it = attrs.get(iid, ITEM_VAZIO)
                if it.estrutura and it.cor:
                    cor = it.cor
                    break
            if cor is None:
                cor = chao.cor
            if cor is None:
                sem_cor += 1
                continue

            # Mesma regra do Minimap::updateTile: qualquer item que bloqueie
            # passagem marca o tile como intransponivel, para o calculo de rota
            # do client nao tentar atravessar parede.
            flags = FLAG_VISTO
            if chao.bloqueia or any(attrs.get(i, ITEM_VAZIO).bloqueia
                                    for i, _, _ in t.itens):
                flags |= FLAG_SEM_PASSAGEM | FLAG_SEM_ROTA

            # speed = ceil(velocidade / 10), limitado a um byte
            vel = (min(255, max(1, -(-chao.velocidade // 10)))
                   if chao.velocidade else VEL_PADRAO)

            chave = (t.z, t.x // MMBLOCK_SIZE, t.y // MMBLOCK_SIZE)
            bloco = blocos.get(chave)
            if bloco is None:
                bloco = bytearray(vazio)
                blocos[chave] = bloco

            idx = ((t.y % MMBLOCK_SIZE) * MMBLOCK_SIZE + (t.x % MMBLOCK_SIZE)) * BYTES_POR_TILE
            bloco[idx] = flags & 0xFF
            bloco[idx + 1] = cor & 0xFF
            bloco[idx + 2] = vel
            contados += 1

        # Sem isto o Mapa acumula os tiles de todas as areas ja lidas e o
        # processo passa de 6 GB no mapa global -- foi OOM na primeira tentativa.
        mapa.esquecer_area(base)

        if verboso and i % 50 == 0:
            print(f"    area {i}/{len(areas)}  {contados} tiles  {len(blocos)} blocos",
                  flush=True)

    return blocos, contados, sem_cor


def escrever_otmm(blocos: dict, destino: Path) -> None:
    saida = bytearray()
    saida += struct.pack("<I", OTMM_SIGNATURE)
    saida += struct.pack("<H", 0)              # offset dos blocos, reescrito abaixo
    saida += struct.pack("<H", OTMM_VERSION)
    saida += struct.pack("<I", 0)              # flags
    _escrever_string(saida, "OTMM 1.0")

    inicio = len(saida)
    struct.pack_into("<H", saida, 4, inicio)

    # ordenado por andar e depois por bloco, so para o arquivo sair estavel
    for (z, bx, by) in sorted(blocos.keys()):
        comprimido = zlib.compress(bytes(blocos[(z, bx, by)]), NIVEL_ZLIB)
        if len(comprimido) > 0xFFFF:
            raise ValueError(f"bloco {(z, bx, by)} comprimido nao cabe em u16")
        saida += struct.pack("<HHB", bx * MMBLOCK_SIZE, by * MMBLOCK_SIZE, z)
        saida += struct.pack("<H", len(comprimido))
        saida += comprimido

    # Fim do arquivo: a Position invalida do otclient e' {UINT16_MAX,
    # UINT16_MAX, UINT8_MAX} (position.h:254). Gravar (0,0,0) nao encerra o
    # laco de leitura -- isValid() aceita (0,0,0) e o client tenta ler um bloco
    # que nao existe, o que da "read failed".
    saida += struct.pack("<HHB", 0xFFFF, 0xFFFF, 0xFF)
    destino.write_bytes(bytes(saida))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--mapa", default=str(RAIZ / "data-otservbr-global/world/otservbr.otbm"))
    p.add_argument("--appearances", default=str(RAIZ / "data/items/appearances.dat"))
    p.add_argument("--saida", default=str(Path(__file__).parent / "minimap.otmm"))
    p.add_argument("--andar-min", type=int, default=0)
    p.add_argument("--andar-max", type=int, default=15)
    p.add_argument("--silencioso", action="store_true")
    args = p.parse_args()

    for caminho in (args.mapa, args.appearances):
        if not Path(caminho).is_file():
            print(f"nao encontrei {caminho}", file=sys.stderr)
            return 1

    verboso = not args.silencioso

    if verboso:
        print("lendo cores e flags do appearances.dat...")
    attrs = ler_atributos(Path(args.appearances))
    com_cor = sum(1 for v in attrs.values() if v.cor is not None)
    if verboso:
        print(f"  {len(attrs)} itens, {com_cor} com cor de automapa")
    if com_cor == 0:
        print("nenhuma cor de automapa encontrada — o appearances.dat esta correto?",
              file=sys.stderr)
        return 1

    if verboso:
        print("varrendo o OTBM...")
    mapa = Mapa(args.mapa)
    largura, altura = mapa.cabecalho[1], mapa.cabecalho[2]
    if verboso:
        print(f"  mapa {largura}x{altura}")

    andares = range(args.andar_min, args.andar_max + 1)
    blocos, tiles, sem_cor = gerar(mapa, attrs, andares, verboso)

    if not blocos:
        print("nenhum tile gerado — confira os andares pedidos", file=sys.stderr)
        return 1

    destino = Path(args.saida)
    escrever_otmm(blocos, destino)

    tam = destino.stat().st_size
    print(f"{tiles} tiles em {len(blocos)} blocos -> {destino.name} "
          f"({tam / 1024 / 1024:.1f} MB)")
    if sem_cor:
        print(f"  {sem_cor} tiles com chao sem cor de automapa (ficam vazios, "
              f"como no client)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
