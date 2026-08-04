#!/usr/bin/env python3
"""Gera os ícones da loja a partir dos assets do próprio client.

O catálogo da Store (data/modules/scripts/gamestore/catalog/*.lua) referencia
~840 imagens que o otclient do mehah não distribui — é arte da CipSoft, servida
pela CDN deles e protegida por Cloudflare. Sem elas o client cai no
`dynamic-image-error` e a loja fica cheia de quadrados vazios.

Este script desenha o que dá a partir do que você já possui legitimamente
(o appearances.dat do client 15.25):

    item      -> sprite do objeto             (offer.itemtype)
    montaria  -> sprite da criatura           (offer.id -> mounts.xml -> clientid)
    outfit    -> sprite da criatura           (offer.sexId.male/female = looktype)

Cobre ~90%. Os ~80 restantes são ícones de categoria e ofertas de sistema
(Prey Slot, Blessings, Premium Time): não existe sprite deles no jogo porque
não são objeto nem criatura. Para esses, --neutro grava um ícone liso, que
fica melhor que o quadrado de erro.

Uso (a partir da raiz do repositório):

    python3 tools/loja/gerar_icones.py --assets C:/otclient-mehah/data/things/1525 \\
        --saida tools/loja/saida
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "tools" / "sprites"))

from PIL import Image                     # noqa: E402
import tibia_assets as ta                 # noqa: E402

CATALOGO = RAIZ / "data" / "modules" / "scripts" / "gamestore" / "catalog"
MOUNTS_XML = RAIZ / "data" / "XML" / "mounts.xml"
HIRELING_LUA = RAIZ / "data" / "libs" / "systems" / "hireling.lua"
LADO = 64                                 # a loja usa ícones 64x64


# ------------------------------------------------------------------ leitura

def ler_mounts() -> dict[int, int]:
    """id da montaria -> clientid (o looktype que existe no appearances)."""
    if not MOUNTS_XML.is_file():
        return {}
    texto = MOUNTS_XML.read_text(encoding="utf-8", errors="replace")
    return {
        int(m.group(1)): int(m.group(2))
        for m in re.finditer(r'<mount id="(\d+)"\s+clientid="(\d+)"', texto)
    }


def ler_hirelings() -> dict[str, int]:
    """Chave do HIRELING_OUTFITS_TABLE -> looktype masculino.

    As ofertas de roupa de hireling referenciam uma constante
    (HIRELING_OUTFITS.COOKING[1]), nao um numero, entao o looktype tem de vir
    da tabela do datapack.
    """
    if not HIRELING_LUA.is_file():
        return {}
    texto = HIRELING_LUA.read_text(encoding="utf-8", errors="replace")
    bloco = re.search(r"HIRELING_OUTFITS_TABLE\s*=\s*\{(.*?)\n\}", texto, re.S)
    if not bloco:
        return {}
    return {
        m.group(1): int(m.group(2))
        for m in re.finditer(r"(\w+)\s*=\s*\{[^}]*male\s*=\s*(\d+)", bloco.group(1))
    }


def ler_ofertas() -> list[dict]:
    """Extrai (icone, tipo, identificador) de cada oferta do catálogo."""
    ofertas = []
    for arquivo in sorted(CATALOGO.glob("*.lua")):
        texto = arquivo.read_text(encoding="utf-8", errors="replace")
        for bloco in re.split(r"\n\t\t\{", texto):
            icones = re.findall(r'"([A-Za-z0-9_. -]+\.png)"', bloco)
            if not icones:
                continue

            # itemtype pode ser numero ou TABELA: as camas vem em duas partes
            # (itemtype = { 39788, 39789 }); a primeira ja desenha a cama.
            item = re.search(r"itemtype\s*=\s*(\d+)", bloco)
            item_tab = re.search(r"itemtype\s*=\s*\{\s*(\d+)", bloco)
            sexo = re.search(r"sexId\s*=\s*\{([^}]*)\}", bloco)
            montaria = "OFFER_TYPE_MOUNT" in bloco
            # tanto a roupa (HIRELING_OUTFITS) quanto a habilidade
            # (HIRELING_SKILLS) usam o mesmo icone; as duas dao o mesmo desenho
            hireling = re.search(r"HIRELING_(?:OUTFITS|SKILLS)\.(\w+)", bloco)
            ident = re.search(r"\bid\s*=\s*(\d+)", bloco)

            if item or item_tab:
                ofertas.append({"icones": icones, "tipo": "item",
                                "id": int((item or item_tab).group(1))})
            elif hireling:
                ofertas.append({"icones": icones, "tipo": "hireling",
                                "chave": hireling.group(1)})
            elif sexo:
                # os ícones vêm na ordem do catálogo: masculino e feminino
                looks = {}
                for m in re.finditer(r"(male|female)\s*=\s*(\d+)", sexo.group(1)):
                    looks[m.group(1)] = int(m.group(2))
                ofertas.append({"icones": icones, "tipo": "outfit", "looks": looks})
            elif montaria and ident:
                ofertas.append({"icones": icones, "tipo": "montaria",
                                "id": int(ident.group(1))})
            else:
                ofertas.append({"icones": icones, "tipo": "sem_asset"})
    return ofertas


# ----------------------------------------------------------------- desenho

# Cores padrão do outfit. A máscara marca as quatro reges com amarelo, vermelho,
# verde e azul puros; o desenho entrega essas áreas em tom de cinza e a cor sai
# da multiplicação. Sem isto o outfit fica lavado, todo cinza.
CORES_PADRAO = {
    "cabeca": (222, 184, 135),   # cabelo/pele
    "corpo": (120, 145, 190),    # torso
    "pernas": (110, 95, 80),     # calça
    "pes": (95, 75, 60),         # botas
}


def colorir(base: Image.Image, mascara: Image.Image) -> Image.Image:
    """Aplica as cores padrão nas áreas que a máscara marca.

    A máscara usa canais puros por região: R alto = corpo, G alto = pernas,
    B alto = pés, R+G (amarelo) = cabeça. Onde ela não marca nada, o desenho
    original passa intacto (cajado, rosto, detalhes que não são coloríveis).
    """
    saida = base.copy()
    px_b, px_m, px_s = base.load(), mascara.load(), saida.load()
    largura, altura = base.size

    for yy in range(altura):
        for xx in range(largura):
            mr, mg, mb, ma = px_m[xx, yy]
            if ma == 0:
                continue
            if mr > 128 and mg > 128:
                cor = CORES_PADRAO["cabeca"]
            elif mr > 128:
                cor = CORES_PADRAO["corpo"]
            elif mg > 128:
                cor = CORES_PADRAO["pernas"]
            elif mb > 128:
                cor = CORES_PADRAO["pes"]
            else:
                continue

            r, g, b, a = px_b[xx, yy]
            if a == 0:
                continue
            # multiplicação: o cinza do desenho modula a cor escolhida
            px_s[xx, yy] = (r * cor[0] // 255, g * cor[1] // 255,
                            b * cor[2] // 255, a)
    return saida

class Desenhista:
    """Lê o appearances.dat e monta a imagem de um item ou de uma criatura."""

    def __init__(self, pasta_assets: Path):
        self.pasta = Path(pasta_assets)
        self.catalogo = ta.Catalogo(self.pasta)
        nome = next(e for e in self.catalogo.entradas
                    if e.get("type") == "appearances")["file"]
        self.aparencias = ta.Appearances(self.pasta / nome)
        self._folhas: dict[str, Image.Image] = {}
        self._cache: dict[tuple, dict | None] = {}

    # -- sprites --------------------------------------------------------
    def sprite(self, spriteid: int) -> Image.Image | None:
        entrada = self.catalogo.folha_de(spriteid)
        if not entrada:
            return None
        arquivo = entrada["file"]
        if arquivo not in self._folhas:
            self._folhas[arquivo] = ta.ler_folha(self.pasta / arquivo)
        folha = self._folhas[arquivo]
        larg, alt = ta.TAMANHOS[entrada["spritetype"]]
        por_linha = ta.LADO_FOLHA // larg
        i = spriteid - entrada["firstspriteid"]
        cx, cy = (i % por_linha) * larg, (i // por_linha) * alt
        return folha.crop((cx, cy, cx + larg, cy + alt))

    # -- estrutura da aparência ----------------------------------------
    def _grupo(self, categoria: str, ident: int) -> dict | None:
        """Primeiro frame group (parado) com pattern, layers e sprite ids.

        O sprite_ids do tibia_assets devolve os ids de TODOS os grupos numa
        lista só. Para indexar direção/addon/camada é preciso saber as
        dimensões, então aqui a aparência é lida com a estrutura preservada.
        """
        chave = (categoria, ident)
        if chave in self._cache:
            return self._cache[chave]

        campo = next(k for k, v in ta.CATEGORIAS.items() if v == categoria)
        b = self.aparencias.dados
        achado = None

        for n, v in ta._campos(b):
            if n != campo or not isinstance(v, tuple):
                continue
            este, grupos = None, []
            for n2, v2 in ta._campos(b, *v):
                if n2 == 1 and not isinstance(v2, tuple):
                    este = v2
                elif n2 == 2 and isinstance(v2, tuple):
                    grupos.append(v2)
            if este != ident or not grupos:
                continue

            # grupo 0 = parado; é a pose que a loja mostra
            info = {"pw": 1, "ph": 1, "pd": 1, "layers": 1, "ids": []}
            for n3, v3 in ta._campos(b, *grupos[0]):
                if n3 != 3 or not isinstance(v3, tuple):
                    continue
                for n4, v4 in ta._campos(b, *v3):
                    if n4 == 1: info["pw"] = v4
                    elif n4 == 2: info["ph"] = v4
                    elif n4 == 3: info["pd"] = v4
                    elif n4 == 4: info["layers"] = v4
                    elif n4 == 5: info["ids"].append(v4)
            achado = info
            break

        self._cache[chave] = achado
        return achado

    def item(self, item_id: int) -> Image.Image | None:
        ids = self.aparencias.sprite_ids("object", item_id)
        return self.sprite(ids[0]) if ids else None

    def criatura(self, looktype: int) -> Image.Image | None:
        """Outfit ou montaria virado para o sul (de frente para quem olha).

        Índice conforme ThingType::getSpriteIndex do client:
            (((fase * pd + z) * ph + y) * pw + x) * layers + camada

        Dois detalhes que só ficam claros olhando os sprites:

        - pattern_height NÃO é "addon acumulado": cada y é uma CAMADA de addon
          para sobrepor. y=0 é o corpo inteiro, y=1 e y=2 são só as peças de
          cada addon, soltas. Usar y = ph-1 sozinho rende fragmentos; o certo
          é compor 0, 1 e 2 nessa ordem.
        - a camada 1 é a máscara de cor (amarelo cabeça, vermelho corpo, verde
          pernas, azul pés). Sem aplicá-la, as áreas coloríveis ficam em tom de
          cinza, porque a cor sai da multiplicação.
        """
        info = self._grupo("outfit", looktype)
        if not info or not info["ids"]:
            return None

        pw, ph, pd = info["pw"], info["ph"], info["pd"]
        layers = max(1, info["layers"])
        x = 2 if pw > 2 else 0          # 0=norte 1=leste 2=sul 3=oeste
        z = 0
        ids = info["ids"]

        def pegar(y: int, camada: int) -> Image.Image | None:
            idx = (((0 * pd + z) * ph + y) * pw + x) * layers + camada
            return self.sprite(ids[idx]) if idx < len(ids) else None

        composto: Image.Image | None = None
        for y in range(ph):
            base = pegar(y, 0)
            if base is None:
                continue
            base = base.convert("RGBA")
            if layers > 1:
                mascara = pegar(y, 1)
                if mascara is not None:
                    base = colorir(base, mascara.convert("RGBA"))
            if composto is None:
                composto = Image.new("RGBA", base.size, (0, 0, 0, 0))
            if base.size != composto.size:
                continue
            composto.alpha_composite(base)

        return composto


# ------------------------------------------------------------------ saída

def ajustar(img: Image.Image) -> Image.Image:
    """Centraliza o sprite numa tela 64x64 transparente."""
    tela = Image.new("RGBA", (LADO, LADO), (0, 0, 0, 0))
    img = img.convert("RGBA")
    if img.width > LADO or img.height > LADO:
        img.thumbnail((LADO, LADO), Image.NEAREST)
    tela.alpha_composite(img, ((LADO - img.width) // 2, (LADO - img.height) // 2))
    return tela


def icone_neutro() -> Image.Image:
    """Placeholder liso para as ofertas que não têm sprite no jogo."""
    tela = Image.new("RGBA", (LADO, LADO), (0, 0, 0, 0))
    for y in range(6, LADO - 6):
        for x in range(6, LADO - 6):
            borda = x in (6, LADO - 7) or y in (6, LADO - 7)
            tela.putpixel((x, y), (90, 90, 96, 255) if borda else (58, 58, 64, 255))
    return tela


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--assets", required=True,
                   help="pasta de assets do client (a que tem catalog-content.json)")
    p.add_argument("--saida", required=True, help="pasta onde gravar os PNGs")
    p.add_argument("--neutro", action="store_true",
                   help="grava ícone liso para as ofertas sem sprite no jogo")
    args = p.parse_args()

    pasta_assets = Path(args.assets)
    if not (pasta_assets / "catalog-content.json").is_file():
        print(f"{pasta_assets} não tem catalog-content.json", file=sys.stderr)
        return 1

    saida = Path(args.saida)
    saida.mkdir(parents=True, exist_ok=True)

    desenhista = Desenhista(pasta_assets)
    mounts = ler_mounts()
    hirelings = ler_hirelings()
    ofertas = ler_ofertas()

    feitos = {"item": 0, "outfit": 0, "montaria": 0, "hireling": 0, "neutro": 0}
    falhas = []

    for oferta in ofertas:
        icones = oferta["icones"]
        tipo = oferta["tipo"]

        for pos, nome in enumerate(icones):
            destino = saida / nome
            img = None

            if tipo == "item":
                img = desenhista.item(oferta["id"])
            elif tipo == "montaria":
                clientid = mounts.get(oferta["id"])
                if clientid:
                    img = desenhista.criatura(clientid)
            elif tipo == "outfit":
                looks = oferta["looks"]
                # o catálogo lista masculino primeiro, depois feminino
                look = looks.get("male") if pos == 0 else looks.get("female")
                img = desenhista.criatura(look or looks.get("male") or 0)
            elif tipo == "hireling":
                look = hirelings.get(oferta["chave"])
                if look:
                    img = desenhista.criatura(look)

            if img is not None:
                ajustar(img).save(destino)
                feitos[tipo] += 1
            else:
                # NAO grava o neutro aqui: o mesmo icone pode aparecer em duas
                # ofertas (o hireling tem entrada de roupa e de habilidade), e
                # a segunda apagaria o desenho da primeira. O neutro so entra
                # depois, para o que ninguem conseguiu desenhar.
                falhas.append((nome, tipo))

    if args.neutro:
        vazio = icone_neutro()
        for nome, _ in falhas:
            destino = saida / nome
            if not destino.exists():
                vazio.save(destino)
                feitos["neutro"] += 1
        falhas = [(n, t) for n, t in falhas if not (saida / n).exists()]

    print(f"itens      : {feitos['item']}")
    print(f"montarias  : {feitos['montaria']}")
    print(f"outfits    : {feitos['outfit']}")
    print(f"hirelings  : {feitos['hireling']}")
    if args.neutro:
        print(f"neutros    : {feitos['neutro']}")
    total = sum(feitos.values())
    print(f"-> {total} ícones em {saida}")
    if falhas:
        print(f"sem desenho: {len(falhas)}  (use --neutro para preencher)")
        for nome, tipo in falhas[:5]:
            print(f"   {nome}  [{tipo}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
