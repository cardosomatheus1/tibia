"""Gera a lista de bosses que a instancia nunca deve fazer nascer.

    python tools/gerar_lista_bosses.py

Por que uma lista gerada, e nao so' a API do jogo: `MonsterType:bossRaceId()`
e `:isRewardBoss()` existem em Lua, mas 99 dos 348 bosses do datapack nao tem
nenhum dos dois preenchidos -- eles se identificam apenas por morarem em
monster/bosses/. Dois desses 99 apareceram nos contornos das nossas hunts
(Ancient Lion Knight e The Flaming Orchid), entao um portao so' com a API
deixaria justamente eles passarem.

Rode de novo quando o datapack mudar.
"""

from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
MONSTROS = RAIZ / "data-otservbr-global/monster"
SAIDA = (RAIZ / "data-otservbr-global/scripts/custom/hunt_instances"
         / "bosses_gerado.lua")

RE_NOME = re.compile(r'createMonsterType\(\s*"([^"]+)"')
RE_CAMPO = re.compile(r"bossRaceId\s*=\s*\d|isRewardBoss\s*=\s*true")


def coletar() -> dict[str, str]:
    """nome do monstro -> por que ele conta como boss."""
    achados: dict[str, str] = {}
    for arq in MONSTROS.rglob("*.lua"):
        texto = arq.read_text(encoding="utf-8", errors="replace")
        nome = RE_NOME.search(texto)
        if not nome:
            continue
        na_pasta = "bosses" in arq.parts
        tem_campo = bool(RE_CAMPO.search(texto))
        if na_pasta or tem_campo:
            achados[nome.group(1)] = ("pasta+campo" if na_pasta and tem_campo
                                      else "pasta" if na_pasta else "campo")
    return achados


def main() -> int:
    achados = coletar()
    so_pasta = sum(1 for v in achados.values() if v == "pasta")
    linhas = [
        "-- GERADO POR tools/gerar_lista_bosses.py -- NAO EDITE A MAO.",
        "--",
        "-- Nomes que a instancia nunca faz nascer. Boss em instancia privada",
        "-- e' farm infinito: o jogador controla quando abre e quando fecha, e o",
        "-- respawn passa a ser decisao dele, nao do servidor.",
        "--",
        f"-- {len(achados)} nomes; {so_pasta} deles NAO tem bossRaceId nem",
        "-- isRewardBoss e so' se reconhecem por morarem em monster/bosses/,",
        "-- que e' por isso que esta lista existe em vez de so' perguntar ao jogo.",
        "",
        "HuntInstanceBosses = {",
    ]
    for nome in sorted(achados):
        seguro = nome.replace("\\", "\\\\").replace('"', '\\"')
        linhas.append(f'\t["{seguro}"] = true,')
    linhas.append("}")
    linhas.append("")
    SAIDA.write_text("\n".join(linhas), encoding="utf-8")
    print(f"{len(achados)} bosses ({so_pasta} so' pela pasta) -> "
          f"{SAIDA.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
