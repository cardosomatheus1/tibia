"""Indice de locais do bestiario: nome de area -> monstros que moram la.

De onde vem: cada arquivo de monstro do datapack traz `monster.Bestiary`, e
dentro dele o campo `Locations` com o texto que o jogo mostra no bestiario
("Antrum of the Fallen.", "Otherworld, Ferumbras' Tower."). Sao 749 monstros
com esse campo.

Por que isso importa: a planilha de hunts tem o NOME da area mas nao tem
monstro nem coordenada. O spawn (otservbr-monster.xml) tem coordenada e
monstro mas nao tem nome de area. Este indice e' a ponte entre os dois, e ela
ja vem pronta dentro do servidor -- nao precisa de wiki nem de pesquisa manual.
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from pathlib import Path

RE_NOME = re.compile(r'createMonsterType\(\s*"([^"]+)"')
RE_LOC = re.compile(r'Locations\s*=\s*"([^"]*)"', re.S)

# Separadores usados dentro de um mesmo Locations. O texto e' prosa do jogo,
# entao vem com virgula, ponto-e-virgula e " and ".
RE_PARTES = re.compile(r"[,;]|\band\b", re.I)

# Trechos que nao sao nome de lugar e so poluem o indice.
RUIDO = {
    "", "unknown", "none", "nowhere", "everywhere", "all over tibia",
    "various places", "surroundings", "the surroundings",
}


def normalizar(texto: object) -> str:
    """Chave de comparacao: sem acento, sem pontuacao, minusculo.

    A planilha e o datapack escrevem o mesmo lugar de formas diferentes
    ("Ferumbras' Tower" x "Ferumbras Tower"), entao comparar cru erra muito.
    """
    s = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def indexar(pasta_monstros: Path) -> dict[str, set[str]]:
    """Le os .lua e devolve {local normalizado: {nomes de monstro}}."""
    indice: dict[str, set[str]] = defaultdict(set)
    for arq in pasta_monstros.rglob("*.lua"):
        texto = arq.read_text(encoding="utf-8", errors="replace")
        nome = RE_NOME.search(texto)
        loc = RE_LOC.search(texto)
        if not (nome and loc):
            continue
        for parte in RE_PARTES.split(loc.group(1)):
            chave = normalizar(parte.strip(" .\n\t"))
            if len(chave) > 3 and chave not in RUIDO:
                indice[chave].add(nome.group(1))
    return dict(indice)


def casar(nome_hunt: str, indice: dict[str, set[str]]) -> tuple[str, set[str], str]:
    """Acha o local do bestiario que corresponde a uma hunt da planilha.

    Devolve (local encontrado, monstros, como casou). O "como casou" existe
    para poder revisar depois so o que veio de casamento fraco.
    """
    chave = normalizar(nome_hunt)
    if not chave:
        return "", set(), "vazio"
    if chave in indice:
        return chave, indice[chave], "exato"

    # Nome contido: a planilha diz "Ancient Ancestorial Grounds" e o bestiario
    # diz "Ancestorial Grounds" (ou o contrario). Fica com o mais especifico.
    contidos = [k for k in indice if chave in k or k in chave]
    if contidos:
        melhor = max(contidos, key=len)
        return melhor, indice[melhor], "contido"

    # Ultimo recurso: todas as palavras da hunt aparecem no local.
    palavras = set(chave.split())
    for k in sorted(indice, key=len):
        if palavras and palavras <= set(k.split()):
            return k, indice[k], "palavras"
    return "", set(), "sem"


if __name__ == "__main__":
    raiz = Path(__file__).resolve().parents[2]
    idx = indexar(raiz / "data-otservbr-global/monster")
    print(f"{len(idx)} locais no bestiario")
    for k in sorted(idx)[:8]:
        print(f"  {k}: {sorted(idx[k])[:4]}")
