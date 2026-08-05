#!/usr/bin/env python3
"""Servidor local do mapeador: renderiza o mapa com os sprites do client.

POR QUE UM SERVIDOR, e nao arquivos prontos
-------------------------------------------
Com sprites de verdade, um no de area (256x256 tiles) vira uma imagem de
8192x8192. Pre-gerar as ~1120 areas daria varios GB e mais de uma hora. Mas
renderizar uma regiao de 128x128 leva ~1,2 s, entao vale renderizar SO o que
esta na tela, no momento em que aparece, e guardar em cache.

O que tornou isso viavel foi indexar as aparencias: Appearances.sprite_ids
percorria o protobuf inteiro a cada item -- 71 ms por sprite, 10 s para uma
regiao pequena. Com Appearances.indexar o mesmo render caiu para ~1,1 s.

Rodar como servidor tambem resolve o file://: o navegador bloqueia fetch()
em arquivo local, e foi o que deixou a primeira versao com tela preta.

    python3 servidor_mapeador.py <mapa.otbm> --assets <pasta> [--porta 8100]
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
import threading
import time
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PIL import Image

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(RAIZ / "tools/sprites"))

from monstros import Sprites
from otbm import Mapa
from render import desenhar
from ver_item import Assets

BLOCO = 128          # tiles por imagem

# Em que resolucao desenhar para atender cada nivel pedido. Renderizar sempre
# a 32 px/tile e reduzir depois desperdica: colar sprite custa proporcional a
# area, e quem esta explorando o mapa pede 2, 4 ou 8. Duas bases cobrem tudo
# -- uma leve para explorar, uma cheia para o zoom maximo -- e cada uma
# atende varios niveis, entao mexer na roda do mouse nao redesenha.
BASES = {1: 8, 2: 8, 4: 8, 8: 8, 16: 32, 32: 32}

RE_BLOCO_XML = re.compile(
    rb'<monster\s+centerx="(\d+)"\s+centery="(\d+)"\s+centerz="(\d+)"'
    rb'(?:\s+radius="(\d+)")?\s*>(.*?)</monster>', re.DOTALL)
RE_FILHO_XML = re.compile(
    rb'<monster\s+name="([^"]+)"\s+x="(-?\d+)"\s+y="(-?\d+)"\s+z="(\d+)"')


class Estado:
    def __init__(self, mapa: Path, assets: Path, spawns: Path, planilha,
                 disco: Path | None = None):
        print("abrindo mapa...")
        self.mapa = Mapa(mapa)
        print("abrindo assets...")
        self.assets = Assets(assets)
        print("indexando aparencias...")
        self.assets.aparencias.indexar("object")
        self.cache: dict[str, bytes] = {}
        self.bases: dict[tuple[int, int, int], Image.Image] = {}
        # cache em disco: o render e' caro mas deterministico, entao vale
        # guardar entre execucoes -- reabrir o mapeador na mesma regiao passa
        # a ser instantaneo
        self.disco = disco
        if disco:
            disco.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        # o Mapa nao e thread-safe (indexa areas sob demanda), entao render
        # e' serializado; o ThreadingHTTPServer segue util para os estaticos
        self.render_lock = threading.Lock()
        self.areas = sorted(self.mapa.areas())
        self.monstros = self._ler_spawns(spawns)
        self.hunts = self._ler_planilha(planilha)
        self.sprites = Sprites(self.assets,
                               RAIZ / "data-otservbr-global/monster")
        self.fila: list[tuple] = []
        self.na_fila: set[tuple] = set()
        self.tem_fila = threading.Event()
        self.pendentes = 0          # blocos que a tela esta esperando agora
        threading.Thread(target=self._prefetcher, daemon=True).start()
        print(f"pronto: {len(self.areas)} areas, "
              f"{self.monstros['total']} spawns, {len(self.hunts)} hunts, "
              f"{len(self.sprites.looktypes)} outfits")

    def monstro_png(self, indice: int) -> bytes | None:
        nomes = self.monstros["nomes"]
        if not 0 <= indice < len(nomes):
            return None
        with self.render_lock:      # Assets._folhas nao e' thread-safe
            return self.sprites.png(nomes[indice])

    def _ler_spawns(self, caminho: Path):
        if not caminho.exists():
            return {"nomes": [], "porAndar": {}, "total": 0}
        dados = caminho.read_bytes()
        nomes, lista_nomes = {}, []
        por_andar = defaultdict(list)
        total = 0
        for m in RE_BLOCO_XML.finditer(dados):
            cx, cy = int(m.group(1)), int(m.group(2))
            for f in RE_FILHO_XML.finditer(m.group(5)):
                nome = f.group(1).decode(errors="replace")
                if nome not in nomes:
                    nomes[nome] = len(lista_nomes)
                    lista_nomes.append(nome)
                por_andar[int(f.group(4))].append(
                    [cx + int(f.group(2)), cy + int(f.group(3)), nomes[nome]])
                total += 1
        return {"nomes": lista_nomes,
                "porAndar": {str(k): v for k, v in sorted(por_andar.items())},
                "total": total}

    def _ler_planilha(self, caminho):
        if not caminho or not Path(caminho).exists():
            return []
        try:
            import openpyxl
        except ImportError:
            return []
        wb = openpyxl.load_workbook(caminho, read_only=True, data_only=True)
        if "Catalogo_Hunts" not in wb.sheetnames:
            return []
        ws, hunts, cab = wb["Catalogo_Hunts"], [], None
        for row in ws.iter_rows(values_only=True):
            if cab is None:
                if row and row[0] == "ID":
                    cab = row
                continue
            if not row or row[0] is None:
                continue
            try:
                hid = int(row[0])
            except (TypeError, ValueError):
                continue
            hunts.append({"id": hid,
                          "nome": str(row[1]) if len(row) > 1 and row[1] else "",
                          "classe": str(row[27]) if len(row) > 27 and row[27] else ""})
        return hunts

    # ------------------------------------------------------------- imagens

    def _base(self, z: int, bx: int, by: int, q: int) -> Image.Image:
        """O bloco desenhado a `q` pixels por tile (ver BASES)."""
        chave = (z, bx, by, q)
        with self.lock:
            im = self.bases.get(chave)
        if im is not None:
            return im
        x0, y0 = bx * BLOCO, by * BLOCO
        t0 = time.perf_counter()
        im = desenhar(self.mapa, self.assets, x0, y0,
                      x0 + BLOCO - 1, y0 + BLOCO - 1, z,
                      zoom=1, px_tile=q).convert("RGB")
        print(f"  render {z}/{bx}_{by} @{q}: {time.perf_counter() - t0:.2f}s",
              flush=True)
        with self.lock:
            # a base de 32 px/tile e' 4096x4096 RGB = 48 MB viva; a de 8 e'
            # 3 MB. O limite conta em megapixels para nao guardar 6 gigantes.
            while sum(b.width * b.height for b in self.bases.values()) > 120e6:
                self.bases.pop(next(iter(self.bases)))
            self.bases[chave] = im
        return im

    def jpeg(self, z: int, bx: int, by: int, p: int) -> bytes:
        """O bloco em `p` pixels por tile.

        Servir sempre 32 px/tile era o grosso da lentidao sentida no
        navegador: com zoom 3 a tela mostra 12 blocos, cada um 4096x4096, e o
        navegador decodificava 200 megapixels para desenhar 1120x848. Agora o
        servidor reduz do lado de ca -- em p=4 o mesmo bloco vira 512x512, uns
        30 KB, e a tela inteira cabe em menos de meio megapixel.
        """
        p = max(1, min(32, 1 << (p - 1).bit_length()))     # potencia de 2
        chave = f"{z}/{bx}_{by}_{p}"
        with self.lock:
            if chave in self.cache:
                return self.cache[chave]
        arq = self.disco / str(z) / f"{bx}_{by}_{p}.jpg" if self.disco else None
        if arq is not None and arq.exists():
            dados = arq.read_bytes()
            self._guardar(chave, dados)
            return dados

        with self.render_lock:
            with self.lock:
                if chave in self.cache:
                    return self.cache[chave]
            im = self._base(z, bx, by, BASES[p])
            lado = BLOCO * p
            if lado != im.width:
                # BOX faz media dos pixels da area: reduzir 8x com NEAREST
                # descartaria 63 de cada 64 pixels e some com paredes finas
                im = im.resize((lado, lado), Image.BOX)
            buf = io.BytesIO()
            # JPEG e' ~7x mais rapido que PNG aqui e o mapa nao usa alfa.
            # 4:4:4 porque sprite e' arte pixelada: subamostrar cor borra
            # contorno de parede.
            im.save(buf, "JPEG", quality=85, subsampling=0)
            dados = buf.getvalue()

        if arq is not None:
            try:
                arq.parent.mkdir(parents=True, exist_ok=True)
                arq.write_bytes(dados)
            except OSError:
                pass
        self._guardar(chave, dados)
        return dados

    def _guardar(self, chave: str, dados: bytes) -> None:
        with self.lock:
            if len(self.cache) > 400:
                self.cache.pop(next(iter(self.cache)))
            self.cache[chave] = dados

    # ------------------------------------------------------------ prefetch

    def pedir_vizinhos(self, z: int, bx: int, by: int, p: int) -> None:
        """Enfileira os 8 blocos ao redor, para o arraste nao esperar render.

        Quem arrasta o mapa quase sempre vai para um vizinho, e o vizinho leva
        ~1 s para nascer. Rendendo antes, o arraste encontra tudo em cache.
        """
        with self.lock:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if dx == dy == 0:
                        continue
                    pedido = (z, bx + dx, by + dy, p)
                    if pedido not in self.na_fila:
                        self.na_fila.add(pedido)
                        self.fila.append(pedido)
        self.tem_fila.set()

    def _prefetcher(self) -> None:
        while True:
            self.tem_fila.wait()
            # Espera a tela ficar quieta. O lock de render e' unico, e sem
            # isto o prefetch pegava a vez entre dois blocos que o usuario
            # esta esperando -- cada tile visivel levava 2 s em vez de 0,7 s.
            while self.pendentes > 0:
                time.sleep(0.05)
            with self.lock:
                if not self.fila:
                    self.tem_fila.clear()
                    continue
                # ultimo a entrar primeiro: o que o usuario pediu por ultimo
                # e' o que ele esta olhando agora
                pedido = self.fila.pop()
                self.na_fila.discard(pedido)
            try:
                self.jpeg(*pedido)
            except Exception:                              # noqa: BLE001
                pass                                       # bloco vazio, tudo bem


def fazer_handler(est: Estado, exemplo: dict):
    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):
            pass

        def _envia(self, dados: bytes, tipo: str, cachear: bool = True):
            self.send_response(200)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(dados)))
            # imagem pode ficar no navegador; a pagina e os dados NAO -- o
            # max-age valia para tudo e servia HTML velho depois de editar
            self.send_header("Cache-Control",
                             "max-age=86400" if cachear else "no-store")
            self.end_headers()
            self.wfile.write(dados)

        def do_GET(self):
            try:
                self.path = self.path.split("?", 1)[0]   # ignora query string
                if self.path in ("/", "/index.html"):
                    html = (AQUI / "mapeador.html").read_text(encoding="utf-8")
                    html = html.replace(
                        '<script src="atlas/dados.js"></script>',
                        "<script>const ATLAS_MODO_SERVIDOR = true;</script>")
                    self._envia(html.encode("utf-8"), "text/html; charset=utf-8",
                                cachear=False)
                    return

                if self.path == "/dados":
                    d = {
                        "bloco": BLOCO,
                        "areas": [{"z": z, "ax": x // 256, "ay": y // 256}
                                  for x, y, z in
                                  ((a[0], a[1], a[2]) for a in est.areas)],
                        "monstros": est.monstros,
                        "hunts": est.hunts,
                        "exemplo": exemplo,
                    }
                    self._envia(json.dumps(d).encode("utf-8"),
                                "application/json; charset=utf-8",
                                cachear=False)
                    return

                m = re.match(r"^/tile/(\d+)/(-?\d+)_(-?\d+)/(\d+)\.jpg$",
                             self.path)
                if m:
                    z, bx, by, p = (int(m.group(i)) for i in (1, 2, 3, 4))
                    with est.lock:
                        est.pendentes += 1
                    try:
                        dados = est.jpeg(z, bx, by, p)
                    finally:
                        with est.lock:
                            est.pendentes -= 1
                    est.pedir_vizinhos(z, bx, by, p)
                    self._envia(dados, "image/jpeg")
                    return

                m = re.match(r"^/monstro/(\d+)\.png$", self.path)
                if m:
                    png = est.monstro_png(int(m.group(1)))
                    if png is None:
                        self.send_error(404)
                        return
                    self._envia(png, "image/png")
                    return

                self.send_error(404)
            except BrokenPipeError:
                pass
            except Exception as e:                     # noqa: BLE001
                self.send_error(500, str(e))
    return H


def exemplo_ciclopes() -> dict:
    x0, y0 = 32384 + 16, 32016 + 16
    x1, y1 = 32384 + 152, 32016 + 104
    lim = {str(z): [[x, y] for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]
           for z in (5, 6, 7, 8, 9)}
    return {"id": 0, "nome": "Ciclopes de Thais (ja mapeada)",
            "obelisco": {"x": 32454, "y": 32116, "z": 7},
            "inicio": {"x": 32464, "y": 32085, "z": 7},
            "limites": lim}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("mapa")
    p.add_argument("--assets", required=True)
    p.add_argument("--spawns",
                   default=str(RAIZ / "data-otservbr-global/world/otservbr-monster.xml"))
    p.add_argument("--planilha")
    p.add_argument("--porta", type=int, default=8100)
    p.add_argument("--cache", default=str(AQUI / "cache_tiles"),
                   help="pasta do cache em disco; vazio desliga")
    args = p.parse_args()

    est = Estado(Path(args.mapa), Path(args.assets),
                 Path(args.spawns), args.planilha,
                 Path(args.cache) if args.cache else None)
    srv = ThreadingHTTPServer(("127.0.0.1", args.porta),
                              fazer_handler(est, exemplo_ciclopes()))
    url = f"http://127.0.0.1:{args.porta}/"
    print(f"\nMapeador em {url}   (Ctrl+C para parar)")
    try:
        import webbrowser
        webbrowser.open(url)
    except Exception:                                  # noqa: BLE001
        pass
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nencerrado")
    return 0


if __name__ == "__main__":
    sys.exit(main())
