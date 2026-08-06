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

# As hunts contornadas pelo achar_hunts.py. Rodando do repositorio elas ficam
# ao lado deste arquivo; no instalado, tambem -- mas ali RAIZ aponta para
# AppData\Local, que nao tem tools/mapa. Por isso o caminho e' relativo a AQUI,
# nao a RAIZ: amarrar em RAIZ fazia a lista chegar vazia para quem instalou.
PASTA_AUTOMATICAS = AQUI / "hunts_automaticas"

# Onde o botao "Salvar" grava. Separada das automaticas de proposito: rodar o
# achar_hunts.py de novo apaga e reescreve aquela pasta, e levar junto o que a
# pessoa corrigiu na mao seria perder trabalho.
PASTA_SALVAS = AQUI / "hunts_salvas"

# As aprovadas: as que ja foram conferidas e podem virar instancia. Tem
# numeracao propria, sequencial, separada do id da planilha -- a planilha tem
# 525 linhas e so' um punhado vira hunt de verdade, entao numerar por ela
# deixaria buracos e nao diria nada sobre ordem de implementacao.
PASTA_REVISADAS = AQUI / "hunts_revisadas"
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(RAIZ / "tools/sprites"))

from gerar_minimapa import ITEM_VAZIO, ler_atributos
from monstros import Sprites
from otbm import Mapa
from render import desenhar
from ver_item import Assets

BLOCO = 128          # tiles por imagem

# Em que resolucao desenhar para atender cada nivel pedido. Renderizar sempre
# a 32 px/tile e reduzir depois desperdica: colar sprite custa proporcional a
# area, e quem esta explorando o mapa pede 2, 4 ou 8. Duas bases cobrem tudo
# -- uma leve para explorar, uma para o zoom maximo -- e cada uma atende
# varios niveis, entao mexer na roda do mouse nao redesenha.
#
# 16 px/tile e' o maior zoom do mapeador: da para marcar tile a tile sem
# esforco, e evita a base de 4096x4096 (48 MB viva, 4x mais lenta) que so
# serviria para ver pixel de sprite.
BASES = {1: 8, 2: 8, 4: 8, 8: 8, 16: 16}

# Tetos de memoria. Existe cache em disco, entao guardar muito na RAM
# rende pouco -- o que importa e' o processo caber numa maquina que
# tambem esta rodando o jogo e o navegador.
TETO_CACHE = 96 << 20      # bytes de JPEG guardados em memoria
TETO_BASES = 16_000_000    # pixels de imagem base viva

RE_BLOCO_XML = re.compile(
    rb'<monster\s+centerx="(\d+)"\s+centery="(\d+)"\s+centerz="(\d+)"'
    rb'(?:\s+radius="(\d+)")?\s*>(.*?)</monster>', re.DOTALL)
RE_FILHO_XML = re.compile(
    rb'<monster\s+name="([^"]+)"\s+x="(-?\d+)"\s+y="(-?\d+)"\s+z="(\d+)"')


class Estado:
    def __init__(self, mapa: Path, assets: Path, spawns: Path, planilha,
                 disco: Path | None = None, monstros: Path | None = None):
        print("abrindo mapa...")
        # sem cache_tiles: o render le cada tile uma vez por bloco e reler e'
        # mais barato que guardar. Com ele o processo chegava a varios GB.
        self.mapa = Mapa(mapa, cache_tiles=False, limite_areas=16,
                         mapear=True)
        print("abrindo assets...")
        self.assets = Assets(assets)
        print("indexando aparencias...")
        self.assets.aparencias.indexar("object")
        # flags de bloqueio, para a varinha saber onde da para andar
        self.atributos = ler_atributos(self._achar_appearances(assets))
        self.cache: dict[str, bytes] = {}
        self.bytes_cache = 0
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
        self.sprites = Sprites(
            self.assets,
            monstros or RAIZ / "data-otservbr-global/monster")
        self.fila: list[tuple] = []
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

    @staticmethod
    def _achar_appearances(assets: Path) -> Path:
        """Onde esta o appearances.dat, no repositorio ou no instalado.

        Rodando do repositorio ele vem de data/items/. Na maquina de quem
        instalou nao existe repositorio nenhum -- so a pasta de assets, onde o
        arquivo vem com o hash no nome (appearances-<hash>.dat). Amarrar so no
        primeiro caminho fazia o servidor instalado morrer no boot.
        """
        do_repo = RAIZ / "data/items/appearances.dat"
        if do_repo.exists():
            return do_repo
        achados = sorted(Path(assets).glob("appearances*.dat"))
        if achados:
            return achados[0]
        raise FileNotFoundError(
            f"nao achei o appearances.dat nem em {do_repo} nem em {assets}")

    def _ler_planilha(self, caminho):
        if not caminho or not Path(caminho).exists():
            # Sem a planilha o campo de id fica mudo: digitar 309 nao mostra
            # "Lion Sanctum" e nao da' para saber se e' a hunt certa. A
            # planilha mora no Downloads de quem a montou, entao os nomes
            # ficam versionados aqui para o mapeador servir sozinho -- os
            # amigos que instalarem tambem nao a tem.
            copia = Path(__file__).parent / "hunts_catalogo.json"
            if copia.exists():
                try:
                    return json.loads(copia.read_text(encoding="utf-8"))
                except ValueError:
                    return []
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
            self.bases[chave] = im
            # a base de 16 px/tile e' 2048x2048 RGB = 12 MB viva, a de 8 e'
            # 3 MB. O teto conta pixels para nao depender do nivel.
            while (sum(b.width * b.height for b in self.bases.values())
                   > TETO_BASES and len(self.bases) > 1):
                self.bases.pop(next(iter(self.bases)))
        return im

    def jpeg(self, z: int, bx: int, by: int, p: int) -> bytes:
        """O bloco em `p` pixels por tile.

        Servir sempre 32 px/tile era o grosso da lentidao sentida no
        navegador: com zoom 3 a tela mostra 12 blocos, cada um 4096x4096, e o
        navegador decodificava 200 megapixels para desenhar 1120x848. Agora o
        servidor reduz do lado de ca -- em p=4 o mesmo bloco vira 512x512, uns
        30 KB, e a tela inteira cabe em menos de meio megapixel.
        """
        p = max(1, min(16, 1 << (p - 1).bit_length()))     # potencia de 2
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
            if chave in self.cache:
                return
            self.cache[chave] = dados
            self.bytes_cache += len(dados)
            # o limite era por QUANTIDADE, e um JPEG varia de 30 KB a 8 MB --
            # 400 deles chegavam a gigabytes. Contar bytes e' o certo.
            while self.bytes_cache > TETO_CACHE and len(self.cache) > 1:
                velha = next(iter(self.cache))
                self.bytes_cache -= len(self.cache.pop(velha))

    # ------------------------------------------------------- varinha magica

    def _andavel(self, x: int, y: int, z: int) -> bool:
        """Da para pisar aqui? Precisa de chao e de nada que bloqueie."""
        t = self.mapa.tile(x, y, z)
        if not t or not t.chao:
            return False
        if self.atributos.get(t.chao, ITEM_VAZIO).bloqueia:
            return False
        for iid, _, _ in t.itens:
            if self.atributos.get(iid, ITEM_VAZIO).bloqueia:
                return False
        return True

    def preencher(self, x: int, y: int, z: int, raio: int = 60,
                  teto: int = 40000, margem: int = 2):
        """Area alcancavel a pe a partir de (x, y, z), mais a parede em volta.

        POR QUE ISTO EXISTE. O primeiro mapeamento da hunt dos ciclopes era um
        RETANGULO de 137x89 em cinco andares: pegava grama, rocha macica e
        area fora da caverna. Um recorte assim carrega tiles que ninguem pisa
        e nao acompanha o formato do lugar.
        Partindo de um ponto de dentro e andando so por onde da para andar, o
        resultado e' a caverna de verdade.

        A `margem` dilata o resultado para incluir a parede que fecha a area.
        Sem ela o recorte terminaria no ultimo tile pisavel e o jogador veria
        o vazio no lugar da parede.

        O `raio` e' o que torna a ferramenta utilizavel na SUPERFICIE. La fora
        tudo e' conectado -- clicar na grama e deixar a busca correr encheu o
        continente inteiro: 40 mil tiles pisaveis espalhados por 349x357. Nao
        adianta avisar depois; limitar a distancia do clique da um resultado
        previsivel em qualquer lugar. Dentro de caverna a parede costuma parar
        antes do raio, e o resultado e' o mesmo de antes.

        Se ainda assim bater no teto, a resposta vem SEM tiles: melhor nao
        marcar nada do que despejar dezenas de milhares para o usuario apagar.
        """
        if not self._andavel(x, y, z):
            return {"erro": "esse tile nao e' pisavel; clique dentro da area"}

        with self.render_lock:      # o Mapa nao e' thread-safe
            dentro = {(x, y)}
            fila = [(x, y)]
            vazou = False
            while fila:
                if len(dentro) >= teto:
                    vazou = True
                    break
                cx, cy = fila.pop()
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1),
                               (1, 1), (1, -1), (-1, 1), (-1, -1)):
                    nx, ny = cx + dx, cy + dy
                    if (nx, ny) in dentro:
                        continue
                    if max(abs(nx - x), abs(ny - y)) > raio:
                        continue
                    if self._andavel(nx, ny, z):
                        dentro.add((nx, ny))
                        fila.append((nx, ny))

            # dilata: a parede que fecha a area tem de vir junto
            total = set(dentro)
            borda = dentro
            for _ in range(max(0, margem)):
                nova = set()
                for cx, cy in borda:
                    for dx in (-1, 0, 1):
                        for dy in (-1, 0, 1):
                            p = (cx + dx, cy + dy)
                            if p not in total:
                                total.add(p)
                                nova.add(p)
                borda = nova

        if vazou:
            return {"erro": f"a area passou de {teto} tiles e nada foi marcado. "
                            f"Diminua o raio (esta em {raio}) ou feche a "
                            f"passagem com o pincel antes de usar a varinha."}

        return {
            "z": z,
            "raio": raio,
            "tiles": sorted(total),
            "pisavel": len(dentro),
            "comMargem": len(total),
            "vazou": vazou,
        }

    # ------------------------------------------------------------ prefetch

    def pedir_vizinhos(self, z: int, bx: int, by: int, p: int) -> None:
        """Deixa na fila os 4 blocos colados neste, para o arraste nao esperar.

        A fila e' TROCADA, nao acumulada. Enfileirar os 8 vizinhos de cada
        bloco pedido gerava 158 renders para 45 pedidos: quase tudo fora da
        tela, e o prefetch disputando o lock com o que o usuario espera. So
        vale adivinhar em volta de onde ele esta agora.
        """
        with self.lock:
            self.fila = [(z, bx + dx, by + dy, p)
                         for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
        self.tem_fila.set()

    def _prefetcher(self) -> None:
        while True:
            self.tem_fila.wait()
            # Espera a tela sossegar. O lock de render e' unico e um render
            # comecado nao da para interromper, entao o prefetch so entra
            # depois de um intervalo sem pedido nenhum -- durante a enxurrada
            # que enche a tela ele fica fora do caminho.
            quieto = 0.0
            while quieto < 0.25:
                if self.pendentes > 0:
                    quieto = 0.0
                else:
                    quieto += 0.05
                time.sleep(0.05)
            with self.lock:
                if not self.fila:
                    self.tem_fila.clear()
                    continue
                pedido = self.fila.pop()
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

        def do_POST(self):
            # Gravar a hunt na pasta do proprio mapeador, com o nome do lugar
            # no arquivo. O botao "Baixar JSON" joga na pasta de downloads do
            # navegador, misturado com todo o resto e com nome que o navegador
            # inventa quando repete -- aqui fica um lugar so', que sobrevive a
            # fechar a aba e da' para pegar depois.
            if self.path == "/revisar":
                self._revisar()
                return
            if self.path != "/salvar":
                self.send_error(404)
                return
            try:
                n = int(self.headers.get("Content-Length") or 0)
                doc = json.loads(self.rfile.read(n).decode("utf-8"))
                if not isinstance(doc, dict) or "limites" not in doc:
                    raise ValueError("nao parece uma hunt")
                hid = int(doc.get("id") or 0)
                nome = re.sub(r"[^A-Za-z0-9]+", "_",
                              str(doc.get("nome") or "sem_nome")).strip("_") or "sem_nome"
                PASTA_SALVAS.mkdir(parents=True, exist_ok=True)
                arq = PASTA_SALVAS / f"hunt_{hid}_{nome}.json"
                arq.write_text(json.dumps(doc, ensure_ascii=False, indent=1),
                               encoding="utf-8")
                self._envia(json.dumps({"arquivo": arq.name,
                                        "pasta": str(PASTA_SALVAS)}).encode("utf-8"),
                            "application/json; charset=utf-8", cachear=False)
            except (ValueError, OSError, UnicodeDecodeError) as e:
                self._envia(json.dumps({"erro": str(e)}).encode("utf-8"),
                            "application/json; charset=utf-8", cachear=False)

        def _revisar(self):
            """Promove a hunt aberta para a lista das aprovadas.

            Recusa o que nao daria para instanciar: sem limites nao ha o que
            recortar, sem obelisco nao ha por onde entrar, sem inicio nao ha
            onde o jogador aparece. Melhor barrar aqui do que descobrir com o
            servidor no ar.
            """
            try:
                n = int(self.headers.get("Content-Length") or 0)
                doc = json.loads(self.rfile.read(n).decode("utf-8"))
                if not isinstance(doc, dict):
                    raise ValueError("corpo invalido")

                faltando = []
                if not doc.get("limites"):
                    faltando.append("limites (pinte a area)")
                if not doc.get("obelisco"):
                    faltando.append("obelisco (por onde se entra)")
                if not doc.get("inicio"):
                    faltando.append("inicio (onde o jogador aparece)")
                if faltando:
                    raise ValueError("falta " + ", ".join(faltando))

                PASTA_REVISADAS.mkdir(parents=True, exist_ok=True)
                # Revisar de novo a MESMA hunt reaproveita o numero, senao
                # cada correcao criaria uma aprovada nova e a lista encheria
                # de versoes da mesma coisa.
                numero, antigo = 0, None
                usados = set()
                for arq in PASTA_REVISADAS.glob("hunt_*.json"):
                    try:
                        d = json.loads(arq.read_text(encoding="utf-8"))
                    except (OSError, ValueError):
                        continue
                    num = d.get("revisada", {}).get("numero", d.get("id", 0))
                    usados.add(num)
                    if d.get("nome") == doc.get("nome"):
                        numero, antigo = num, arq
                if not numero:
                    numero = max(usados, default=0) + 1

                doc["revisada"] = {
                    "numero": numero,
                    "em": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "origem": "automatica" if doc.get("automatico") else "manual",
                }
                nome = re.sub(r"[^A-Za-z0-9]+", "_",
                              str(doc.get("nome") or "sem_nome")).strip("_") or "sem_nome"
                arq = PASTA_REVISADAS / f"hunt_{numero}_{nome}.json"
                arq.write_text(json.dumps(doc, ensure_ascii=False, indent=1),
                               encoding="utf-8")
                if antigo and antigo != arq:
                    antigo.unlink(missing_ok=True)   # renomeou: nao deixa as duas
                self._envia(json.dumps({"numero": numero, "arquivo": arq.name,
                                        "pasta": str(PASTA_REVISADAS),
                                        "substituiu": bool(antigo)}).encode("utf-8"),
                            "application/json; charset=utf-8", cachear=False)
            except (ValueError, OSError, UnicodeDecodeError) as e:
                self._envia(json.dumps({"erro": str(e)}).encode("utf-8"),
                            "application/json; charset=utf-8", cachear=False)

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

                # Hunts que o achar_hunts.py contornou sozinho. Sao 132
                # arquivos: escolher no seletor de arquivo do sistema seria
                # pior do que uma lista aqui, ainda mais para conferir varias
                # em sequencia.
                if self.path == "/revisadas":
                    lista = []
                    for arq in sorted(PASTA_REVISADAS.glob("hunt_*.json")):
                        try:
                            d = json.loads(arq.read_text(encoding="utf-8"))
                        except (OSError, ValueError):
                            continue
                        r = d.get("revisada", {})
                        lista.append({
                            "numero": r.get("numero", d.get("id", 0)),
                            "id": d.get("id", 0), "nome": d.get("nome", ""),
                            "arquivo": arq.name, "andares": d.get("andares", []),
                            "tiles": sum(len(v) for v in d.get("limites", {}).values()),
                            "monstros": d.get("totalMonstros", 0),
                            "temObelisco": bool(d.get("obelisco")),
                            "temInicio": bool(d.get("inicio")),
                            "origem": r.get("origem", "?"),
                        })
                    lista.sort(key=lambda h: h["numero"])
                    self._envia(json.dumps(lista).encode("utf-8"),
                                "application/json; charset=utf-8", cachear=False)
                    return

                m = re.match(r"^/revisadas/([A-Za-z0-9_.\-]+\.json)$", self.path)
                if m:
                    arq = PASTA_REVISADAS / m.group(1)
                    if (arq.resolve().parent != PASTA_REVISADAS.resolve()
                            or not arq.is_file()):
                        self.send_error(404)
                        return
                    self._envia(arq.read_bytes(),
                                "application/json; charset=utf-8", cachear=False)
                    return

                if self.path == "/automaticas":
                    pasta = PASTA_AUTOMATICAS
                    lista = []
                    for arq in sorted(pasta.glob("hunt_*.json")):
                        try:
                            d = json.loads(arq.read_text(encoding="utf-8"))
                        except (OSError, ValueError):
                            continue
                        a = d.get("automatico", {})
                        lista.append({
                            "id": d["id"], "nome": d["nome"], "arquivo": arq.name,
                            "andares": d["andares"],
                            "tiles": sum(len(v) for v in d["limites"].values()),
                            "confianca": a.get("confianca", "?"),
                            "pureza": a.get("pureza", 0),
                            "monstros": d.get("totalMonstros", 0),
                        })
                    lista.sort(key=lambda h: ({"alta": 0, "media": 1, "baixa": 2}
                                              .get(h["confianca"], 3), h["nome"]))
                    self._envia(json.dumps(lista).encode("utf-8"),
                                "application/json; charset=utf-8", cachear=False)
                    return

                m = re.match(r"^/automaticas/([A-Za-z0-9_.\-]+\.json)$", self.path)
                if m:
                    arq = PASTA_AUTOMATICAS / m.group(1)
                    # resolve() para o nome nao escapar da pasta
                    if (arq.resolve().parent != PASTA_AUTOMATICAS.resolve()
                            or not arq.is_file()):
                        self.send_error(404)
                        return
                    self._envia(arq.read_bytes(), "application/json; charset=utf-8",
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

                m = re.match(r"^/preencher/(\d+)/(-?\d+)/(-?\d+)/(\d+)$", self.path)
                if m:
                    z, x, y, raio = (int(m.group(i)) for i in (1, 2, 3, 4))
                    raio = max(5, min(200, raio))
                    self._envia(json.dumps(est.preencher(x, y, z, raio)).encode(),
                                "application/json; charset=utf-8", cachear=False)
                    return

                m = re.match(r"^/monstro/(\d+)\.png$", self.path)
                if m:
                    png = est.monstro_png(int(m.group(1)))
                    if png is None:
                        self.send_error(404)
                        return
                    self._envia(png, "image/png")
                    return

                # URL de tile sem o nivel: e' a pagina antiga, que ficou em
                # cache no navegador quando o Cache-Control ainda valia para o
                # HTML. Ela pede blocos que nao existem mais e a tela fica
                # preta -- Ctrl+Shift+R resolve.
                if re.match(r"^/tile/\d+/-?\d+_-?\d+\.jpg$", self.path):
                    print("  ATENCAO: pedido no formato antigo "
                          f"({self.path}). A pagina aberta esta em cache; "
                          "recarregue com Ctrl+Shift+R.", flush=True)
                self.send_error(404)
            except BrokenPipeError:
                pass
            except Exception as e:                     # noqa: BLE001
                self.send_error(500, str(e))
    return H


def exemplo_ciclopes() -> dict:
    """A hunt que abre de partida: os ciclopes ao norte de Thais.

    Era um retangulo escrito na mao -- 137x89 tiles em cinco andares, 61.605
    no total, cobrindo montanha, mar e o que mais estivesse no caminho. Como e'
    a primeira coisa que aparece na tela, dava a impressao de que mapear era
    isso: pintar um bloco por cima da regiao.

    Agora vem do achar_hunts.py, com o mesmo contorno das outras: 10.327 tiles
    seguindo as cavernas, 84% de ciclope dentro. Foi gerado com --perto porque
    "Cyclops Camp" existe em mais de um lugar do mapa e o maior grupo nao e' o
    de Thais.
    """
    arq = AQUI / "exemplo_ciclopes.json"
    if arq.exists():
        try:
            return json.loads(arq.read_text(encoding="utf-8"))
        except ValueError:
            pass
    # Sem o arquivo, um retangulo pequeno so' para a tela nao abrir vazia.
    return {"id": 0, "nome": "Ciclopes de Thais (exemplo minimo)",
            "obelisco": {"x": 32454, "y": 32116, "z": 7},
            "inicio": {"x": 32464, "y": 32085, "z": 7},
            "limites": {"7": [[x, y] for x in range(32440, 32471)
                              for y in range(32070, 32101)]}}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("mapa")
    p.add_argument("--assets", required=True)
    p.add_argument("--spawns",
                   default=str(RAIZ / "data-otservbr-global/world/otservbr-monster.xml"))
    p.add_argument("--planilha")
    p.add_argument("--monstros",
                   help="pasta com os .lua dos monstros (de onde vem o lookType)")
    p.add_argument("--porta", type=int, default=8100)
    p.add_argument("--cache", default=str(AQUI / "cache_tiles"),
                   help="pasta do cache em disco; vazio desliga")
    args = p.parse_args()

    est = Estado(Path(args.mapa), Path(args.assets),
                 Path(args.spawns), args.planilha,
                 Path(args.cache) if args.cache else None,
                 Path(args.monstros) if args.monstros else None)
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
