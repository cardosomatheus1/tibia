#!/usr/bin/env python3
"""Gera o manifest do updater do otclient (mehah) e a pasta de arquivos servida.

O client tem um updater embutido (modules/updater): ao abrir, ele manda um POST
para Services.updater e recebe um JSON com a lista de arquivos e o CRC32 de cada
um. Ele compara com o que tem localmente e baixa so o que difere -- nao o pacote
inteiro. Assim, atualizar o client e' copiar arquivos no servidor; o jogador
recebe no proximo login.

Formato do JSON de resposta (visto em modules/updater/updater.lua):

    {
      "url":   "http://.../files/",          # base de download
      "files": { "modules/x/x.lua": "crc32", ... },
      "binary": { "file": "otclient.exe", "checksum": "crc32", "url": "..." },
      "keepFiles": false
    }

O checksum e' CRC32 em hex minusculo SEM zero a esquerda -- o client usa
stdext::dec_to_hex, que chama std::to_chars(16) e nao preenche. Por isso aqui e'
format(crc, "x") e nunca "%08x": um "%08x" faria todo checksum que comeca com
zero nunca casar, e o jogador baixaria esses arquivos em todo login.

As chaves de `files` levam BARRA INICIAL ("/modules/x.lua") -- e' o formato que
o g_resources.filesChecksums() gera. Por isso a --url NAO deve terminar em
barra: o updater faz `url .. file`, e "http://.../files" + "/modules/x.lua" junta
sem a barra dupla que um servidor HTTP poderia recusar.

O que NAO entra no manifest, de proposito:

  data/things/  -> os assets da 15.25 (170+ MB). Vem no instalador uma vez; o
                   updater nao deve reenviar isso a cada correcao de codigo.
  data/sounds/  -> mesma razao.
  *.otmm        -> o minimapa. O client sobrescreve /minimap.otmm ao explorar,
                   entao o checksum de cada jogador diverge; incluir aqui faria
                   todo mundo rebaixar o mapa base a cada login.
  *.log, *.dmp  -> lixo de runtime.
  otclient.*    -> o binario vai no campo `binary`, nao em `files`.

Uso (a partir da raiz do repositorio):

    python3 tools/updater/gerar_manifest.py --client C:/otclient-mehah \\
        --url http://rhapsodyyy.duckdns.org:8090/files/ \\
        --saida tools/updater/publicado
"""
import argparse
import json
import shutil
import sys
import zlib
from pathlib import Path

# Diretorios e arquivos que ficam fora do updater (ver docstring).
PASTAS_IGNORADAS = ("data/things/", "data/sounds/")
EXT_IGNORADAS = (".otmm", ".log", ".dmp", ".pdb", ".ilk", ".exe", ".bak",
                 ".console-bak")
# O proprio launcher e seu estado NAO entram no manifest: se entrassem, o
# updater tentaria baixar o launcher por cima dele mesmo enquanto ele roda,
# corrompendo o arquivo. Atualizar o launcher e' caso raro, feito via novo
# instalador. tibia.ico tambem fica de fora (so o instalador precisa).
# tibia.ico ENTRA: o launcher aponta o atalho para ele em tempo de execucao,
# entao precisa existir tambem em quem atualiza sem reinstalar.
NOMES_IGNORADOS = ("otclient.log", "launcher.ps1", "launcher.vbs",
                   "launcher.log", ".versao_instalada")

# O binario e' tratado a parte, no campo `binary` do manifest.
BINARIO = "otclient.exe"


def crc32_hex(caminho: Path) -> str:
    """CRC32 no formato do client: hex minusculo, sem zero a esquerda."""
    crc = 0
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            crc = zlib.crc32(bloco, crc)
    return format(crc & 0xFFFFFFFF, "x")


def deve_incluir(rel: str) -> bool:
    rel_barra = rel.replace("\\", "/")
    if any(rel_barra.startswith(p) for p in PASTAS_IGNORADAS):
        return False
    if rel_barra.lower().endswith(EXT_IGNORADAS):
        return False
    if Path(rel_barra).name in NOMES_IGNORADOS:
        return False
    return True


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--client", required=True,
                   help="pasta do client montado (a que tem otclient.exe)")
    p.add_argument("--url", required=True,
                   help="URL base de onde o client baixa (SEM barra final; o "
                        "updater junta url .. /caminho)")
    p.add_argument("--saida", required=True,
                   help="pasta a publicar: recebe manifest.json e files/")
    p.add_argument("--sem-binario", action="store_true",
                   help="nao inclui o otclient.exe no manifest")
    args = p.parse_args()

    client = Path(args.client)
    if not (client / BINARIO).exists():
        print(f"{client} nao parece um client montado (sem {BINARIO})", file=sys.stderr)
        return 1
    url = args.url.rstrip("/")   # o path das chaves ja comeca com barra

    saida = Path(args.saida)
    pasta_files = saida / "files"
    if pasta_files.exists():
        shutil.rmtree(pasta_files)
    pasta_files.mkdir(parents=True, exist_ok=True)

    files: dict[str, str] = {}
    total = 0
    for caminho in sorted(client.rglob("*")):
        if not caminho.is_file():
            continue
        rel = caminho.relative_to(client).as_posix()
        if not deve_incluir(rel):
            continue

        # chave com barra inicial, como o client gera em filesChecksums()
        files["/" + rel] = crc32_hex(caminho)
        destino = pasta_files / rel
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(caminho, destino)
        total += caminho.stat().st_size

    binario = None
    if not args.sem_binario:
        exe = client / BINARIO
        binario = {
            "file": "/" + BINARIO,
            "checksum": crc32_hex(exe),
            "url": url,
        }
        shutil.copy2(exe, pasta_files / BINARIO)
        total += exe.stat().st_size

    # "version": impressao digital do conjunto (arquivos + binario). Muda se
    # qualquer coisa muda. O launcher guarda a version que instalou e, no
    # arranque, compara so isto com a do servidor: se for igual, abre o jogo na
    # hora, sem conferir os ~3000 arquivos um a um (o que levava quase um minuto).
    resumo = "\n".join(f"{k}={files[k]}" for k in sorted(files))
    if binario:
        resumo += f"\n{binario['file']}={binario['checksum']}"
    version = format(zlib.crc32(resumo.encode("utf-8")) & 0xFFFFFFFF, "x")

    manifest: dict = {
        "url": url,
        "version": version,
        "keepFiles": False,
        "files": files,
    }
    if binario:
        manifest["binary"] = binario

    (saida / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"{len(files)} arquivos no manifest"
          + (" + otclient.exe" if not args.sem_binario else ""))
    print(f"  {total / 1024 / 1024:.1f} MB copiados para {pasta_files}")
    print(f"  manifest: {saida / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
