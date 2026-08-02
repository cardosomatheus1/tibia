#!/usr/bin/env python3
"""Lista as falas pendentes de uma ou mais quests, na ordem em que aparecem.

    python3 tools/traducao/por_quest.py 001_the_queen_of_the_banshees
    python3 tools/traducao/por_quest.py 001 002 003
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("quests", nargs="+", help="prefixo ou nome do arquivo da quest")
    p.add_argument("--catalogo", default="tools/traducao/catalogo.json")
    p.add_argument("--extrator", default="tools/traducao/extrair_quests.lua")
    p.add_argument("--lua", default="lua5.4")
    args = p.parse_args()

    cat = json.loads(Path(args.catalogo).read_text())
    feito = {k for k, v in cat.get("textos", {}).items() if v.get("pt")}

    saida = subprocess.run([args.lua, args.extrator], capture_output=True, text=True, check=True)
    quests = json.loads(saida.stdout)

    for q in quests:
        stem = Path(q["file"]).stem
        if not any(stem.startswith(pref) or pref in stem for pref in args.quests):
            continue
        falas = [q["name"]]
        for m in q["missions"]:
            falas.append(m["name"])
            if "description" in m:
                falas.append(m["description"])
            for s in m.get("states", []):
                if "text" in s:
                    falas.append(s["text"])
        falas = [f for f in falas if len(f) > 1]
        pendentes = [f for f in falas if f not in feito]
        print(f"### {stem}  ({q['name']})")
        print(f"# {len(falas)} falas, {len(pendentes)} pendentes")
        for idx, m in enumerate(q["missions"], 1):
            tags = []
            if m.get("description_is_function"):
                tags.append("description=FUNCTION")
            n_func_states = sum(1 for s in m.get("states", []) if s.get("is_function"))
            if n_func_states:
                tags.append(f"{n_func_states} state(s)=FUNCTION")
            if tags:
                print(f"  -- missao {idx} ({m['name']}): {', '.join(tags)}")
        print()
        for f in pendentes:
            print(f)
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
