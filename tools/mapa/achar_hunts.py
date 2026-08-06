"""Acha e contorna hunts sozinho, a partir do nome na planilha.

    python achar_hunts.py <mapa.otbm> --planilha catalogo.xlsx --nivel 200

Como funciona, em tres passos que nao pedem clique nenhum:

1. NOME -> MONSTROS. O bestiario de cada monstro do datapack diz onde ele mora
   (`Locations = "Antrum of the Fallen."`). Invertendo isso vira um indice
   local -> monstros. Ver bestiario.py.

2. MONSTROS -> COORDENADAS. O otservbr-monster.xml tem os 51.896 pontos de
   spawn com nome e posicao. Os spawns das especies da hunt sao agrupados
   (uniao por proximidade) e o maior grupo e' a hunt.

3. COORDENADAS -> CONTORNO. Enchente multi-semente que sai de TODOS os spawns
   do grupo ao mesmo tempo, limitada a `--alcance` tiles de algum spawn.

O passo 3 e' o que conserta o problema da varinha manual. Com raio a partir de
um clique, a superficie e' toda conectada e a enchente vazava pelo continente
inteiro (40 mil tiles numa hunt de ciclope). Limitando pela distancia ate o
spawn, a mesma hunt sai com 731 tiles no andar de superficie -- a fronteira
passa a ser "onde tem monstro", que e' a definicao real de uma hunt.

A saida e' um JSON por hunt no mesmo formato que o mapeador.html exporta,
entao da' para abrir no mapeador, conferir com os sprites na tela e corrigir o
que estiver torto. `obelisco` e `inicio` ficam nulos: onde o jogador entra e'
decisao de quem esta desenhando a hunt, nao da' para deduzir do mapa.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))

from bestiario import casar, indexar, normalizar  # noqa: E402
from gerar_minimapa import ITEM_VAZIO, ler_atributos  # noqa: E402
from otbm import Mapa  # noqa: E402

VIZINHOS = tuple((dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if (dx, dy) != (0, 0))

RE_BOSS = re.compile(r"bossRaceId\s*=\s*\d|isRewardBoss\s*=\s*true")


def ler_bosses(pasta: Path) -> set[str]:
    """Nomes que nao podem virar spawn de instancia.

    Mesmo criterio do tools/gerar_lista_bosses.py: a pasta monster/bosses/ mais
    o campo do bosstiary. Nenhum dos dois sozinho basta -- 99 bosses so' estao
    na pasta e 126 arquivos com o campo moram fora dela.
    """
    achados = set()
    for arq in pasta.rglob("*.lua"):
        texto = arq.read_text(encoding="utf-8", errors="replace")
        nome = re.search(r'createMonsterType\(\s*"([^"]+)"', texto)
        if nome and ("bosses" in arq.parts or RE_BOSS.search(texto)):
            achados.add(nome.group(1))
    return achados


BOSSES: set[str] = set()


RE_MONSTRO = re.compile(r'createMonsterType\(\s*"([^"]+)"')
RE_EXP = re.compile(r"monster\.experience\s*=\s*(\d+)")


def ler_forca(pasta_monstros: Path) -> dict[str, int]:
    """nome do monstro -> experiencia. E' o que separa hunt de area de novato.

    Sem isto o programa aceitava "Schrodinger's Island" casada com Tiquanda e
    entregava uma hunt de level 200+ cheia de Bat, Cobra e Flamingo.
    """
    forca = {}
    for arq in pasta_monstros.rglob("*.lua"):
        texto = arq.read_text(encoding="utf-8", errors="replace")
        nome = RE_MONSTRO.search(texto)
        if nome:
            exp = RE_EXP.search(texto)
            forca[nome.group(1)] = int(exp.group(1)) if exp else 0
    return forca


def mediana(valores: list[int]) -> int:
    if not valores:
        return 0
    v = sorted(valores)
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) // 2


def ler_spawns(caminho: Path) -> list[tuple[int, int, int, list[str]]]:
    """Le o arquivo de spawns. Os grupos tem tag <monster> aninhada em <monster>."""
    raiz = ET.parse(caminho).getroot()
    saida = []
    for grupo in raiz.findall("monster"):
        nomes = [m.get("name") for m in grupo.findall("monster") if m.get("name")]
        if nomes:
            saida.append((int(grupo.get("centerx")), int(grupo.get("centery")),
                          int(grupo.get("centerz")), nomes))
    return saida


def agrupar(pontos: list[tuple[int, int, int]], passo: int = 30) -> list[list[int]]:
    """Une pontos proximos em xy (ignorando o andar) e devolve os grupos.

    Ignorar o andar e' de proposito: uma hunt e' um lugar, e o mesmo lugar
    costuma ter spawn na superficie e nos andares de baixo. Separar por andar
    partiria a hunt em pedacos que depois teriam de ser remontados.
    """
    pai = list(range(len(pontos)))

    def raiz(a: int) -> int:
        while pai[a] != a:
            pai[a] = pai[pai[a]]
            a = pai[a]
        return a

    celas: dict[tuple[int, int], list[int]] = defaultdict(list)
    for i, (x, y, _) in enumerate(pontos):
        celas[(x // passo, y // passo)].append(i)
    for (cx, cy), indices in celas.items():
        vizinhas = [j for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                    for j in celas.get((cx + dx, cy + dy), ())]
        for i in indices:
            xi, yi, _ = pontos[i]
            for j in vizinhas:
                if j <= i:
                    continue
                xj, yj, _ = pontos[j]
                if abs(xi - xj) <= passo and abs(yi - yj) <= passo:
                    a, b = raiz(i), raiz(j)
                    if a != b:
                        pai[b] = a

    grupos: dict[int, list[int]] = defaultdict(list)
    for i in range(len(pontos)):
        grupos[raiz(i)].append(i)
    return sorted(grupos.values(), key=len, reverse=True)


class Contornador:
    """Guarda o mapa aberto e responde se um tile da' para pisar."""

    def __init__(self, mapa_otbm: Path):
        self.mapa = Mapa(str(mapa_otbm), cache_tiles=False, limite_areas=24, mapear=True)
        self.atributos = ler_atributos(RAIZ / "data/items/appearances.dat")

    def andavel(self, x: int, y: int, z: int) -> bool:
        t = self.mapa.tile(x, y, z)
        if not t or not t.chao:
            return False
        if self.atributos.get(t.chao, ITEM_VAZIO).bloqueia:
            return False
        for iid, _, _ in t.itens:
            if self.atributos.get(iid, ITEM_VAZIO).bloqueia:
                return False
        return True

    def contornar(self, spawns: list[tuple[int, int]], z: int,
                  alcance: int, margem: int) -> set[tuple[int, int]]:
        """Enchente a partir de todos os spawns, presa a `alcance` deles."""
        permitido: set[tuple[int, int]] = set()
        for sx, sy in spawns:
            for dx in range(-alcance, alcance + 1):
                for dy in range(-alcance, alcance + 1):
                    permitido.add((sx + dx, sy + dy))

        dentro = {p for p in spawns if self.andavel(p[0], p[1], z)}
        fila = list(dentro)
        while fila:
            cx, cy = fila.pop()
            for dx, dy in VIZINHOS:
                p = (cx + dx, cy + dy)
                if p in dentro or p not in permitido:
                    continue
                if self.andavel(p[0], p[1], z):
                    dentro.add(p)
                    fila.append(p)

        total = set(dentro)
        borda = dentro
        for _ in range(max(0, margem)):
            nova = set()
            for cx, cy in borda:
                for dx, dy in VIZINHOS:
                    p = (cx + dx, cy + dy)
                    if p not in total:
                        total.add(p)
                        nova.add(p)
            borda = nova
        return total


def montar_doc(h, especies, do_grupo, local, tipo, origem_nome, descartados,
               exp, ct, spawns, forca, args):
    """Contorna um grupo de spawns e monta o JSON da hunt.

    Devolve (doc, conjuntos, "") ou (None, None, motivo da recusa). Usado
    pelas duas passagens -- pela do nome e pela da area -- para que uma hunt
    achada de um jeito ou de outro passe exatamente pelos mesmos filtros.
    """
    por_andar: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for x, y, z in do_grupo:
        por_andar[z].append((x, y))

    limites: dict[str, list[list[int]]] = {}
    for z, pts in sorted(por_andar.items()):
        tiles = ct.contornar(pts, z, args.alcance, args.margem)
        if tiles:
            limites[str(z)] = sorted([x, y] for x, y in tiles)
    if not limites:
        return None, None, "nada pisavel"

    # bbox, origem do recorte e monstros de dentro, iguais ao mapeador.html
    caixas = {}
    for z, lista in limites.items():
        xs = [t[0] for t in lista]
        ys = [t[1] for t in lista]
        caixas[z] = {"x0": min(xs), "y0": min(ys), "x1": max(xs), "y1": max(ys),
                     "tiles": len(lista)}
    org = {"x": min(c["x0"] for c in caixas.values()),
           "y": min(c["y0"] for c in caixas.values())}

    conjuntos = {z: {tuple(t) for t in lista} for z, lista in limites.items()}
    dentro: dict[str, list[dict]] = {}
    total_mon = 0
    barrados: Counter = Counter()
    for x, y, z, nomes in spawns:
        s = conjuntos.get(str(z))
        if not s or (x, y) not in s:
            continue
        for n in nomes:
            # Boss dentro do contorno nao entra na hunt. Numa instancia
            # privada quem decide quando abrir e fechar e' o jogador, entao o
            # respawn do boss viraria decisao dele: entrar, matar, sair,
            # entrar de novo. O servidor tambem barra na hora de nascer, mas
            # deixar no JSON so' empurraria o problema para la'.
            if n in BOSSES:
                barrados[n] += 1
                continue
            dentro.setdefault(str(z), []).append(
                {"nome": n, "x": x, "y": y, "z": z,
                 "rx": x - org["x"], "ry": y - org["y"]})
            total_mon += 1

    tipos = Counter(m["nome"] for lista in dentro.values() for m in lista)
    # Quanto do que ficou dentro e' realmente da hunt. Se der baixo, a
    # enchente pegou area vizinha e vale olhar no mapeador.
    proprios = sum(n for t, n in tipos.items() if t in especies)
    pureza = round(100 * proprios / total_mon) if total_mon else 0
    # Forca do que ficou DENTRO, nao so' do que era esperado: mede se o
    # contorno pegou area de bicho fraco em volta.
    exp_dentro = mediana([forca.get(m["nome"], 0)
                          for lista in dentro.values() for m in lista])
    # Pureza baixa quer dizer que a maioria do que ficou dentro nao e' da
    # hunt: o contorno vazou para a vizinhanca. A Medusa Tower saia com
    # 110 mil tiles, 28% de pureza e Gargoyle e Earth Elemental dentro --
    # o mesmo estrago da area errada, so' que por outro caminho, porque as
    # especies ESPERADAS eram fortes. Entregar isso e' pior que nao
    # entregar nada: parece pronto ate' alguem abrir.
    if origem_nome == "area":
        # Pela regiao a pureza mede a pergunta errada. As "especies esperadas"
        # sao a fauna forte de Oramond inteira, nao as desta hunt: um contorno
        # perfeito de uma caverna de Oramond marca 40% de pureza so' porque as
        # outras especies fortes da regiao moram noutra caverna. O que importa
        # aqui e' o que a hunt e' -- se o que esta dentro serve para 200+ --,
        # e isso quem responde e' a experiencia mediana de quem mora la.
        if exp_dentro < args.exp_minima:
            return None, None, f"bicho fraco dentro (exp mediana {exp_dentro})"
    elif pureza < args.pureza_minima:
        return None, None, f"contorno vazou (pureza {pureza}%)"
    # Pela area o nome e' palpite: o bestiario disse "Marapur", nao o nome da
    # hunt, e quem decidiu qual pedaco de Marapur e' esta hunt foi a direcao
    # escrita na planilha. O contorno pode estar certo e a etiqueta errada,
    # entao nunca sobe de "baixa".
    if origem_nome == "area":
        confianca = "baixa"
    else:
        confianca = "alta" if tipo == "exato" and pureza >= 70 else "media"

    doc = {
        "id": h["id"], "nome": h["nome"],
        "obelisco": None, "inicio": None,
        "andares": sorted(int(z) for z in limites),
        "origemRecorte": org, "bbox": caixas, "inicioRelativo": None,
        "monstros": dentro, "totalMonstros": total_mon,
        "monstrosPorTipo": dict(tipos.most_common()),
        "limites": limites,
        "gerado": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "automatico": {
            "localBestiario": local, "casamento": tipo,
            "origemDoNome": origem_nome,
            "especiesEsperadas": sorted(especies),
            "spawnsNoGrupo": len(do_grupo), "gruposDescartados": descartados,
            "pureza": pureza, "confianca": confianca,
            "expEsperada": exp, "expDentro": exp_dentro,
            "alcance": args.alcance, "margem": args.margem,
            "bossesBarrados": dict(barrados.most_common()),
        },
    }
    return doc, conjuntos, ""


# Rumo escrito na coluna "Localizacao" da planilha ("Nordeste de Isle of Ada").
# x cresce para leste e y cresce para o sul, que e' a convencao do mapa.
DIRECOES = {
    "norte": (0, -1), "sul": (0, 1), "leste": (1, 0), "oeste": (-1, 0),
    "nordeste": (1, -1), "noroeste": (-1, -1),
    "sudeste": (1, 1), "sudoeste": (-1, 1),
    "centro": (0, 0), "central": (0, 0), "arredores": (0, 0),
}
FUNDO = ("abaixo", "sob ", "subsolo", "subterraneo", "embaixo", "sob o", "sob a")


def pista(localizacao: str) -> tuple[tuple[int, int] | None, bool]:
    """Le o rumo e a profundidade da descricao da planilha."""
    texto = normalizar(localizacao)
    rumo = next((v for k, v in DIRECOES.items() if texto.startswith(k)), None)
    if rumo is None:
        rumo = next((v for k, v in DIRECOES.items() if f" {k} " in f" {texto} "), None)
    return rumo, any(p.strip() in texto for p in FUNDO)


def ler_planilha(caminho: Path, nivel: int) -> list[dict]:
    import openpyxl
    ws = openpyxl.load_workbook(caminho, read_only=True, data_only=True)["Catalogo_Hunts"]
    linhas = [r for r in ws.iter_rows(values_only=True)]
    i = next(k for k, r in enumerate(linhas) if r and r[0] == "ID")
    cab = linhas[i]

    def col(pedaco: str) -> int | None:
        for j, c in enumerate(cab):
            if c and pedaco.lower() in str(c).lower():
                return j
        return None

    c_lvl, c_area, c_loc = col("Level m"), col("rea / Acesso"), col("Localiza")
    saida = []
    for r in linhas[i + 1:]:
        if not (r and isinstance(r[0], int)):
            continue
        tem_level = isinstance(r[c_lvl], (int, float))
        # Com nivel 0 (pedido por id) entra tambem quem esta sem level na
        # planilha -- Cyclopolis, por exemplo, que e' o exemplo do mapeador.
        if nivel and not (tem_level and r[c_lvl] >= nivel):
            continue
        saida.append({"id": r[0], "nome": str(r[1]),
                      "level": int(r[c_lvl]) if tem_level else 0,
                      "area": str(r[c_area] or ""), "local": str(r[c_loc] or "")})
    return saida


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("mapa")
    p.add_argument("--planilha", required=True)
    p.add_argument("--nivel", type=int, default=200, help="level minimo (padrao 200)")
    p.add_argument("--alcance", type=int, default=14,
                   help="quantos tiles alem do spawn a hunt pode ir (padrao 14)")
    p.add_argument("--margem", type=int, default=2, help="tiles de parede em volta (padrao 2)")
    p.add_argument("--passo-area", type=int, default=15,
                   help="distancia que junta spawns na busca por regiao (padrao 15)")
    p.add_argument("--minimo-spawns", type=int, default=4,
                   help="grupo com menos spawns que isso e' descartado (padrao 4)")
    p.add_argument("--exp-minima", type=int, default=1000,
                   help="experiencia mediana minima das especies (padrao 1000)")
    p.add_argument("--pureza-minima", type=int, default=50,
                   help="%% dos monstros de dentro que precisam ser da hunt (padrao 50)")
    p.add_argument("--sobreposicao", type=float, default=0.3,
                   help="acima disso duas hunts sao o mesmo lugar (padrao 0.3)")
    p.add_argument("--saida", default=str(RAIZ / "tools/mapa/hunts_automaticas"))
    p.add_argument("--so", help="processa so a hunt com este id (para testar)")
    p.add_argument("--perto", metavar="X,Y",
                   help="prefere o grupo de spawns mais proximo deste ponto")
    args = p.parse_args()

    t0 = time.time()
    saida = Path(args.saida)
    saida.mkdir(parents=True, exist_ok=True)

    print("lendo bestiario...", end=" ", flush=True)
    indice = indexar(RAIZ / "data-otservbr-global/monster")
    print(f"{len(indice)} locais")

    print("lendo spawns...", end=" ", flush=True)
    spawns = ler_spawns(RAIZ / "data-otservbr-global/world/otservbr-monster.xml")
    por_especie: dict[str, list[tuple[int, int, int]]] = defaultdict(list)
    for x, y, z, nomes in spawns:
        for n in nomes:
            por_especie[n].append((x, y, z))
    print(f"{len(spawns)} pontos, {len(por_especie)} especies")

    global BOSSES
    BOSSES = ler_bosses(RAIZ / "data-otservbr-global/monster")
    print(f"{len(BOSSES)} bosses ficam de fora")

    print("lendo forca dos monstros...", end=" ", flush=True)
    forca = ler_forca(RAIZ / "data-otservbr-global/monster")
    print(f"{len(forca)} monstros")

    print("abrindo o mapa...", end=" ", flush=True)
    ct = Contornador(Path(args.mapa))
    print(f"{time.time() - t0:.1f}s")

    # Com --so o filtro de level nao vale: pedir uma hunt pelo id e' pedir
    # aquela hunt. E' assim que se gera o exemplo dos ciclopes, que nao tem
    # level na planilha e ficaria de fora de qualquer corte.
    hunts = ler_planilha(Path(args.planilha), 0 if args.so else args.nivel)
    if args.so:
        hunts = [h for h in hunts if str(h["id"]) == args.so]
    print(f"\n{len(hunts)} hunts de level {args.nivel}+\n")

    relatorio = []
    prontas = []
    for h in hunts:
        local, especies, tipo = casar(h["nome"], indice)
        if not especies:
            relatorio.append({**h, "estado": "sem monstros", "confianca": "nenhuma"})
            print(f"  [{h['id']:3}] {h['nome'][:34]:36} -- nao achei no bestiario")
            continue

        # Forca das especies esperadas. O casamento pode estar sintaticamente
        # certo e semanticamente errado: e' assim que uma hunt de level 200+
        # acabava com Bat, Cobra e Flamingo dentro. Medido nas 66 hunts que
        # casam, so' duas ficam abaixo de 1000 e o resto passa de 1100 --
        # a separacao e' limpa, nao um corte arbitrario.
        exp = mediana([forca.get(e, 0) for e in especies])
        if exp < args.exp_minima:
            relatorio.append({**h, "estado": f"monstros fracos (exp mediana {exp})",
                              "confianca": "nenhuma", "monstros": sorted(especies)})
            print(f"  [{h['id']:3}] {h['nome'][:34]:36} -- monstros fracos "
                  f"(exp mediana {exp}, minimo {args.exp_minima})")
            continue

        pontos = [pt for e in especies for pt in por_especie.get(e, ())]
        if not pontos:
            relatorio.append({**h, "estado": "monstros sem spawn", "confianca": "nenhuma",
                              "monstros": sorted(especies)})
            print(f"  [{h['id']:3}] {h['nome'][:34]:36} -- {len(especies)} monstros, nenhum com spawn")
            continue

        grupos = agrupar(pontos)
        # Por padrao vale o maior grupo. Com --perto vale o mais proximo do
        # ponto dado: ha nome de area que se repete pelo mapa (Cyclops Camp
        # tem varios), e ai o maior nem sempre e' o que se quer.
        grupo = grupos[0]
        if args.perto:
            alvo_x, alvo_y = (int(v) for v in args.perto.split(","))

            def distancia(g):
                xs = [pontos[i][0] for i in g]
                ys = [pontos[i][1] for i in g]
                return max(abs(sum(xs) // len(xs) - alvo_x),
                           abs(sum(ys) // len(ys) - alvo_y))

            candidatos = [g for g in grupos if len(g) >= args.minimo_spawns]
            if candidatos:
                grupo = min(candidatos, key=distancia)
        if len(grupo) < args.minimo_spawns:
            relatorio.append({**h, "estado": f"grupo pequeno ({len(grupo)})",
                              "confianca": "nenhuma", "monstros": sorted(especies)})
            print(f"  [{h['id']:3}] {h['nome'][:34]:36} -- maior grupo tem so {len(grupo)} spawns")
            continue

        doc, conjuntos, motivo = montar_doc(
            h, especies, [pontos[i] for i in grupo], local, tipo, "nome",
            len(grupos) - 1, exp, ct, spawns, forca, args)
        if not doc:
            relatorio.append({**h, "estado": motivo, "confianca": "nenhuma",
                              "monstros": sorted(especies)})
            print(f"  [{h['id']:3}] {h['nome'][:34]:36} -- {motivo}")
            continue

        a = doc["automatico"]
        prontas.append((h, doc, conjuntos))
        tiles = sum(len(v) for v in doc["limites"].values())
        relatorio.append({**h, "estado": "ok", "confianca": a["confianca"],
                          "tiles": tiles, "andares": doc["andares"],
                          "pureza": a["pureza"], "expEsperada": exp,
                          "expDentro": a["expDentro"], "monstros": sorted(especies)})
        print(f"  [{h['id']:3}] {h['nome'][:34]:36} {tiles:6} tiles  "
              f"{len(doc['limites'])} andares  pureza {a['pureza']:3}%  "
              f"exp {a['expDentro']:5}  {a['confianca']}")

    # ------------------------------------------------- segunda volta: por area
    # 76 das 146 nao tem o nome no bestiario -- ele diz "Marapur", nao
    # "Ancestral Ruins". Aqui o caminho e' o inverso: pega os monstros da
    # REGIAO, agrupa os spawns dela e da' UM grupo para cada hunt, escolhido
    # pelo rumo que a planilha escreve ("Nordeste de Isle of Ada").
    #
    # Isto ja existiu antes como remendo e deu errado: caia sempre no maior
    # grupo, e catorze hunts de Marapur viravam catorze copias do mesmo lugar.
    # A diferenca agora e' que cada hunt leva um grupo DIFERENTE, e o rumo
    # decide qual. Onde nao houver grupo sobrando, a hunt fica sem contorno --
    # e' melhor do que repetir.
    sem_nome = [h for h in hunts
                if any(r["id"] == h["id"] and r["estado"] == "sem monstros"
                       for r in relatorio)]
    # Chave normalizada: a planilha escreve "Ab'Dendriel" numa linha e
    # "Ab'dendriel" noutra, e com a chave crua viravam duas regioes que
    # recebiam os MESMOS grupos -- duas hunts no mesmo lugar, de novo.
    por_area: dict[str, list[dict]] = defaultdict(list)
    for h in sem_nome:
        if h["area"]:
            por_area[normalizar(h["area"])].append(h)
    if por_area:
        print(f"\n{len(sem_nome)} sem nome no bestiario -> "
              f"tentando por area ({len(por_area)} regioes)\n")

    for area, doArea in sorted(por_area.items(), key=lambda kv: -len(kv[1])):
        local, especies, tipo = casar(area, indice)
        if not especies:
            continue
        # A regiao inteira traz a fauna toda, inclusive Bat e Flamingo. Uma
        # hunt de 200+ e' definida pelos fortes, entao os fracos saem antes de
        # agrupar -- senao os spawns deles costuram pedacos distantes do mapa
        # num grupo so'.
        fortes = {e for e in especies if forca.get(e, 0) >= args.exp_minima}
        if not fortes:
            continue
        # Agrupamento mais apertado que o da passagem pelo nome. La o grupo e'
        # a hunt inteira e 30 tiles nao a parte; aqui e' a REGIAO inteira, e
        # com 30 ela vira um grupo so': Oramond dava 1 grupo para 6 hunts, e
        # cinco ficavam sem lugar. Com 15 da' 9 grupos, um por caverna.
        pontos = [pt for e in fortes for pt in por_especie.get(e, ())]
        grupos = [g for g in agrupar(pontos, args.passo_area)
                  if len(g) >= args.minimo_spawns]
        if not grupos:
            continue

        cx = sum(pontos[i][0] for g in grupos for i in g) // sum(len(g) for g in grupos)
        cy = sum(pontos[i][1] for g in grupos for i in g) // sum(len(g) for g in grupos)

        def perfil(g):
            xs = [pontos[i][0] for i in g]
            ys = [pontos[i][1] for i in g]
            zs = [pontos[i][2] for i in g]
            gx, gy = sum(xs) // len(xs), sum(ys) // len(ys)
            dx, dy = gx - cx, gy - cy
            tam = max(1.0, (dx * dx + dy * dy) ** 0.5)
            return (dx / tam, dy / tam), sum(1 for z in zs if z > 7) / len(zs), len(g)

        perfis = [perfil(g) for g in grupos]

        # Pontua cada par (hunt, grupo) e distribui pelo melhor primeiro. Sem
        # rumo na planilha, o desempate e' o tamanho do grupo.
        pares = []
        for ih, h in enumerate(doArea):
            rumo, fundo = pista(h["local"])
            for ig, (vetor, prof, tam) in enumerate(perfis):
                nota = 0.0
                if rumo and rumo != (0, 0):
                    norma = (rumo[0] ** 2 + rumo[1] ** 2) ** 0.5
                    nota += 2.0 * (vetor[0] * rumo[0] + vetor[1] * rumo[1]) / norma
                elif rumo == (0, 0):
                    nota += 2.0 * (1 - abs(vetor[0]) - abs(vetor[1]))
                nota += (prof if fundo else 1 - prof)
                nota += min(tam, 200) / 1000.0
                pares.append((nota, ih, ig))
        pares.sort(reverse=True)

        usados_h, usados_g = set(), set()
        for nota, ih, ig in pares:
            if ih in usados_h or ig in usados_g:
                continue
            usados_h.add(ih)
            usados_g.add(ig)
            h = doArea[ih]
            exp = mediana([forca.get(e, 0) for e in fortes])
            doc, conj, motivo = montar_doc(
                h, fortes, [pontos[i] for i in grupos[ig]], local, tipo, "area",
                len(grupos) - 1, exp, ct, spawns, forca, args)
            for r in relatorio:
                if r["id"] != h["id"]:
                    continue
                if not doc:
                    r["estado"] = f"por area: {motivo}"
                else:
                    a = doc["automatico"]
                    a["rumoPlanilha"] = h["local"]
                    r.update({"estado": "ok", "confianca": a["confianca"],
                              "tiles": sum(len(v) for v in doc["limites"].values()),
                              "andares": doc["andares"], "pureza": a["pureza"],
                              "expDentro": a["expDentro"],
                              "monstros": sorted(fortes)})
            if doc:
                prontas.append((h, doc, conj))
                t = sum(len(v) for v in doc["limites"].values())
                print(f"  [{h['id']:3}] {h['nome'][:30]:32} {t:6} tiles  "
                      f"pureza {doc['automatico']['pureza']:3}%  "
                      f"<- {area[:16]:18} {h['local'][:22]}")
        faltou = len(doArea) - len(usados_h)
        if faltou:
            print(f"        ({faltou} hunt(s) de {area} sem grupo sobrando)")

    # ---------------------------------------------------- um lugar, uma hunt
    # Duas hunts no mesmo lugar nao existe no jogo, entao aqui e' sempre erro:
    # ou o nome casou com o lugar errado, ou sao a mesma area com dois nomes.
    # Fica a de casamento mais forte e as outras saem -- entregar as duas seria
    # empurrar para quem for conferir a decisao que o programa devia tomar.
    def nota(par):
        _, d, _ = par
        a = d["automatico"]
        return (a["casamento"] == "exato", a["pureza"], a["spawnsNoGrupo"])

    prontas.sort(key=nota, reverse=True)
    aceitas: list[tuple] = []
    for h, doc, conj in prontas:
        meu = {(z, t) for z, s in conj.items() for t in s}
        colide = None
        for h2, doc2, conj2 in aceitas:
            outro = {(z, t) for z, s in conj2.items() for t in s}
            comum = len(meu & outro)
            if comum and comum / min(len(meu), len(outro)) >= args.sobreposicao:
                colide = (h2, doc2, round(100 * comum / min(len(meu), len(outro))))
                break
        if colide:
            h2, _, pct = colide
            for r in relatorio:
                if r["id"] == h["id"]:
                    r["estado"] = f"mesmo lugar da hunt {h2['id']} ({pct}% igual)"
                    r["confianca"] = "nenhuma"
            print(f"  [{h['id']:3}] {h['nome'][:34]:36} -- REMOVIDA: {pct}% igual "
                  f"a [{h2['id']}] {h2['nome']}")
            continue
        aceitas.append((h, doc, conj))

    for arq in saida.glob("hunt_*.json"):
        arq.unlink()
    for h, doc, _ in aceitas:
        nome_arq = f"hunt_{h['id']}_{re.sub(r'[^A-Za-z0-9]+', '_', h['nome'])}.json"
        (saida / nome_arq).write_text(json.dumps(doc, ensure_ascii=False, indent=1),
                                      encoding="utf-8")
        for r in relatorio:
            if r["id"] == h["id"]:
                r["arquivo"] = nome_arq

    (saida / "_relatorio.json").write_text(
        json.dumps(relatorio, ensure_ascii=False, indent=1), encoding="utf-8")
    c = Counter(r["confianca"] for r in relatorio)
    print(f"\n{time.time() - t0:.0f}s  |  {len(aceitas)} hunts entregues  "
          f"(alta {c['alta']}  media {c['media']}  baixa {c['baixa']})  "
          f"| {c['nenhuma']} recusadas")
    print(f"saida em {saida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
