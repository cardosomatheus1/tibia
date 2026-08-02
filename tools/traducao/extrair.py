#!/usr/bin/env python3
"""Extrai as falas e as palavras-chave dos NPCs para um catalogo de traducao.

Varre `data-otservbr-global/npc/**/*.lua` e a `data/npclib/`, junta tudo
num JSON e conta quantas vezes cada texto aparece. A contagem importa: a
cauda e longa (traduzir metade das falas ditas exige ~1000 textos), entao
da pra atacar por ordem de impacto em vez de por ordem alfabetica.

    python3 tools/traducao/extrair.py --saida tools/traducao/catalogo.json

Rodar de novo **preserva o que ja foi traduzido**: o catalogo antigo e
lido e so entram as chaves novas. Texto que sumiu do datapack e marcado
como `obsoleto` em vez de apagado.

O formato e simples de editar a mao:

    {
      "textos":  { "Good bye.": {"pt": "Ate mais.", "n": 66} },
      "palavras": { "trade": {"pt": "negociar", "n": 31} }
    }
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

# textos que o NPC fala
PADROES_TEXTO = [
    re.compile(r"""(?:text|message|msg)\s*=\s*(['"])(.+?)\1""", re.S),
    re.compile(r"""npcHandler:say\(\s*(['"])(.+?)\1""", re.S),
    re.compile(r"""setMessage\(\s*[A-Z_]+\s*,\s*(['"])(.+?)\1""", re.S),
    re.compile(r"""npc:talk\(\s*[^,]+,\s*(['"])(.+?)\1""", re.S),
    # as respostas padrao de todo NPC, na tabela do npc_handler:
    #   [MESSAGE_GREET] = "..."
    re.compile(r"""\[MESSAGE_[A-Z_]+\]\s*=\s*(['"])(.+?)\1""", re.S),
]
# palavras que o jogador digita
PADRAO_CHAVE = re.compile(r"""addKeyword\(\s*\{([^}]*)\}""", re.S)
PADRAO_ASPAS = re.compile(r"""['"]([^'"]+)['"]""")
# tambem conta o que aparece entre chaves nas falas: e o que o client deixa
# clicavel, entao precisa de traducao e de volta pela normalizacao
PADRAO_CHAVES_NO_TEXTO = re.compile(r"\{([^}|]+)\}")


def varrer(pastas) -> tuple[Counter, Counter, dict]:
    """Devolve (textos, palavras, quem_fala).

    `quem_fala` guarda de quais NPCs cada frase veio. Sem isso a traducao
    fica as cegas: a mesma frase muda de tom conforme quem diz, e sem saber
    o falante da pra escolher a palavra errada com facilidade.
    """
    textos, palavras, falantes = Counter(), Counter(), {}
    for pasta in pastas:
        p = Path(pasta)
        if not p.exists():
            continue
        for arquivo in sorted(p.rglob("*.lua")):
            conteudo = arquivo.read_text(errors="replace")
            for padrao in PADROES_TEXTO:
                for _, texto in padrao.findall(conteudo):
                    texto = texto.strip()
                    if len(texto) > 1:
                        textos[texto] += 1
                        falantes.setdefault(texto, set()).add(arquivo.stem)
                        for dentro in PADRAO_CHAVES_NO_TEXTO.findall(texto):
                            palavras[dentro.strip().lower()] += 1
            for grupo in PADRAO_CHAVE.findall(conteudo):
                for palavra in PADRAO_ASPAS.findall(grupo):
                    palavras[palavra.strip().lower()] += 1
    return textos, palavras, falantes


def juntar(antigo: dict, achados: Counter, falantes: dict | None = None) -> tuple[dict, int, int]:
    novo, entram, somem = {}, 0, 0
    for chave, n in achados.most_common():
        anterior = antigo.get(chave, {})
        if not anterior:
            entram += 1
        item = {"pt": anterior.get("pt", ""), "n": n}
        if falantes and chave in falantes:
            quem = sorted(falantes[chave])
            item["npc"] = quem if len(quem) <= 6 else quem[:6] + [f"+{len(quem) - 6}"]
        novo[chave] = item
    for chave, dado in antigo.items():
        if chave not in novo and dado.get("pt"):
            novo[chave] = {**dado, "obsoleto": True}
            somem += 1
    return novo, entram, somem


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--saida", default="tools/traducao/catalogo.json")
    p.add_argument("--pastas", nargs="*",
                   default=["data-otservbr-global/npc", "data/npclib"])
    args = p.parse_args()

    saida = Path(args.saida)
    antigo = json.loads(saida.read_text()) if saida.exists() else {}

    textos, palavras, falantes = varrer(args.pastas)
    cat_textos, novos_t, velhos_t = juntar(antigo.get("textos", {}), textos, falantes)
    cat_palavras, novos_p, velhos_p = juntar(antigo.get("palavras", {}), palavras)

    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps({"textos": cat_textos, "palavras": cat_palavras,
                                 "apelidos": antigo.get("apelidos", {})},
                                indent=1, ensure_ascii=False) + "\n")

    feitos_t = sum(1 for v in cat_textos.values() if v.get("pt"))
    feitos_p = sum(1 for v in cat_palavras.values() if v.get("pt"))
    ditas = sum(v["n"] for v in cat_textos.values() if not v.get("obsoleto"))
    ditas_ok = sum(v["n"] for v in cat_textos.values()
                   if v.get("pt") and not v.get("obsoleto"))

    print(f"catalogo -> {saida}")
    print(f"  textos:   {feitos_t}/{len(cat_textos)} traduzidos"
          f"  (+{novos_t} novos, {velhos_t} obsoletos)")
    print(f"  palavras: {feitos_p}/{len(cat_palavras)} traduzidas"
          f"  (+{novos_p} novas, {velhos_p} obsoletas)")
    if ditas:
        print(f"  cobertura das falas ditas: {ditas_ok / ditas * 100:.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
