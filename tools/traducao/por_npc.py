#!/usr/bin/env python3
"""Mostra as falas de um NPC na ordem do arquivo, para traduzir por personagem.

Lore nao se traduz por frequencia. A fala de um NPC e uma conversa com voz
propria e termos que reaparecem; traduzir frases soltas de 300 NPCs
diferentes produz tres nomes diferentes para a mesma coisa. Aqui sai o
roteiro inteiro de um personagem, na ordem em que esta no arquivo.

    python3 tools/traducao/por_npc.py seymour
    python3 tools/traducao/por_npc.py --maiores 20
"""
from __future__ import annotations
import argparse, json, re, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from extrair import PADROES_TEXTO   # noqa: E402


def falas_do_arquivo(caminho: Path):
    """Na ordem do arquivo, sem repetir."""
    conteudo = caminho.read_text(errors="replace")
    achados = []
    for padrao in PADROES_TEXTO:
        for m in padrao.finditer(conteudo):
            achados.append((m.start(), m.group(2).strip()))
    vistos, saida = set(), []
    for _, t in sorted(achados):
        if len(t) > 1 and t not in vistos:
            vistos.add(t)
            saida.append(t)
    return saida


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("npc", nargs="?")
    p.add_argument("--catalogo", default="tools/traducao/catalogo.json")
    p.add_argument("--pasta", default="data-otservbr-global/npc")
    p.add_argument("--maiores", type=int, help="lista os N NPCs com mais texto pendente")
    args = p.parse_args()

    cat = json.loads(Path(args.catalogo).read_text())
    feito = {k for k, v in cat.get("textos", {}).items() if v.get("pt")}

    if args.maiores or not args.npc:
        pendente = Counter()
        for arq in sorted(Path(args.pasta).rglob("*.lua")):
            n = sum(len(t) for t in falas_do_arquivo(arq) if t not in feito)
            if n:
                pendente[arq.stem] = n
        for nome, n in pendente.most_common(args.maiores or 20):
            print(f"  {n:6d} chars  {nome}")
        return 0

    arq = Path(args.pasta) / f"{args.npc}.lua"
    if not arq.exists():
        achados = list(Path(args.pasta).rglob(f"*{args.npc}*.lua"))
        if not achados:
            raise SystemExit(f"nao achei npc '{args.npc}'")
        arq = achados[0]

    falas = falas_do_arquivo(arq)
    faltam = [t for t in falas if t not in feito]
    print(f"# {arq.stem}: {len(falas)} falas, {len(faltam)} pendentes")
    for t in faltam:
        print(t)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
