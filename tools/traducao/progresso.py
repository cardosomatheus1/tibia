#!/usr/bin/env python3
"""Progresso da traducao por cidade e por NPC — a metrica que importa.

Percentual global engana. Um NPC meio traduzido le pior que um NPC em
ingles: o jogador ve a frase de saudacao em portugues e a resposta em
ingles, e conclui que o servidor esta quebrado. E cidade meio traduzida
tem o mesmo efeito no passeio do jogador.

Por isso a unidade de trabalho e o **NPC inteiro**, e a ordem e **por
cidade**: com Rookgaard 100% pronta, quem comeca o jogo tem a experiencia
completa, mesmo que Thais nem tenha comecado.

    python3 tools/traducao/progresso.py            # resumo por cidade
    python3 tools/traducao/progresso.py --cidade rookgaard
    python3 tools/traducao/progresso.py --pela-metade   # os que estao pior
"""
from __future__ import annotations
import argparse, json, re, sys, xml.etree.ElementTree as ET
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from por_npc import falas_do_arquivo   # noqa: E402

# centro aproximado de cada cidade, para dizer a que cidade um NPC pertence
CIDADES = {
    "rookgaard": (32097, 32219, 7), "dawnport": (32083, 31905, 7),
    "thais": (32369, 32241, 7), "carlin": (32360, 31782, 7),
    "ab_dendriel": (32732, 31634, 7), "kazordoon": (32649, 31925, 11),
    "venore": (32957, 32076, 7), "edron": (33217, 31814, 6),
    "darashia": (33213, 32454, 7), "ankrahmun": (33194, 32853, 8),
    "port_hope": (32595, 32744, 7), "liberty_bay": (32317, 32826, 7),
    "svargrond": (32212, 31132, 7), "yalahar": (32787, 31276, 7),
    "farmine": (33023, 31521, 11), "gray_beach": (33447, 31323, 9),
    "krailos": (33657, 31665, 8), "issavi": (33921, 31477, 6),
}


def cidade_de(x, y, z):
    melhor, dist = "outros", 10 ** 9
    for nome, (cx, cy, cz) in CIDADES.items():
        d = abs(x - cx) + abs(y - cy) + abs(z - cz) * 40
        if d < dist:
            melhor, dist = nome, d
    return melhor if dist < 500 else "outros"


def onde_moram(xml_path):
    """nome do npc (arquivo) -> cidade, pela posicao onde ele nasce."""
    onde = {}
    for grupo in ET.parse(xml_path).getroot():
        try:
            cx = int(grupo.get("centerx")); cy = int(grupo.get("centery"))
            cz = int(grupo.get("centerz"))
        except (TypeError, ValueError):
            continue
        for npc in grupo:
            nome = (npc.get("name") or "").strip().lower()
            if nome:
                onde[re.sub(r"[^a-z0-9]+", "_", nome).strip("_")] = cidade_de(cx, cy, cz)
    return onde


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--catalogo", default="tools/traducao/catalogo.json")
    p.add_argument("--pasta", default="data-otservbr-global/npc")
    p.add_argument("--xml", default="data-otservbr-global/world/otservbr-npc.xml")
    p.add_argument("--cidade")
    p.add_argument("--pela-metade", action="store_true")
    args = p.parse_args()

    feito = {k for k, v in json.loads(Path(args.catalogo).read_text())
             .get("textos", {}).items() if v.get("pt")}
    onde = onde_moram(args.xml) if Path(args.xml).exists() else {}

    npcs = []
    for arq in sorted(Path(args.pasta).rglob("*.lua")):
        falas = falas_do_arquivo(arq)
        if not falas:
            continue
        prontas = sum(1 for t in falas if t in feito)
        npcs.append((onde.get(arq.stem, "outros"), arq.stem, prontas, len(falas)))

    if args.pela_metade:
        meio = [n for n in npcs if 0 < n[2] < n[3]]
        meio.sort(key=lambda n: -(n[2] / n[3]))
        print(f"NPCs pela metade — a pior leitura possivel ({len(meio)}):")
        for cid, nome, ok, tot in meio[:25]:
            print(f"  {ok:3d}/{tot:3d}  {nome} ({cid})")
        return 1 if meio else 0

    if args.cidade:
        sel = [n for n in npcs if n[0] == args.cidade]
        sel.sort(key=lambda n: (n[2] == n[3], -(n[3] - n[2])))
        print(f"{args.cidade}: {len(sel)} NPCs")
        for cid, nome, ok, tot in sel:
            marca = "OK " if ok == tot else ("meio" if ok else "   ")
            print(f"  {marca} {ok:3d}/{tot:3d}  {nome}")
        return 0

    print(f"{'cidade':<14} {'NPCs':>5} {'prontos':>8} {'meio':>5} {'falas':>7} {'%':>6}")
    agreg = {}
    for cid, nome, ok, tot in npcs:
        a = agreg.setdefault(cid, [0, 0, 0, 0, 0])
        a[0] += 1
        a[1] += 1 if ok == tot else 0
        a[2] += 1 if 0 < ok < tot else 0
        a[3] += tot
        a[4] += ok
    for cid, a in sorted(agreg.items(), key=lambda kv: -kv[1][3]):
        print(f"{cid:<14} {a[0]:>5} {a[1]:>8} {a[2]:>5} {a[3]:>7} {a[4]/a[3]*100:>5.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
