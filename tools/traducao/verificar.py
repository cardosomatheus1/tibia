#!/usr/bin/env python3
"""Confere a saude da traducao — para o trabalho nao apodrecer calado.

O jeito de perder traducao nao e alguem apagar o arquivo. E o upstream
corrigir uma virgula numa frase: a chave deixa de bater, aquela linha volta
para o ingles e ninguem percebe. Com milhares de frases isso vai comendo o
trabalho aos poucos.

    python3 tools/traducao/verificar.py

Sai com codigo 1 quando tem algo para uma pessoa decidir, entao serve
direto num hook de commit ou na CI.
"""
from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from extrair import varrer   # noqa: E402
from gerar_dicionario import tolerante   # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--catalogo", default="tools/traducao/catalogo.json")
    p.add_argument("--pastas", nargs="*",
                   default=["data-otservbr-global/npc", "data/npclib"])
    p.add_argument("--parecidas", type=float, default=0.88,
                   help="quao parecido para sugerir que a frase so mudou")
    args = p.parse_args()

    cat = json.loads(Path(args.catalogo).read_text())
    textos_atuais, palavras_atuais, _ = varrer(args.pastas)

    traduzidos = {k: v for k, v in cat.get("textos", {}).items() if v.get("pt")}
    presentes = set(textos_atuais)

    # 1. o que esta traduzido e ainda casa exatamente
    casam = {k for k in traduzidos if k in presentes}

    # 2. o que casa so pela chave tolerante — funciona, mas o catalogo esta
    #    desatualizado e vale atualizar a chave
    por_tolerante = {}
    for k in presentes:
        por_tolerante.setdefault(tolerante(k), k)
    tolerados = {}
    for k in traduzidos:
        if k in casam:
            continue
        alvo = por_tolerante.get(tolerante(k))
        if alvo:
            tolerados[k] = alvo

    # 3. orfas: traduzido e nao existe mais. Pode ser frase removida ou
    #    frase que mudou de verdade — o parecido diz qual dos dois.
    orfas = [k for k in traduzidos if k not in casam and k not in tolerados]
    sem_traducao = [k for k in presentes if k not in traduzidos]
    sugestoes = []
    for k in orfas:
        perto = difflib.get_close_matches(k, sem_traducao, n=1, cutoff=args.parecidas)
        if perto:
            sugestoes.append((k, perto[0]))

    ditas = sum(textos_atuais.values())
    ditas_ok = sum(textos_atuais[k] for k in casam) + \
        sum(textos_atuais[v] for v in tolerados.values())

    print(f"frases no datapack: {len(presentes)}  ({ditas} ocorrencias)")
    print(f"  traduzidas e casando:  {len(casam)}")
    if tolerados:
        print(f"  casando so por tolerancia: {len(tolerados)}  "
              f"(funciona, mas atualize a chave)")
    print(f"  sem traducao:          {len(sem_traducao)}")
    print(f"  cobertura das falas ditas: {ditas_ok / ditas * 100:.1f}%" if ditas else "")

    if tolerados:
        print("\nchave desatualizada (a frase mudou de pontuacao/espaco):")
        for antiga, nova in list(tolerados.items())[:10]:
            print(f"  - {antiga[:64]}")
            print(f"  + {nova[:64]}")

    if sugestoes:
        print(f"\ntraducao orfa com frase parecida no lugar ({len(sugestoes)}):")
        print("  provavelmente o upstream editou o texto. Confira e mova o \"pt\".")
        for antiga, nova in sugestoes[:10]:
            print(f"  - {antiga[:70]}")
            print(f"  + {nova[:70]}")

    # 4. glossario: termo que devia ficar no original mas foi traduzido, e
    #    termo comum traduzido de dois jeitos diferentes pelo caminho
    glos = Path(args.catalogo).parent / "glossario.json"
    problemas_glos = []
    if glos.exists():
        g = json.loads(glos.read_text())
        intocaveis = [n for grupo in g["nao_traduzir"].values()
                      if isinstance(grupo, list) for n in grupo]
        for original, dado in cat.get("textos", {}).items():
            pt = dado.get("pt")
            if not pt:
                continue
            for nome in intocaveis:
                if nome in original and nome not in pt:
                    problemas_glos.append((nome, original))
                    break

    if problemas_glos:
        print(f"\nnome proprio que sumiu na traducao ({len(problemas_glos)}):")
        print("  esta no glossario como intocavel — o jogador vai procurar")
        print("  no mapa/item um nome que so existe no dialogo.")
        for nome, frase in problemas_glos[:8]:
            print(f"  {nome}: {frase[:60]}")

    # 5. palavra clicavel traduzida sem caminho de volta. E o erro mais
    #    grave que existe aqui: o jogador clica em {dicas}, o NPC nao
    #    entende, e a conversa vira beco sem saida.
    import re as _re
    entrada = {v["pt"].lower() for v in cat.get("palavras", {}).values() if v.get("pt")}
    entrada |= {v["pt"].lower() for v in cat.get("apelidos", {}).values() if v.get("pt")}
    originais = set(cat.get("palavras", {})) | set(cat.get("apelidos", {}))
    quebradas = []
    for original, dado in cat.get("textos", {}).items():
        pt = dado.get("pt")
        if not pt:
            continue
        for termo in _re.findall(r"\{([^}|]+)\}", pt):
            t = termo.strip().lower()
            if t and t not in entrada and t not in originais:
                quebradas.append((t, pt))
                break

    if quebradas:
        print(f"\npalavra clicavel sem caminho de volta ({len(quebradas)}):")
        print("  o jogador clica, o NPC nao entende, a conversa trava.")
        print("  ou traduza de volta no catalogo, ou deixe o termo no original.")
        for termo, frase in quebradas[:10]:
            print(f"  {{{termo}}}: {frase[:58]}")

    perdidas = [k for k in orfas if k not in dict(sugestoes)]
    if perdidas:
        print(f"\ntraducao orfa sem par ({len(perdidas)}): a frase sumiu do datapack.")
        print("  fica guardada no catalogo — se a frase voltar, volta a funcionar.")

    precisa_olhar = bool(tolerados or sugestoes or problemas_glos or quebradas)
    print("\n" + ("precisa de uma olhada." if precisa_olhar else "tudo em ordem."))
    return 1 if precisa_olhar else 0


if __name__ == "__main__":
    raise SystemExit(main())
