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
RE_PARTES = re.compile(r"[,;.]|\band\b", re.I)

# `\z` do Lua emenda a string na linha seguinte comendo o espaco em branco.
RE_EMENDA = re.compile(r"\\z\s*")

# Nome de lugar em Tibia e' Title Case ("Nightmare Isles", "Antrum of the
# Fallen"). O resto do Locations e' prosa em minuscula, e e' dai que vinha o
# estrago: guardar o pedaco inteiro criava chaves como "a single spawn in a
# tower", com as quais varias hunts casavam por substring e caiam todas no
# mesmo lugar. Entao so' o trecho em Title Case entra no indice.
# Os conectores podem vir em sequencia -- "Antrum of the Fallen" tem dois
# seguidos. Aceitar so' um cortava o nome em "Antrum" e a hunt deixava de casar.
RE_TRECHO = re.compile(
    r"\b[A-Z][\w'\-]*(?:\s+(?:(?:of|the|and|in|on|at|to|de|du|la|le)\s+)*"
    r"[A-Z][\w'\-]*)*")

# Palavras que comecam frase e viram "lugar" de mentira quando estao sozinhas.
SOZINHAS_RUINS = {
    "a", "all", "almost", "an", "another", "any", "around", "at", "below",
    "beneath", "between", "can", "close", "deep", "deeper", "few", "found",
    "here", "in", "inside", "it", "its", "just", "lot", "many", "mostly",
    "near", "none", "nowhere", "of", "on", "one", "only", "other", "outside",
    "over", "several", "single", "some", "somewhere", "the", "their", "there",
    "these", "they", "this", "to", "under", "unknown", "various", "way",
    "with", "within", "everywhere", "spawn", "spawns", "places", "place",
    "surroundings", "surface", "dungeon", "cave", "caves", "area", "areas",
    "tibia", "quest", "room", "tower", "camp", "city", "island", "islands",
}


def normalizar(texto: object) -> str:
    """Chave de comparacao: sem acento, sem pontuacao, minusculo.

    A planilha e o datapack escrevem o mesmo lugar de formas diferentes
    ("Ferumbras' Tower" x "Ferumbras Tower"), entao comparar cru erra muito.
    """
    s = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def lugares(texto_locations: str) -> list[str]:
    """Tira do texto do bestiario so' o que e' nome de lugar.

    "A few spawns in the Underground Glooth Factory, Glooth Factory, and
    Rathleton Sewers." -> Underground Glooth Factory, Glooth Factory,
    Rathleton Sewers. A prosa em volta e' descartada.
    """
    saida = []
    for parte in RE_PARTES.split(RE_EMENDA.sub(" ", texto_locations)):
        for trecho in RE_TRECHO.findall(parte):
            chave = normalizar(trecho)
            if len(chave) <= 3:
                continue
            # uma palavra so' precisa ser palavra de verdade, nao inicio de
            # frase ("All ...", "Several ...", "Deeper ...")
            if " " not in chave and chave in SOZINHAS_RUINS:
                continue
            # e nada pode ser feito so' de palavras genericas
            if all(p in SOZINHAS_RUINS for p in chave.split()):
                continue
            saida.append(chave)
    return saida


def indexar(pasta_monstros: Path) -> dict[str, set[str]]:
    """Le os .lua e devolve {local normalizado: {nomes de monstro}}."""
    indice: dict[str, set[str]] = defaultdict(set)
    for arq in pasta_monstros.rglob("*.lua"):
        texto = arq.read_text(encoding="utf-8", errors="replace")
        nome = RE_NOME.search(texto)
        loc = RE_LOC.search(texto)
        if not (nome and loc):
            continue
        for chave in lugares(loc.group(1)):
            indice[chave].add(nome.group(1))
    return dict(indice)


def casar(nome_hunt: str, indice: dict[str, set[str]]) -> tuple[str, set[str], str]:
    """Acha o local do bestiario que corresponde a uma hunt da planilha.

    So' devolve casamento forte. Nao achar e' resposta legitima e melhor do
    que chutar: um chute vira contorno no lugar errado, com os monstros
    errados, e parece resultado bom ate' alguem abrir e conferir.
    """
    chave = normalizar(nome_hunt)
    if not chave:
        return "", set(), "vazio"
    if chave in indice:
        return chave, indice[chave], "exato"

    # Nome contido, mas so' quando sobra pouco: a planilha diz "Ancient
    # Ancestorial Grounds" e o bestiario diz "Ancestorial Grounds". Sem a
    # exigencia de tamanho, "Crypt" casava com qualquer cripta do jogo.
    palavras = chave.split()
    candidatos = []
    for k in indice:
        pk = k.split()
        if not (_contem(pk, palavras) or _contem(palavras, pk)):
            continue
        menor, maior = sorted((len(pk), len(palavras)))
        if menor / maior >= 0.6:
            candidatos.append(k)
    if candidatos:
        melhor = max(candidatos, key=len)
        return melhor, indice[melhor], "contido"
    return "", set(), "sem"


def _contem(maior: list[str], menor: list[str]) -> bool:
    """menor aparece inteiro e em sequencia dentro de maior."""
    n = len(menor)
    return n > 0 and any(maior[i:i + n] == menor for i in range(len(maior) - n + 1))


if __name__ == "__main__":
    raiz = Path(__file__).resolve().parents[2]
    idx = indexar(raiz / "data-otservbr-global/monster")
    print(f"{len(idx)} locais no bestiario")
    for k in sorted(idx)[:8]:
        print(f"  {k}: {sorted(idx[k])[:4]}")
