#!/usr/bin/env python3
"""Gera um visualizador HTML autocontido de uma regiao do mapa.

Abre no navegador, mostra a coordenada exata sob o cursor, e clicar copia a
Position(...) pronta. Sem servidor, sem dependencia externa: a imagem vai
embutida em base64.

Serve para escolher coordenada sem precisar andar no jogo -- foi o que fez
falta ao localizar a entrada da hunt.

    python3 visualizador.py x0 y0 x1 y1 z --assets <pasta> --saida mapa.html

Regiao grande fica pesada: 200x200 tiles a zoom 2 ja da ~5 MB de PNG. Para
visao ampla use --modo minimapa, que pinta 1 pixel por tile a partir do
appearances.dat (mesma logica do gerar_minimapa.py) e aguenta milhares de
tiles.
"""
from __future__ import annotations

import argparse
import base64
import io
import sys
from pathlib import Path

from PIL import Image

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
sys.path.insert(0, str(AQUI))

from otbm import Mapa

HTML = """<meta charset="utf-8">
<title>Mapa {x0}-{x1} / {y0}-{y1} z{z}</title>
<style>
 body{{margin:0;background:#1b1b1f;color:#ddd;font:13px system-ui,sans-serif}}
 #barra{{position:fixed;top:0;left:0;right:0;padding:8px 12px;background:#26262c;
   border-bottom:1px solid #3a3a44;display:flex;gap:16px;align-items:center;z-index:9}}
 #coord{{font:15px ui-monospace,monospace;color:#7fd1ff;min-width:260px}}
 #copiado{{color:#8ee08e;opacity:0;transition:opacity .25s}}
 #palco{{margin-top:44px;overflow:auto;height:calc(100vh - 44px)}}
 #env{{position:relative;display:inline-block}}
 img{{display:block;image-rendering:pixelated;transform-origin:0 0}}
 #cruz{{position:absolute;pointer-events:none;outline:2px solid #ff5a5a;display:none}}
 button{{background:#3a3a44;color:#ddd;border:0;padding:5px 10px;border-radius:4px;
   cursor:pointer}}
 button:hover{{background:#4a4a56}}
</style>
<div id="barra">
  <span id="coord">passe o mouse sobre o mapa</span>
  <button onclick="zoom(1.25)">+</button>
  <button onclick="zoom(0.8)">&minus;</button>
  <button onclick="zoom(0)">100%</button>
  <span id="copiado">copiado</span>
  <span style="margin-left:auto;color:#888">
    regiao x {x0}-{x1} &middot; y {y0}-{y1} &middot; z {z} &middot; {larg}x{alt} tiles
  </span>
</div>
<div id="palco"><div id="env">
  <img id="mapa" src="data:image/png;base64,{b64}">
  <div id="cruz"></div>
</div></div>
<script>
const X0={x0}, Y0={y0}, Z={z}, TILE={tile};
const img=document.getElementById('mapa'), cruz=document.getElementById('cruz');
const env=document.getElementById('env'), coord=document.getElementById('coord');
let esc=1, atual=null;

function aplica(){{
  img.style.transform='scale('+esc+')';
  env.style.width=(img.naturalWidth*esc)+'px';
  env.style.height=(img.naturalHeight*esc)+'px';
}}
function zoom(f){{ esc = f===0 ? 1 : Math.min(8,Math.max(0.1,esc*f)); aplica(); }}

env.addEventListener('mousemove', e=>{{
  const r=env.getBoundingClientRect();
  const px=(e.clientX-r.left)/esc, py=(e.clientY-r.top)/esc;
  const tx=Math.floor(px/TILE), ty=Math.floor(py/TILE);
  atual=[X0+tx, Y0+ty];
  coord.textContent='Position('+atual[0]+', '+atual[1]+', '+Z+')';
  cruz.style.display='block';
  cruz.style.left=(tx*TILE*esc)+'px';
  cruz.style.top=(ty*TILE*esc)+'px';
  cruz.style.width=(TILE*esc-4)+'px';
  cruz.style.height=(TILE*esc-4)+'px';
}});
env.addEventListener('mouseleave', ()=>{{ cruz.style.display='none'; }});
env.addEventListener('click', ()=>{{
  if(!atual) return;
  const t='Position('+atual[0]+', '+atual[1]+', '+Z+')';
  navigator.clipboard.writeText(t);
  const c=document.getElementById('copiado');
  c.style.opacity=1; setTimeout(()=>c.style.opacity=0,900);
}});
aplica();
</script>
"""


def render_minimapa(mapa: Mapa, x0, y0, x1, y1, z, attrs) -> Image.Image:
    """1 pixel por tile, cor do automapa. Aguenta regiao grande."""
    from gerar_minimapa import ITEM_VAZIO
    im = Image.new("RGB", (x1 - x0 + 1, y1 - y0 + 1), (0, 0, 0))
    px = im.load()
    for t in mapa.regiao(x0, y0, x1, y1, z):
        cor = None
        for iid in [i for i, _, _ in t.itens][::-1] + ([t.chao] if t.chao else []):
            it = attrs.get(iid, ITEM_VAZIO)
            if it.estrutura and it.cor is not None:
                cor = it.cor
                break
        if cor is None:
            continue
        # cor de 216 do automapa -> RGB
        px[t.x - x0, t.y - y0] = ((cor // 36) * 51,
                                  ((cor // 6) % 6) * 51,
                                  (cor % 6) * 51)
    return im


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("coords", nargs=5, type=int,
                   metavar=("X0", "Y0", "X1", "Y1", "Z"))
    p.add_argument("--mapa", default="data-otservbr-global/world/otservbr.otbm")
    p.add_argument("--assets")
    p.add_argument("--saida", required=True)
    p.add_argument("--modo", choices=("sprites", "minimapa"), default="sprites")
    p.add_argument("--zoom", type=int, default=2)
    p.add_argument("--dat", default=str(RAIZ / "data/items/appearances.dat"))
    # Recorte gerado pelo recortar.py vem REBASEADO para 0,0. Sem isto o
    # visualizador mostraria a coordenada do recorte, nao a do mundo -- que e'
    # justamente a que se quer ler.
    p.add_argument("--offset", nargs=2, type=int, default=[0, 0],
                   metavar=("GX", "GY"),
                   help="coordenada global do canto do recorte")
    args = p.parse_args()

    x0, y0, x1, y1, z = args.coords
    larg, alt = x1 - x0 + 1, y1 - y0 + 1
    print(f"regiao {larg}x{alt} tiles, modo {args.modo}")

    m = Mapa(args.mapa)
    if args.modo == "minimapa":
        from gerar_minimapa import ler_atributos
        im = render_minimapa(m, x0, y0, x1, y1, z, ler_atributos(Path(args.dat)))
        tile = 1
    else:
        if not args.assets:
            print("modo sprites exige --assets", file=sys.stderr)
            return 2
        from render import desenhar
        from ver_item import Assets
        im = desenhar(m, Assets(args.assets), x0, y0, x1, y1, z,
                      zoom=args.zoom, grade=False)
        tile = 32 * args.zoom

    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode()

    gx, gy = args.offset
    Path(args.saida).write_text(HTML.format(
        x0=x0 + gx, y0=y0 + gy, x1=x1 + gx, y1=y1 + gy, z=z,
        larg=larg, alt=alt, tile=tile, b64=b64), encoding="utf-8")
    mb = len(b64) * 3 / 4 / 1024 / 1024
    print(f"{args.saida}  ({mb:.1f} MB de imagem embutida)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
