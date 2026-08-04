#!/usr/bin/env python3
"""Servidor de atualizacao do client, para rodar no VPS.

Atende o updater embutido do otclient (mehah). Duas rotas:

    POST /updater        -> devolve o manifest.json (o client manda um POST com
                            a versao dele; a resposta e' a lista arquivo->crc32)
    GET  /files/<path>   -> serve o arquivo daquele caminho

O manifest e a pasta files/ sao gerados por gerar_manifest.py. Aqui o servidor
so os entrega; nao calcula nada. Assim, publicar uma atualizacao e' regenerar a
pasta e recarregar (ou reiniciar) este servico.

O GET em /updater tambem devolve o manifest, o que ajuda a testar no navegador.

Uso:

    python3 updater_server.py --raiz /root/client-update --porta 8090

Espera encontrar em --raiz:
    manifest.json
    files/...
"""
import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

RAIZ = Path(".")
PREFIXO_FILES = "/files/"

# O client pede os ícones da loja em http://<host>/images/store/<tamanho>/<nome>.png
# (o tamanho é 64 para o produto e 13 para o ícone do menu). O endereço vem do
# coinImagesURL do config.lua do servidor. Servir daqui evita subir um segundo
# servidor web só para isso.
PREFIXO_LOJA = "/images/store/"


class Handler(BaseHTTPRequestHandler):
    server_version = "rhapsodyyy-updater/1.0"

    # O BaseHTTPRequestHandler responde em HTTP/1.0 por padrao, e a biblioteca
    # HTTP do otclient nao interpreta esse status line -- ela falha com
    # "Cannot parse response code from status line" e nenhum icone da loja
    # carrega. Com HTTP/1.1 funciona. Exige Content-Length correto em toda
    # resposta, o que ja e' feito aqui (inclusive nos send_error).
    protocol_version = "HTTP/1.1"

    def end_headers(self):
        # HTTP/1.1 implica keep-alive, e o downloader do client parece esperar o
        # fechamento da conexao para dar a imagem por concluida -- com a conexao
        # presa, os icones da loja iam aparecendo um a um ao longo de ~30 s.
        # Fechar explicitamente mantem o status line que ele sabe ler e libera
        # cada resposta na hora.
        self.send_header("Connection", "close")
        super().end_headers()

    def _manifest(self):
        caminho = RAIZ / "manifest.json"
        if not caminho.is_file():
            self.send_error(500, "manifest.json ausente")
            return
        corpo = caminho.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def _arquivo(self, rota: str, prefixo: str = PREFIXO_FILES,
                 pasta: str = "files"):
        # unquote: nomes com [ ] chegam como %5B/%5D e precisam voltar ao literal,
        # senao o arquivo (que tem [ ] no disco) nao e' encontrado.
        rel = unquote(rota[len(prefixo):])

        base = (RAIZ / pasta).resolve()
        alvo = (base / rel).resolve()
        # nunca deixa sair da pasta files/ (path traversal)
        if not str(alvo).startswith(str(base) + os.sep) and alvo != base:
            self.send_error(403, "fora da pasta")
            return
        if not alvo.is_file():
            self.send_error(404, "nao encontrado")
            return

        corpo = alvo.read_bytes()
        self.send_response(200)
        tipo = "image/png" if alvo.suffix.lower() == ".png" else "application/octet-stream"
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def _rota(self):
        rota = self.path.split("?", 1)[0]
        # normaliza a barra dupla que apareceria se a url tivesse barra final
        while "//" in rota:
            rota = rota.replace("//", "/")
        return rota

    def do_POST(self):
        # descarta o corpo enviado pelo client (versao/os/etc); a resposta e' fixa
        tam = int(self.headers.get("Content-Length", 0) or 0)
        if tam:
            self.rfile.read(tam)
        if self._rota() == "/updater":
            self._manifest()
        else:
            self.send_error(404, "rota desconhecida")

    def do_GET(self):
        rota = self._rota()
        if rota == "/updater":
            self._manifest()
        elif rota.startswith(PREFIXO_FILES):
            self._arquivo(rota)
        elif rota.startswith(PREFIXO_LOJA):
            self._arquivo(rota, PREFIXO_LOJA, "images_store")
        elif rota == "/health":
            corpo = b'{"ok":true}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)
        else:
            self.send_error(404, "rota desconhecida")

    def log_message(self, fmt, *args):
        # log enxuto: metodo, rota e status
        print("%s - %s" % (self.address_string(), fmt % args))


def main():
    global RAIZ
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--raiz", required=True,
                   help="pasta com manifest.json e files/")
    p.add_argument("--porta", type=int, default=8090)
    p.add_argument("--host", default="0.0.0.0")
    args = p.parse_args()

    RAIZ = Path(args.raiz).resolve()
    if not (RAIZ / "manifest.json").is_file():
        raise SystemExit(f"nao achei manifest.json em {RAIZ}")

    httpd = ThreadingHTTPServer((args.host, args.porta), Handler)
    print(f"updater servindo {RAIZ} em http://{args.host}:{args.porta}")
    print(f"  manifest: http://{args.host}:{args.porta}/updater")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
