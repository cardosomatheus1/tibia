"""Transforma uma hunt revisada nos arquivos que o servidor consome.

    python gerar_instancia.py <mapa.otbm> --hunt hunts_revisadas/hunt_4_x.json

De um JSON do mapeador saem quatro coisas:

    world/hunt_instances/<slug>_instance.otbm   o recorte do mapa
    scripts/.../spawns_<slug>.lua               os pontos de spawn
    scripts/.../<slug>_selector.lua             o obelisco e a janela
    catalogo_<slug>.lua                         o trecho para o catalogo

A hunt dos ciclopes foi montada peca por peca, a mao. Repetir isso oito vezes
convidaria ao erro de digitacao que ninguem ve -- um offset trocado corrompe o
mapa em silencio, e a spec (secao 3.1) ja avisa disso. Aqui tudo sai da mesma
fonte: o JSON que foi conferido na tela.

O QUE ESTE PROGRAMA NAO DECIDE

`retornoEmergencia` fica no templo de Thais para todas. E' uma posicao
verificada e segura, mas nao e' a mais proxima de cada hunt -- so' e' usada
quando o retorno normal falha. Vale revisar hunt a hunt depois.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

from gerar_minimapa import ITEM_VAZIO, ler_atributos  # noqa: E402
from otbm import Mapa  # noqa: E402

DESTINO_MAPA = RAIZ / "data-otservbr-global/world/hunt_instances"
DESTINO_LUA = RAIZ / "data-otservbr-global/scripts/custom/hunt_instances"

# Faixa livre do mapa. A oficial acaba em x 34304; daqui para cima e' vazio.
# Uma banda de y por hunt, seis slots ao longo do x.
BANDA_Y_BASE = 36864
BANDA_Y_PASSO = 1024
SLOT_X_BASE = 36864
ACTION_ID_BASE = 65001

TEMPLO_THAIS = "Position(32369, 32241, 7)"

# Margem de terreno em volta da hunt, em tiles (spec 6.1.1). Nao e' enfeite: o
# viewport mostra 8 a 11 tiles alem de onde o jogador pode ir, e sem margem ele
# ve o VAZIO na borda e a instancia deixa de parecer o mapa de verdade. Foi a
# primeira coisa que se notou comparando com a hunt dos ciclopes, que tem 16.
MARGEM = 16

# Vizinhos em cruz, para procurar tile pisavel perto de um ponto.
CRUZ = [(0, 0), (0, -1), (0, 1), (-1, 0), (1, 0),
        (-1, -1), (1, -1), (-1, 1), (1, 1)]


def slugificar(nome: str) -> str:
    s = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")
    return re.sub(r"_+", "_", s)


def camel(slug: str) -> str:
    partes = slug.split("_")
    return partes[0] + "".join(p.capitalize() for p in partes[1:])


class Mundo:
    """O mapa aberto, com a pergunta que importa: da' para pisar aqui?"""

    def __init__(self, caminho: Path):
        self.mapa = Mapa(str(caminho), cache_tiles=False, limite_areas=24, mapear=True)
        self.atributos = ler_atributos(self._appearances())

    @staticmethod
    def _appearances() -> Path:
        do_repo = RAIZ / "data/items/appearances.dat"
        if do_repo.exists():
            return do_repo
        assets = Path.home() / "AppData/Local/Mapeador de Hunts/assets"
        achados = sorted(assets.glob("appearances*.dat"))
        if achados:
            return achados[0]
        raise FileNotFoundError("nao achei o appearances.dat")

    def andavel(self, x: int, y: int, z: int) -> bool:
        t = self.mapa.tile(x, y, z)
        if not t or not t.chao:
            return False
        if self.atributos.get(t.chao, ITEM_VAZIO).bloqueia:
            return False
        return all(not self.atributos.get(i, ITEM_VAZIO).bloqueia
                   for i, _, _ in t.itens)

    def vazio(self, x: int, y: int, z: int) -> bool:
        return self.mapa.tile(x, y, z) is None

    def perto_andavel(self, x: int, y: int, z: int, quantos: int) -> list[tuple[int, int, int]]:
        """Ate' `quantos` tiles pisaveis em volta do ponto, ele incluso."""
        saida = []
        for dx, dy in CRUZ:
            if self.andavel(x + dx, y + dy, z):
                saida.append((x + dx, y + dy, z))
            if len(saida) >= quantos:
                break
        return saida


def faixa_livre(mundo: Mundo, x0: int, y0: int, larg: int, alt: int,
                andares: list[int]) -> tuple[bool, str]:
    """Confere que o retangulo do slot esta vazio em todos os andares.

    Amostra em grade de 8: percorrer tile a tile em 6 slots x 9 andares seria
    lento e nao acrescentaria -- o mapa e' gravado em blocos de 256, entao
    qualquer area ocupada aparece na amostra.
    """
    for z in andares:
        for dx in range(0, larg, 8):
            for dy in range(0, alt, 8):
                if not mundo.vazio(x0 + dx, y0 + dy, z):
                    return False, f"ocupado em ({x0 + dx}, {y0 + dy}, {z})"
    return True, ""


def gerar_spawns(doc: dict, slug: str, org: dict) -> tuple[str, int]:
    """Lua com os pontos de spawn, ja relativos ao recorte."""
    pontos = []
    for z, lista in sorted(doc.get("monstros", {}).items(), key=lambda kv: int(kv[0])):
        for m in lista:
            pontos.append((m["nome"], m["x"] - org["x"], m["y"] - org["y"], int(z)))
    linhas = [
        f"-- Pontos de spawn de {doc['nome']}.",
        "-- GERADO POR tools/mapa/gerar_instancia.py -- NAO EDITE A MAO.",
        "--",
        "-- x/y sao RELATIVOS ao recorte e z e' ABSOLUTO, igual ao .otbm: a",
        "-- posicao real e' origem do slot + isto. Coordenada absoluta aqui",
        "-- somada ao offset do slot estouraria o uint16 (spec 3.1).",
        "--",
        "-- Bosses ja ficaram de fora na geracao do JSON, e o instance_spawns",
        "-- barra de novo na hora de nascer.",
        "",
        "HuntInstanceSpawns = HuntInstanceSpawns or {}",
        "",
        f'HuntInstanceSpawns["{slug}"] = {{',
    ]
    for nome, x, y, z in pontos:
        seguro = nome.replace("\\", "\\\\").replace('"', '\\"')
        linhas.append(f'\t{{ nome = "{seguro}", x = {x}, y = {y}, z = {z}, '
                      f"respawnMs = 90000 }},")
    linhas.append("}")
    linhas.append("")
    return "\n".join(linhas), len(pontos)


def gerar_selector(slug: str, chave: str, nome: str) -> str:
    modelo = (DESTINO_LUA / "thais_cyclops_selector.lua").read_text(encoding="utf-8")
    # O seletor precisa do catalogo DELE, nao do dos ciclopes. O modelo carrega
    # catalogo.lua quando HuntInstances nao existe -- mas ele existia, sem esta
    # hunt dentro, e o template vinha nil. O Action:position() e' registrado na
    # carga, entao o erro derruba o registro inteiro: sete seletores morreram
    # assim e so' duas hunts subiram.
    modelo = modelo.replace(
        """if not HuntInstances then
	dofile(DATA_DIRECTORY .. "/scripts/custom/hunt_instances/catalogo.lua")
end""",
        f"""if not (HuntInstances and HuntInstances.{chave}) then
	dofile(DATA_DIRECTORY .. "/scripts/custom/hunt_instances/catalogo_{slug}.lua")
end""")
    texto = modelo.replace("HuntInstances.thaisCyclops", f"HuntInstances.{chave}")
    texto = texto.replace("-- Seletor de entrada:",
                          f"-- Seletor de entrada de {nome}.\n"
                          "-- GERADO POR tools/mapa/gerar_instancia.py a partir do de Thais.\n"
                          "-- Seletor de entrada:")
    return texto


def gerar_catalogo(doc: dict, slug: str, chave: str, org: dict, larg: int, alt: int,
                   andares: list[int], slots: list[tuple[int, int]],
                   entradas: list[tuple[int, int, int]], aid: int,
                   jogador: list[tuple[int, int, int]], fronteira: dict,
                   marcados: list[int]) -> str:
    o = doc["obelisco"]
    ret = jogador[0] if jogador else (o["x"], o["y"] + 2, o["z"])
    L = [
        f"-- {doc['nome']} -- hunt revisada #{doc['revisada']['numero']}.",
        "-- GERADO POR tools/mapa/gerar_instancia.py. Os numeros vem do JSON",
        "-- conferido no mapeador, nao de estimativa.",
        "",
        "HuntInstances = HuntInstances or {}",
        "",
        f"HuntInstances.{chave} = {{",
        f'\tslug = "{slug}",',
        f'\tnome = "{doc["nome"]}",',
        "\tenabled = true,",
        "",
        "\ttemplate = {",
        f'\t\tcaminho = "/world/hunt_instances/{slug}_instance.otbm",',
        f"\t\torigem = Position({org['x']}, {org['y']}, 0),",
        f"\t\tlargura = {larg},",
        f"\t\taltura = {alt},",
        f"\t\tandares = {{ {', '.join(str(z) for z in andares)} }},",
        "\t},",
        "",
        "\t-- A hunt dentro do recorte. O resto e' margem, que existe para ser",
        "\t-- VISTA: o beforeLeave para o jogador na borda da hunt, e o que ele",
        "\t-- enxerga alem disso e' terreno de verdade, nao o vazio.",
        f"\tmargemRecorte = {MARGEM},",
        f"\tfronteira = {{ x0 = {fronteira['x0']}, y0 = {fronteira['y0']}, "
        f"x1 = {fronteira['x1']}, y1 = {fronteira['y1']} }},",
        "",
        "\t-- Os andares que SAO a hunt. O recorte tem mais: inclui o andar por",
        "\t-- onde se sai, para a escada existir. Pisar nele e' sair da hunt, e a",
        "\t-- zona nao o cobre justamente para o dialogo disparar la'.",
        f"\tandaresHunt = {{ {', '.join(str(z) for z in marcados)} }},",
        "",
        "\tslotOrigens = {",
    ]
    for sx, sy in slots:
        L.append(f"\t\tPosition({sx}, {sy}, 0),")
    L += [
        "\t},",
        "",
        "\t-- Onde o jogador aparece, relativo ao slot. Sai do `inicio` marcado",
        "\t-- no mapeador; os vizinhos foram conferidos como pisaveis.",
        "\tentradasRelativas = {",
    ]
    for ex, ey, ez in entradas:
        L.append(f"\t\t{{ x = {ex}, y = {ey}, z = {ez} }},")
    L += [
        "\t},",
        "",
        "\tseletor = {",
        f"\t\tposicao = Position({o['x']}, {o['y']}, {o['z']}),",
        "\t\titemId = 2199,",
        f"\t\tactionId = {aid},",
        "\t},",
        "",
        "\t-- Tiles onde os membros da party sobem para consentir: presenca",
        "\t-- fisica e' o consentimento, porque a ModalWindow morre ao andar.",
        "\tplayerPositions = {",
    ]
    for px, py, pz in jogador:
        L.append(f"\t\tPosition({px}, {py}, {pz}),")
    L += [
        "\t},",
        "",
        f"\tretornoGlobal = Position({ret[0]}, {ret[1]}, {ret[2]}),",
        f"\tretornoEmergencia = {TEMPLO_THAIS},   -- revisar: nao e' o templo mais proximo",
        "\traioRetorno = 2,",
        "",
        "\tmaximoSlots = 6,",
        "",
        "\tduracaoMaximaMinutos = 180,",
        "\tgraceVazioMinutos = 3,",
        "\tcooldownMinutos = 5,",
        "",
        "\tpermiteSolo = true,",
        "\tpermiteParty = true,",
        "\tminimoMembrosParty = 2,",
        "\tmaximoMembros = 5,",
        "\tmesmoAndar = true,",
        "\texigeTodosOsMembros = true,",
        "",
        "\tpermiteEntradaTardia = false,",
        "\tpermiteReentrada = false,",
        "\tmantemAposSaidaDoLider = true,",
        "\tmantemAposPartyDesfeita = true,",
        "",
        "\tmultiplicadorExp = 1.0,",
        "\tmultiplicadorLoot = 1.0,",
        "\tmultiplicadorSpawn = 1.0,",
        "",
        "\tskullsBloqueadas = { SKULL_WHITE, SKULL_RED, SKULL_BLACK },",
        "\tbloqueiaComPvpLock = true,",
        "\tremoveItensNoChaoAoLimpar = true,",
        "}",
        "",
    ]
    return "\n".join(L)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("mapa")
    p.add_argument("--hunt", required=True, help="JSON de hunts_revisadas/")
    p.add_argument("--slug", help="padrao: do nome da hunt")
    p.add_argument("--seco", action="store_true", help="so confere, nao grava")
    args = p.parse_args()

    doc = json.loads(Path(args.hunt).read_text(encoding="utf-8"))
    numero = doc["revisada"]["numero"]
    slug = args.slug or slugificar(doc["nome"])
    chave = camel(slug)

    if not doc.get("obelisco") or not doc.get("inicio"):
        print("FALHA: hunt sem obelisco ou sem inicio")
        return 1

    xs = [c["x0"] for c in doc["bbox"].values()] + [c["x1"] for c in doc["bbox"].values()]
    ys = [c["y0"] for c in doc["bbox"].values()] + [c["y1"] for c in doc["bbox"].values()]
    hx0, hx1, hy0, hy1 = min(xs), max(xs), min(ys), max(ys)
    x0, y0 = hx0 - MARGEM, hy0 - MARGEM
    x1, y1 = hx1 + MARGEM, hy1 + MARGEM
    larg, alt = x1 - x0 + 1, y1 - y0 + 1

    # Os andares vao dos marcados ATE' o do obelisco. Sair da hunt e' subir ou
    # descer para o andar de onde se entrou; sem ele no recorte a escada some e
    # o jogador fica preso -- foi o que aconteceu em Lower Roshamuul, cortada
    # so' nos andares 5 e 6 com a saida no 7.
    marcados = sorted(int(z) for z in doc["limites"])
    zo = doc["obelisco"]["z"]
    andares = list(range(min(marcados[0], zo), max(marcados[-1], zo) + 1))
    org = {"x": x0, "y": y0}
    fronteira = {"x0": hx0 - x0, "y0": hy0 - y0, "x1": hx1 - x0, "y1": hy1 - y0}

    print(f"#{numero} {doc['nome']}  ->  {slug}")
    print(f"  hunt   : x {hx0}-{hx1}  y {hy0}-{hy1}  andares marcados {marcados}")
    print(f"  recorte: x {x0}-{x1}  y {y0}-{y1}  z {andares[0]}-{andares[-1]}"
          f"  ({larg}x{alt}, {len(andares)} andares, margem {MARGEM})")

    print("  abrindo o mapa...", end=" ", flush=True)
    mundo = Mundo(Path(args.mapa))
    print("ok")

    # --- faixa dos slots ---
    banda_y = BANDA_Y_BASE + BANDA_Y_PASSO * numero
    passo_x = 512 if larg <= 448 else larg + 64
    slots = [(SLOT_X_BASE + passo_x * i, banda_y) for i in range(6)]
    for sx, sy in slots:
        livre, motivo = faixa_livre(mundo, sx, sy, larg, alt, andares)
        if not livre:
            print(f"  FALHA: slot ({sx},{sy}) nao esta livre -- {motivo}")
            return 1
    print(f"  slots  : y {banda_y}, x {slots[0][0]}..{slots[-1][0]} "
          f"(passo {passo_x}) -- todos livres")

    # --- entradas ---
    i = doc["inicio"]
    perto = mundo.perto_andavel(i["x"], i["y"], i["z"], 5)
    if not perto:
        print(f"  FALHA: o inicio ({i['x']},{i['y']},{i['z']}) nao e' pisavel")
        return 1
    entradas = [(px - x0, py - y0, pz) for px, py, pz in perto]
    print(f"  entrada: {len(entradas)} tile(s) a partir de "
          f"({i['x']},{i['y']},{i['z']}) -> relativo {entradas[0]}")

    # --- obelisco e tiles de consentimento ---
    o = doc["obelisco"]
    jogador = [t for t in mundo.perto_andavel(o["x"], o["y"], o["z"], 6)
               if (t[0], t[1]) != (o["x"], o["y"])][:5]
    if len(jogador) < 2:
        print(f"  FALHA: so' {len(jogador)} tile(s) pisavel(is) junto ao obelisco")
        return 1
    print(f"  obelisco: ({o['x']},{o['y']},{o['z']}), "
          f"{len(jogador)} tile(s) para a party")

    if args.seco:
        print("  (seco: nada gravado)")
        return 0

    # --- recorte do mapa ---
    DESTINO_MAPA.mkdir(parents=True, exist_ok=True)
    otbm = DESTINO_MAPA / f"{slug}_instance.otbm"
    r = subprocess.run(
        [sys.executable, str(AQUI / "recortar.py"), args.mapa, str(otbm),
         str(x0), str(y0), str(x1), str(y1), str(andares[0]), str(andares[-1])],
        capture_output=True, text=True)
    if r.returncode != 0 or not otbm.exists():
        print(f"  FALHA no recorte:\n{r.stdout}\n{r.stderr}")
        return 1
    for linha in r.stdout.splitlines():
        if any(k in linha for k in ("tiles gravados", "itens removidos",
                                    "tiles de casa", "AVISO")):
            print("  " + linha.strip())
    print(f"  mapa   : {otbm.name} ({otbm.stat().st_size // 1024} KB)")

    # --- spawns, seletor, catalogo ---
    lua, n = gerar_spawns(doc, slug, org)
    (DESTINO_LUA / f"spawns_{slug}.lua").write_text(lua, encoding="utf-8")
    print(f"  spawns : spawns_{slug}.lua ({n} pontos)")

    (DESTINO_LUA / f"{slug}_selector.lua").write_text(
        gerar_selector(slug, chave, doc["nome"]), encoding="utf-8")
    print(f"  seletor: {slug}_selector.lua")

    trecho = gerar_catalogo(doc, slug, chave, org, larg, alt, andares, slots,
                            entradas, ACTION_ID_BASE + numero, jogador, fronteira,
                            marcados)
    destino = DESTINO_LUA / f"catalogo_{slug}.lua"
    destino.write_text(trecho, encoding="utf-8")
    print(f"  catalogo: {destino.name}  (actionId {ACTION_ID_BASE + numero})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
