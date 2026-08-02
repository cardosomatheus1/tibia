#!/usr/bin/env python3
"""Progresso da traducao do quest log, por quest.

Mesma logica do progresso.py dos NPCs: a unidade de trabalho e a quest
inteira (nome da quest + nome de cada missao + description/states),
nunca deixar uma pela metade. Os casos description/states que sao
function (valor dinamico no meio do texto) contam à parte, porque nao
tem uma chave de texto simples no catalogo — vivem em QuestsDinamico
dentro de idioma_quests.lua.

    python3 tools/traducao/progresso_quests.py
    python3 tools/traducao/progresso_quests.py --quest 001_the_queen_of_the_banshees
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path


def rodar_extrator(lua_bin: str, script: str) -> list[dict]:
    saida = subprocess.run([lua_bin, script], capture_output=True, text=True, check=True)
    return json.loads(saida.stdout)


def falas_estaticas(quest: dict) -> list[str]:
    falas = [quest["name"]]
    for m in quest["missions"]:
        falas.append(m["name"])
        if "description" in m:
            falas.append(m["description"])
        for s in m.get("states", []):
            if "text" in s:
                falas.append(s["text"])
    return falas


def dinamicos_da_quest(quest: dict) -> int:
    n = 0
    for m in quest["missions"]:
        if m.get("description_is_function"):
            n += 1
        for s in m.get("states", []):
            if s.get("is_function"):
                n += 1
    return n


def dinamicos_portados(quest_id: int, arquivo_hook: Path) -> set[tuple]:
    """Le QuestsDinamico[questId] = { [missionId] = {...} } do idioma_quests.lua
    a mao seria fragil; em vez disso, so contamos quantos ja existem via
    uma marcacao simples: procurar `QuestsDinamico[<id>]` no arquivo.
    Retorna o numero de blocos `= {` dentro daquele questId (aproximado,
    suficiente pra acompanhar progresso, nao para validar sintaxe)."""
    texto = arquivo_hook.read_text()
    m = re.search(rf"QuestsDinamico\[{quest_id}\]\s*=\s*\{{", texto)
    if not m:
        return 0
    # conta quantas vezes aparece "description = function" ou "\[%d+\] = function"
    # dentro do bloco daquele questId ate o proximo "QuestsDinamico[" ou fim.
    resto = texto[m.end():]
    prox = resto.find("\nQuestsDinamico[")
    bloco = resto if prox == -1 else resto[:prox]
    return bloco.count("function(player)")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--catalogo", default="tools/traducao/catalogo.json")
    p.add_argument("--extrator", default="tools/traducao/extrair_quests.lua")
    p.add_argument("--hook", default="data/npclib/npc_system/idioma_quests.lua")
    p.add_argument("--lua", default="lua5.4")
    p.add_argument("--quest")
    args = p.parse_args()

    cat = json.loads(Path(args.catalogo).read_text())
    feito = {k for k, v in cat.get("textos", {}).items() if v.get("pt")}
    quests = rodar_extrator(args.lua, args.extrator)
    hook_path = Path(args.hook)

    linhas = []
    tot_ok = tot_falas = tot_dinamico = tot_dinamico_ok = 0
    for idx, q in enumerate(quests, start=1):
        nome_arquivo = Path(q["file"]).stem
        falas = falas_estaticas(q)
        prontas = sum(1 for f in falas if f in feito)
        din_total = dinamicos_da_quest(q)
        din_ok = dinamicos_portados(idx, hook_path) if din_total else 0
        din_ok = min(din_ok, din_total)
        linhas.append((idx, nome_arquivo, q["name"], prontas, len(falas), din_ok, din_total))
        tot_ok += prontas
        tot_falas += len(falas)
        tot_dinamico += din_total
        tot_dinamico_ok += din_ok

    if args.quest:
        linhas = [l for l in linhas if args.quest in l[1]]

    for idx, arq, nome, ok, tot, din_ok, din_tot in linhas:
        extra = f"  +{din_ok}/{din_tot} dinamico" if din_tot else ""
        marca = "OK  " if ok == tot and din_ok == din_tot else ("meio" if ok else "    ")
        print(f"{marca} {idx:3d}  {ok:4d}/{tot:<4d}  {arq}{extra}")

    if not args.quest:
        pct = tot_ok / tot_falas * 100 if tot_falas else 0
        pct_din = tot_dinamico_ok / tot_dinamico * 100 if tot_dinamico else 100
        print()
        print(f"estatico: {tot_ok}/{tot_falas} ({pct:.1f}%)   dinamico: {tot_dinamico_ok}/{tot_dinamico} ({pct_din:.1f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
