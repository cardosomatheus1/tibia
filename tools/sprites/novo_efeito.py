#!/usr/bin/env python3
"""Injeta sprites próprios nos assets do client 15.x como efeito ou missile.

Uso — magic effect (animação de N quadros num tile):

    python3 tools/sprites/novo_efeito.py efeito \\
        --assets /caminho/do/client/assets \\
        --dat-servidor data/items/appearances.dat \\
        --id 350 --duracao 100 \\
        tools/sprites/arte/fogo/efeito_01.png ...

Uso — distance effect (o projétil que voa de A até B):

    python3 tools/sprites/novo_efeito.py missile \\
        --assets /caminho/do/client/assets \\
        --dat-servidor data/items/appearances.dat \\
        --id 70 \\
        tools/sprites/arte/fogo/missile_base.png

No missile basta **um** sprite apontando para a direita: as outras sete
direções saem de rotação. Se você preferir desenhar as oito à mão, passe os
nove arquivos na ordem NO, N, NE, O, centro, L, SO, S, SE.

Depois de rodar, o efeito já existe dos dois lados: o client desenha e o
servidor aceita, porque o Canary registra os efeitos lendo o próprio
appearances.dat (`Game::loadAppearanceProtobuf`). Nada de recompilar.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
import tibia_assets as ta   # noqa: E402

# ordem das direções de um missile (matriz 3x3 do pattern)
GIROS = [45, 90, 135, 0, 0, 180, -45, -90, -135]


def carregar_quadros(caminhos: list[str], lado: int) -> list[Image.Image]:
    quadros = []
    for c in caminhos:
        img = Image.open(c).convert("RGBA")
        if img.size != (lado, lado):
            print(f"  aviso: {Path(c).name} é {img.width}x{img.height}, "
                  f"redimensionando para {lado}x{lado}")
            img = img.resize((lado, lado), Image.NEAREST)
        quadros.append(img)
    return quadros


def espalhar_direcoes(base: Image.Image) -> list[Image.Image]:
    """Gera os 9 sprites de um missile a partir de um que aponta pra direita."""
    return [base.rotate(g, resample=Image.NEAREST, expand=False) for g in GIROS]


def montar_folha(quadros: list[Image.Image], lado: int) -> Image.Image:
    por_linha = ta.LADO_FOLHA // lado
    folha = Image.new("RGBA", (ta.LADO_FOLHA, ta.LADO_FOLHA), (0, 0, 0, 0))
    for i, q in enumerate(quadros):
        folha.paste(q, ((i % por_linha) * lado, (i // por_linha) * lado))
    return folha


def gravar_assets(pasta: Path, quadros: list[Image.Image], lado: int) -> list[int]:
    """Grava uma folha nova e devolve os spriteids alocados."""
    spritetype = {32: 0, 64: 3}[lado]
    if len(quadros) > ta.sprites_por_folha(spritetype):
        raise SystemExit(f"cabem no máximo {ta.sprites_por_folha(spritetype)} "
                         f"sprites de {lado}x{lado} por folha")

    catalogo = ta.Catalogo(pasta)
    primeiro = catalogo.proximo_spriteid()
    ultimo = primeiro + len(quadros) - 1

    temporario = pasta / ".folha-nova.tmp"
    ta.escrever_folha(temporario, montar_folha(quadros, lado))
    nome = ta.nome_de_folha(temporario)
    shutil.move(temporario, pasta / nome)

    catalogo.adicionar_folha(nome, spritetype, primeiro, ultimo)
    catalogo.salvar()
    print(f"  folha {nome[:24]}… : spriteids {primeiro}..{ultimo}")
    return list(range(primeiro, ultimo + 1))


def atualizar_dat(pasta: Path, aplicar) -> None:
    """Aplica uma mudança no appearances.dat do client e renomeia pelo hash."""
    catalogo = ta.Catalogo(pasta)
    entrada = next(e for e in catalogo.entradas if e.get("type") == "appearances")
    antigo = pasta / entrada["file"]

    ap = ta.Appearances(antigo)
    aplicar(ap)
    temporario = pasta / ".appearances.tmp"
    ap.salvar(temporario)

    import hashlib
    sha = hashlib.sha256(temporario.read_bytes()).hexdigest()
    novo = f"appearances-{sha}.dat"
    shutil.move(temporario, pasta / novo)
    if antigo.name != novo:
        antigo.unlink(missing_ok=True)
        Path(str(antigo) + ".lzma").unlink(missing_ok=True)

    entrada["file"] = novo
    catalogo.salvar()
    print(f"  appearances do client -> {novo[:24]}…")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("tipo", choices=["efeito", "missile"])
    p.add_argument("pngs", nargs="+")
    p.add_argument("--assets", required=True,
                   help="pasta de assets do client (a que tem catalog-content.json)")
    p.add_argument("--dat-servidor",
                   help="data/items/appearances.dat do servidor (opcional, "
                        "mas sem ele o Canary não registra o efeito novo)")
    p.add_argument("--id", type=int, required=True, help="id do efeito/missile")
    p.add_argument("--duracao", type=int, default=100,
                   help="duração de cada quadro em ms (só para efeito)")
    p.add_argument("--tamanho", type=int, default=32, choices=[32, 64],
                   help="lado do sprite em pixels")
    args = p.parse_args()

    pasta = Path(args.assets)
    if not (pasta / "catalog-content.json").is_file():
        raise SystemExit(f"{pasta} não parece uma pasta de assets")

    quadros = carregar_quadros(args.pngs, args.tamanho)
    if args.tipo == "missile":
        if len(quadros) == 1:
            quadros = espalhar_direcoes(quadros[0])
            print("  1 sprite recebido: gerando as 8 direções por rotação")
        elif len(quadros) != 9:
            raise SystemExit("missile aceita 1 sprite (rotacionado) ou os 9")

    # confere se o id já existe antes de mexer em qualquer arquivo
    catalogo = ta.Catalogo(pasta)
    entrada = next(e for e in catalogo.entradas if e.get("type") == "appearances")
    existentes = ta.Appearances(pasta / entrada["file"]).ids(
        "effect" if args.tipo == "efeito" else "missile")
    if args.id in existentes:
        raise SystemExit(f"o id {args.id} já existe — livres a partir de "
                         f"{max(existentes) + 1}")

    print(f"{args.tipo} {args.id}: {len(quadros)} sprite(s) de "
          f"{args.tamanho}x{args.tamanho}")
    ids = gravar_assets(pasta, quadros, args.tamanho)

    def aplicar(ap: ta.Appearances):
        if args.tipo == "efeito":
            ap.adicionar_efeito(args.id, ids, args.duracao, args.tamanho == 64)
        else:
            ap.adicionar_missile(args.id, ids)

    atualizar_dat(pasta, aplicar)

    if args.dat_servidor:
        ap = ta.Appearances(args.dat_servidor)
        aplicar(ap)
        ap.salvar()
        print(f"  appearances do servidor -> {args.dat_servidor}")

    tipo_lua = "sendMagicEffect" if args.tipo == "efeito" else "sendDistanceEffect"
    print(f"\npronto. no Lua do servidor: posicao:{tipo_lua}({args.id})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
