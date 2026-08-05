"""Varre o que o achar_hunts.py produziu procurando resultado ruim.

Existe porque os defeitos apareceram olhando, um por um, no mapeador: uma hunt
de level 200+ cheia de Centipede e Flamingo, cinco hunts marcando o mesmo
pedaco de Roshamuul. Achar isso na mao nao escala para 146 -- e o proximo lote
teria os mesmos problemas em outras hunts.

Cada verificacao aqui nasceu de um erro real:

  sobreposicao   duas hunts no mesmo lugar. No jogo isso nao existe.
  monstro fraco  o contorno pegou area de bicho de level 10.
  vazio          area grande com pouco monstro: contorno pegou mato em volta.
  gigante        muito maior que as outras: quase sempre vazou para o vizinho.
  fora do nome   o local do bestiario nao parece com o nome da hunt.

    python auditar_hunts.py [--pasta hunts_automaticas]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from bestiario import normalizar  # noqa: E402


def carregar(pasta: Path) -> list[dict]:
    saida = []
    for arq in sorted(pasta.glob("hunt_*.json")):
        try:
            d = json.loads(arq.read_text(encoding="utf-8"))
        except ValueError:
            print(f"  !! {arq.name}: JSON invalido")
            continue
        d["_arquivo"] = arq.name
        d["_tiles"] = {z: {tuple(t) for t in lista} for z, lista in d["limites"].items()}
        saida.append(d)
    return saida


def mediana(v: list[int]) -> int:
    if not v:
        return 0
    v = sorted(v)
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) // 2


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--pasta", default=str(Path(__file__).parent / "hunts_automaticas"))
    p.add_argument("--exp-minima", type=int, default=1000)
    p.add_argument("--densidade-minima", type=float, default=0.006,
                   help="monstros por tile abaixo disso e' area vazia demais")
    args = p.parse_args()

    hunts = carregar(Path(args.pasta))
    print(f"{len(hunts)} hunts na pasta\n")
    problemas: dict[int, list[str]] = {}

    def anotar(h: dict, texto: str) -> None:
        problemas.setdefault(h["id"], []).append(texto)

    # 1. duas hunts no mesmo lugar
    for i, a in enumerate(hunts):
        ta = {(z, t) for z, s in a["_tiles"].items() for t in s}
        for b in hunts[i + 1:]:
            tb = {(z, t) for z, s in b["_tiles"].items() for t in s}
            comum = len(ta & tb)
            if comum and comum / min(len(ta), len(tb)) >= 0.3:
                pct = round(100 * comum / min(len(ta), len(tb)))
                anotar(a, f"sobrepoe {pct}% com [{b['id']}] {b['nome']}")
                anotar(b, f"sobrepoe {pct}% com [{a['id']}] {a['nome']}")

    # 2, 3, 4, 5
    tamanhos = sorted(sum(len(s) for s in h["_tiles"].values()) for h in hunts)
    if tamanhos:
        corte = tamanhos[int(len(tamanhos) * 0.9)] * 2
    for h in hunts:
        a = h.get("automatico", {})
        tiles = sum(len(s) for s in h["_tiles"].values())

        if a.get("expDentro", 0) < args.exp_minima:
            fracos = [n for n, _ in list(h["monstrosPorTipo"].items())[:3]]
            anotar(h, f"monstros fracos dentro (exp mediana {a.get('expDentro')}): "
                      f"{', '.join(fracos)}")

        dens = h["totalMonstros"] / tiles if tiles else 0
        if dens < args.densidade_minima:
            anotar(h, f"area vazia: {h['totalMonstros']} monstros em {tiles} tiles "
                      f"({dens:.4f}/tile)")

        if tamanhos and tiles > corte:
            anotar(h, f"gigante: {tiles} tiles (o dobro do percentil 90, {corte})")

        # o nome do bestiario deve parecer com o nome da hunt
        n1, n2 = set(normalizar(h["nome"]).split()), set(a.get("localBestiario", "").split())
        if n2 and not (n1 & n2):
            anotar(h, f"nome nao bate: hunt '{h['nome']}' x bestiario "
                      f"'{a.get('localBestiario')}'")

        if a.get("pureza", 100) < 50:
            anotar(h, f"pureza {a['pureza']}%: a maioria dos monstros dentro nao e' da hunt")

    if not problemas:
        print("nenhum problema encontrado")
        return 0

    print(f"{len(problemas)} hunts com problema:\n")
    por_id = {h["id"]: h for h in hunts}
    for hid in sorted(problemas, key=lambda k: -len(problemas[k])):
        print(f"  [{hid:3}] {por_id[hid]['nome']}")
        for t in problemas[hid]:
            print(f"         - {t}")
    print(f"\n{len(hunts) - len(problemas)} hunts passaram em tudo")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
