#!/usr/bin/env python3
"""Sprite de cada monstro, pelo nome que aparece no arquivo de spawn.

O `otservbr-monster.xml` so diz o nome ("Cyclops"). O desenho mora em dois
lugares diferentes: o `.lua` do monstro tem o `lookType`, e o `appearances.dat`
tem os sprites daquele outfit. Este modulo faz a ponte.

Duas formas de aparencia, e as duas aparecem no datapack:

    lookType    = 22     outfit de verdade, com direcoes e camadas
    lookTypeEx  = 3031   o monstro E' um item (bau, estatua, pilha de ouro)

Escolher o sprite certo dentro de um outfit nao e' pegar o primeiro id. Eles
vem numa grade, na ordem que o client indexa:

    indice = ((((fase * profundidade + z) * altura + y) * largura + x)
              * camadas) + camada

Para o mapa interessa a direcao SUL (x=2), parado (fase 0), sem addon nem
montaria (y=z=0), e so a camada 0 -- a camada 1 e' a mascara de cor, que
sozinha vira uma silhueta chapada.
"""
from __future__ import annotations

import re
from pathlib import Path

from PIL import Image

SUL = 2                      # ordem do client: 0 norte, 1 leste, 2 sul, 3 oeste

# O nome que vale e' o de Game.createMonsterType: e' por ele que o servidor
# registra o monstro, e e' ele que aparece no arquivo de spawn. So 55 dos 1656
# arquivos definem monster.name, entao usar so esse campo perde quase tudo.
RE_TIPO = re.compile(r'createMonsterType\(\s*"([^"]+)"')
RE_NOME = re.compile(r'monster\.name\s*=\s*"([^"]+)"')
RE_LOOKTYPE = re.compile(r'lookType\s*=\s*(\d+)')
RE_LOOKTYPE_EX = re.compile(r'lookTypeEx\s*=\s*(\d+)')


def ler_looktypes(pasta: Path) -> dict[str, tuple[str, int]]:
    """nome minusculo -> ("outfit"|"item", id). Le os .lua do datapack."""
    saida: dict[str, tuple[str, int]] = {}
    for arq in pasta.rglob("*.lua"):
        try:
            texto = arq.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        nomes = {m.group(1).strip().lower()
                 for m in (RE_TIPO.search(texto), RE_NOME.search(texto)) if m}
        if not nomes:
            continue                      # arquivo auxiliar, sem monstro
        lt = RE_LOOKTYPE.search(texto)
        ltx = RE_LOOKTYPE_EX.search(texto)
        if lt and int(lt.group(1)) > 0:
            valor = ("outfit", int(lt.group(1)))
        elif ltx and int(ltx.group(1)) > 0:
            valor = ("item", int(ltx.group(1)))
        else:
            continue
        for nome in nomes:
            saida.setdefault(nome, valor)
    return saida


def _sprite_do_outfit(assets, looktype: int) -> Image.Image | None:
    grupo = assets.aparencias.indexar_grupos("outfit").get(looktype)
    if not grupo:
        return None
    largura, altura, profundidade, camadas, ids = grupo
    if not ids:
        return None
    x = SUL if largura > SUL else 0
    i = (((0 * profundidade + 0) * altura + 0) * largura + x) * camadas
    if i >= len(ids):
        i = 0
    s = assets.sprite(ids[i])
    return s.copy() if s is not None else None


class Sprites:
    """Cache de nome -> imagem RGBA. Uma leitura por nome, e so sob demanda."""

    def __init__(self, assets, pasta_monstros: Path):
        self.assets = assets
        self.looktypes = ler_looktypes(pasta_monstros)
        self._cache: dict[str, Image.Image | None] = {}

    def de(self, nome: str) -> Image.Image | None:
        chave = nome.strip().lower()
        if chave in self._cache:
            return self._cache[chave]
        info = self.looktypes.get(chave)
        img = None
        if info:
            tipo, ident = info
            img = (_sprite_do_outfit(self.assets, ident) if tipo == "outfit"
                   else self.assets.item(ident))
        self._cache[chave] = img
        return img

    def png(self, nome: str) -> bytes | None:
        """PNG no tamanho original -- 32x32 ou 64x64.

        Nao encolhe de proposito: o tamanho E' a informacao. Um sprite de
        64x64 ocupa 2x2 tiles no jogo, e o mapeador precisa disso para
        desenhar o monstro cobrindo a area certa. Quem recebe divide por 32
        e sabe quantos tiles o bicho ocupa.
        """
        import io
        img = self.de(nome)
        if img is None:
            return None
        buf = io.BytesIO()
        img.save(buf, "PNG", optimize=False, compress_level=6)
        return buf.getvalue()
