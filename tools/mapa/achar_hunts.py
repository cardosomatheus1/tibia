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
        if not (isinstance(r[c_lvl], (int, float)) and r[c_lvl] >= nivel):
            continue
        saida.append({"id": r[0], "nome": str(r[1]), "level": int(r[c_lvl]),
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

    print("lendo forca dos monstros...", end=" ", flush=True)
    forca = ler_forca(RAIZ / "data-otservbr-global/monster")
    print(f"{len(forca)} monstros")

    print("abrindo o mapa...", end=" ", flush=True)
    ct = Contornador(Path(args.mapa))
    print(f"{time.time() - t0:.1f}s")

    hunts = ler_planilha(Path(args.planilha), args.nivel)
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
        grupo = grupos[0]
        if len(grupo) < args.minimo_spawns:
            relatorio.append({**h, "estado": f"grupo pequeno ({len(grupo)})",
                              "confianca": "nenhuma", "monstros": sorted(especies)})
            print(f"  [{h['id']:3}] {h['nome'][:34]:36} -- maior grupo tem so {len(grupo)} spawns")
            continue

        do_grupo = [pontos[i] for i in grupo]
        por_andar: dict[int, list[tuple[int, int]]] = defaultdict(list)
        for x, y, z in do_grupo:
            por_andar[z].append((x, y))

        limites: dict[str, list[list[int]]] = {}
        for z, pts in sorted(por_andar.items()):
            tiles = ct.contornar(pts, z, args.alcance, args.margem)
            if tiles:
                limites[str(z)] = sorted([x, y] for x, y in tiles)

        if not limites:
            relatorio.append({**h, "estado": "nada pisavel", "confianca": "nenhuma",
                              "monstros": sorted(especies)})
            print(f"  [{h['id']:3}] {h['nome'][:34]:36} -- nenhum tile pisavel")
            continue

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
        for x, y, z, nomes in spawns:
            s = conjuntos.get(str(z))
            if not s or (x, y) not in s:
                continue
            for n in nomes:
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
        if pureza < args.pureza_minima:
            relatorio.append({**h, "estado": f"contorno vazou (pureza {pureza}%)",
                              "confianca": "nenhuma", "monstros": sorted(especies)})
            print(f"  [{h['id']:3}] {h['nome'][:34]:36} -- contorno vazou "
                  f"(pureza {pureza}%, {sum(len(v) for v in limites.values())} tiles)")
            continue

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
                "especiesEsperadas": sorted(especies),
                "spawnsNoGrupo": len(grupo), "gruposDescartados": len(grupos) - 1,
                "pureza": pureza, "confianca": confianca,
                "expEsperada": exp, "expDentro": exp_dentro,
                "alcance": args.alcance, "margem": args.margem,
            },
        }
        prontas.append((h, doc, conjuntos))

        tiles = sum(len(v) for v in limites.values())
        relatorio.append({**h, "estado": "ok", "confianca": confianca, "tiles": tiles,
                          "andares": doc["andares"], "pureza": pureza,
                          "expEsperada": exp, "expDentro": exp_dentro,
                          "monstros": sorted(especies)})
        print(f"  [{h['id']:3}] {h['nome'][:34]:36} {tiles:6} tiles  "
              f"{len(limites)} andares  pureza {pureza:3}%  exp {exp_dentro:5}  {confianca}")

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
