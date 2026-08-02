#!/usr/bin/env python3
"""Importa os textos estaticos das quests para o catalogo de traducao.

O quest log e a quest tracker sao um sistema separado do dos NPCs (dados
em data-otservbr-global/lib/core/quests/catalog/*.lua, um arquivo por
quest), mas usam a mesma camada de idioma: Player.getQuestName/
getMissionName/getMissionDescription chamam Idioma.saida, que consulta o
mesmo dicionario textos do catalogo.json.

Como os arquivos de quest misturam Lua de verdade com codigo do jogo
(Storage.Quest.*, configManager etc.) e nao dao pra varrer com regex com
seguranca, a extracao roda o Lua de verdade (extrair_quests.lua, com
Storage/configManager dublados) e despeja nome da quest, nome de cada
missao e description/states quando sao string fixa. Casos description/
states que sao function(player) (valor dinamico no meio do texto) ficam
de fora daqui — vao para QuestsDinamico em idioma_quests.lua, a mao.

    python3 tools/traducao/importar_quests.py
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

FALLBACK_SEM_MISSAO = "An error has occurred, please contact a gamemaster."


def rodar_extrator(lua_bin: str, script: str) -> list[dict]:
    saida = subprocess.run([lua_bin, script], capture_output=True, text=True, check=True)
    return json.loads(saida.stdout)


def registrar(textos: dict, texto: str, origem: str) -> None:
    if len(texto) <= 1:
        return
    entrada = textos.setdefault(texto, {"pt": "", "n": 0})
    entrada["n"] = entrada.get("n", 0) + 1
    origens = entrada.setdefault("npc", [])
    if origem not in origens:
        origens.append(origem)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--catalogo", default="tools/traducao/catalogo.json")
    p.add_argument("--extrator", default="tools/traducao/extrair_quests.lua")
    p.add_argument("--lua", default="lua5.4")
    args = p.parse_args()

    cat = json.loads(Path(args.catalogo).read_text())
    textos = cat.setdefault("textos", {})

    antes = len(textos)
    quests = rodar_extrator(args.lua, args.extrator)

    n_dinamico = 0
    for q in quests:
        origem = "quest:" + Path(q["file"]).stem
        registrar(textos, q["name"], origem)
        for m in q["missions"]:
            registrar(textos, m["name"], origem)
            if "description" in m:
                registrar(textos, m["description"], origem)
            elif m.get("description_is_function"):
                n_dinamico += 1
            for s in m.get("states", []):
                if "text" in s:
                    registrar(textos, s["text"], origem)
                elif s.get("is_function"):
                    n_dinamico += 1

    registrar(textos, FALLBACK_SEM_MISSAO, "quest:_sistema")

    Path(args.catalogo).write_text(json.dumps(cat, indent=1, ensure_ascii=False) + "\n")
    print(f"{len(quests)} quests processadas")
    print(f"{len(textos) - antes} chaves novas no catalogo (total agora: {len(textos)})")
    print(f"{n_dinamico} description/states dinamicos (function) ficaram de fora — tratar em QuestsDinamico")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
