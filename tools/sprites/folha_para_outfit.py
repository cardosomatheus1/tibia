#!/usr/bin/env python3
"""Converte uma folha de personagem (4 direcoes x N quadros) em sprites de
outfit do Tibia.

Espera uma imagem com os quadros em grade, nesta ordem de linhas:

    sul (de frente), leste, norte (de costas), oeste

Ele acha a grade sozinho pelas faixas de conteudo, tira o fundo por
preenchimento a partir das bordas, reduz para o tamanho do tile, reduz a
paleta (a mesma para todos os quadros, senao a animacao cintila) e encaixa
cada quadro num sprite de 64x64 com o pe no chao do tile.

    python3 tools/sprites/folha_para_outfit.py folha.png saida/ --altura 40

O alinhamento e feito pela **base comum** de todos os quadros: se cada um
fosse centralizado sozinho, o personagem pularia durante a caminhada.
"""
from __future__ import annotations

import argparse
from collections import Counter, deque
from pathlib import Path

from PIL import Image

LADO_SPRITE = 64
NOMES = ["sul", "leste", "norte", "oeste"]


# ------------------------------------------------------------------ grade

def faixas(valores, limite, minimo):
    saida, ini = [], None
    for i, v in enumerate(valores):
        if v > limite and ini is None:
            ini = i
        elif v <= limite and ini is not None:
            if i - ini >= minimo:
                saida.append((ini, i - 1))
            ini = None
    if ini is not None and len(valores) - ini >= minimo:
        saida.append((ini, len(valores) - 1))
    return saida


def achar_grade(im):
    """Descobre as linhas e colunas da grade pelo conteudo."""
    px = im.convert("RGB").load()
    L, A = im.size
    marca = [[False] * L for _ in range(A)]
    for y in range(A):
        for x in range(L):
            r, g, b = px[x, y]
            if max(r, g, b) - min(r, g, b) > 18 or r + g + b > 150:
                marca[y][x] = True
    por_linha = [sum(l) for l in marca]
    por_col = [sum(marca[y][x] for y in range(A)) for x in range(L)]
    return (faixas(por_linha, 3, A // 40), faixas(por_col, 3, L // 40))


# ------------------------------------------------------------------- fundo

def tirar_fundo(quadro, tolerancia=42):
    """Apaga o fundo alcancavel a partir das bordas.

    Preenchimento a partir da borda, e nao limiar de cor: assim o contorno
    preto do desenho e preservado, porque ele so e alcancado por dentro.
    """
    im = quadro.convert("RGBA")
    L, A = im.size
    px = im.load()
    fundo = Counter()
    for x in range(L):
        fundo[px[x, 0][:3]] += 1
        fundo[px[x, A - 1][:3]] += 1
    for y in range(A):
        fundo[px[0, y][:3]] += 1
        fundo[px[L - 1, y][:3]] += 1
    cf = fundo.most_common(1)[0][0]

    visto = [[False] * L for _ in range(A)]
    fila = deque()
    for x in range(L):
        fila.extend([(x, 0), (x, A - 1)])
    for y in range(A):
        fila.extend([(0, y), (L - 1, y)])
    while fila:
        x, y = fila.popleft()
        if not (0 <= x < L and 0 <= y < A) or visto[y][x]:
            continue
        r, g, b, _ = px[x, y]
        if abs(r - cf[0]) + abs(g - cf[1]) + abs(b - cf[2]) > tolerancia:
            continue
        visto[y][x] = True
        px[x, y] = (0, 0, 0, 0)
        fila.extend([(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)])
    return im


# ---------------------------------------------------------------- paleta

def paleta_comum(quadros, cores=24):
    """Uma paleta so para a folha inteira — senao a animacao cintila."""
    largura = sum(q.width for q in quadros)
    junto = Image.new("RGBA", (largura, max(q.height for q in quadros)), (0, 0, 0, 0))
    x = 0
    for q in quadros:
        junto.paste(q, (x, 0))
        x += q.width
    opaco = Image.new("RGB", junto.size, (0, 0, 0))
    opaco.paste(junto.convert("RGB"), mask=junto.split()[3])
    reduzida = opaco.quantize(colors=cores, method=Image.MEDIANCUT)
    mapa = reduzida.getpalette()[: cores * 3]
    return [tuple(mapa[i * 3:i * 3 + 3]) for i in range(cores)]


def reduzir_com_alfa(img, tamanho):
    """Reduz sem borrar a cor contra o transparente.

    Reduzir RGBA direto mistura os pixels de fora (pretos e transparentes)
    na cor da borda, o que escurece o contorno e derruba o alfa de detalhe
    fino. Multiplicar pelo alfa antes e dividir depois resolve.
    """
    o = img.load()
    pre = Image.new("RGBA", img.size)
    pp = pre.load()
    for y in range(img.height):
        for x in range(img.width):
            r, g, b, a = o[x, y]
            k = a / 255
            pp[x, y] = (int(r * k), int(g * k), int(b * k), a)

    pre = pre.resize(tamanho, Image.LANCZOS)
    saida = Image.new("RGBA", tamanho)
    sp, rp = saida.load(), pre.load()
    for y in range(tamanho[1]):
        for x in range(tamanho[0]):
            r, g, b, a = rp[x, y]
            if a == 0:
                sp[x, y] = (0, 0, 0, 0)
                continue
            k = 255 / a
            sp[x, y] = (min(255, int(r * k)), min(255, int(g * k)),
                        min(255, int(b * k)), a)
    return saida


def fechar_falhas(img, corte):
    """Reacende pixel que caiu logo abaixo do corte e tem vizinho dos dois lados.

    E o que salva o cabo do cajado: com 1px de largura depois da reducao ele
    vira tracejado, porque um pixel sim outro nao fica meio transparente.
    """
    px = img.load()
    L, A = img.size
    alvo = []
    for y in range(A):
        for x in range(L):
            if px[x, y][3] >= corte or px[x, y][3] < corte * 0.35:
                continue
            viz_v = (y > 0 and px[x, y - 1][3] >= corte) and \
                    (y < A - 1 and px[x, y + 1][3] >= corte)
            viz_h = (x > 0 and px[x - 1, y][3] >= corte) and \
                    (x < L - 1 and px[x + 1, y][3] >= corte)
            if viz_v or viz_h:
                alvo.append((x, y))
    for x, y in alvo:
        r, g, b, _ = px[x, y]
        px[x, y] = (r, g, b, 255)
    return img


def encaixar(img, paleta, corte_alfa=78):
    img = fechar_falhas(img.copy(), corte_alfa)
    saida = Image.new("RGBA", img.size, (0, 0, 0, 0))
    o, s = img.load(), saida.load()
    for y in range(img.height):
        for x in range(img.width):
            r, g, b, a = o[x, y]
            if a < corte_alfa:
                continue
            melhor, dist = paleta[0], 1e9
            for c in paleta:
                d = ((c[0] - r) ** 2 * 0.30 + (c[1] - g) ** 2 * 0.59
                     + (c[2] - b) ** 2 * 0.11)
                if d < dist:
                    melhor, dist = c, d
            s[x, y] = melhor + (255,)
    return saida


# ------------------------------------------------------------------ main

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("folha")
    p.add_argument("saida")
    p.add_argument("--altura", type=int, default=40,
                   help="altura do personagem em pixels no sprite final")
    p.add_argument("--cores", type=int, default=24)
    p.add_argument("--base-y", type=int, default=62,
                   help="linha do sprite 64x64 onde ficam os pes")
    args = p.parse_args()

    im = Image.open(args.folha)
    linhas, colunas = achar_grade(im)
    print(f"grade encontrada: {len(linhas)} direcoes x {len(colunas)} quadros")
    if len(linhas) != 4:
        raise SystemExit("esperava 4 linhas (sul, leste, norte, oeste)")

    # 1. recorta e limpa o fundo de cada celula
    limpos = []
    for (y1, y2) in linhas:
        for (x1, x2) in colunas:
            m = 6
            cel = im.crop((max(0, x1 - m), max(0, y1 - m),
                           min(im.width, x2 + m), min(im.height, y2 + m)))
            limpos.append(tirar_fundo(cel))

    # 2. escala unica para todos, tirada do quadro mais alto
    alto = max(q.getbbox()[3] - q.getbbox()[1] for q in limpos)
    escala = args.altura / alto
    reduzidos = [reduzir_com_alfa(q, (max(1, round(q.width * escala)),
                                      max(1, round(q.height * escala))))
                 for q in limpos]

    # 3. paleta compartilhada
    paleta = paleta_comum(reduzidos, args.cores)
    reduzidos = [encaixar(q, paleta) for q in reduzidos]

    # 4. ancora comum: um so deslocamento para a folha inteira
    #    (se cada quadro fosse centralizado pela propria caixa, o personagem
    #     pularia de um quadro para o outro durante a caminhada)
    caixas = [q.getbbox() for q in reduzidos]
    chao = max(c[3] for c in caixas)
    centro = sum((c[0] + c[2]) / 2 for c in caixas) / len(caixas)
    dx = round(48 - centro)                    # o tile e o quadrante inferior direito
    dy = args.base_y - chao

    destino = Path(args.saida)
    destino.mkdir(parents=True, exist_ok=True)
    n_quadros = len(colunas)
    arquivos = []
    for i, q in enumerate(reduzidos):
        sprite = Image.new("RGBA", (LADO_SPRITE, LADO_SPRITE), (0, 0, 0, 0))
        sprite.paste(q, (dx, dy), q)
        direcao = NOMES[i // n_quadros]
        arq = destino / f"{direcao}_{i % n_quadros + 1}.png"
        sprite.save(arq)
        arquivos.append(arq)

    print(f"{len(arquivos)} sprites de {LADO_SPRITE}x{LADO_SPRITE} em {destino}")
    print(f"  personagem com {args.altura}px de altura, pe em y={args.base_y}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
