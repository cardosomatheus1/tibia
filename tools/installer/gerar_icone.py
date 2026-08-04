#!/usr/bin/env python3
"""Extrai o icone (todos os tamanhos) de um .exe e salva como .ico.

O ExtractAssociatedIcon do .NET so devolve 32x32, que fica borrado em atalho de
tela grande. Aqui a gente le os recursos de icone do proprio PE (RT_GROUP_ICON +
RT_ICON) e remonta o .ico completo, com todas as resolucoes que o exe traz.

Uso: extrair o icone do client oficial (que tem o icone do Tibia) para o
instalador do client mehah usar.

    python3 tools/installer/gerar_icone.py <client.exe> <saida.ico>
"""
import struct
import sys

RT_ICON = 3
RT_GROUP_ICON = 14


def ler_pe(dados):
    e_lfanew = struct.unpack_from("<I", dados, 0x3C)[0]
    assert dados[e_lfanew:e_lfanew + 4] == b"PE\x00\x00", "nao e um PE"
    coff = e_lfanew + 4
    n_sec, = struct.unpack_from("<H", dados, coff + 2)
    tam_opt, = struct.unpack_from("<H", dados, coff + 16)
    # o Optional Header comeca logo apos o COFF File Header, que tem 20 bytes
    opt = coff + 20
    magic, = struct.unpack_from("<H", dados, opt)
    # data directory de recursos e' o indice 2 (PE32+ o array comeca em +112)
    dd = opt + (112 if magic == 0x20B else 96)
    res_rva, res_size = struct.unpack_from("<II", dados, dd + 2 * 8)

    secoes = []
    sec = opt + tam_opt
    for i in range(n_sec):
        base = sec + i * 40
        vsize, vaddr, rawsize, rawptr = struct.unpack_from("<IIII", dados, base + 8)
        secoes.append((vaddr, vsize, rawptr, rawsize))
    return res_rva, secoes


def rva_para_off(rva, secoes):
    for vaddr, vsize, rawptr, rawsize in secoes:
        if vaddr <= rva < vaddr + max(vsize, rawsize):
            return rawptr + (rva - vaddr)
    raise ValueError(f"rva {rva:#x} fora das secoes")


def entradas_dir(dados, base_res_off, dir_off):
    """Percorre uma tabela de recursos, devolve (id, offset_do_no, e_dir)."""
    n_name, n_id = struct.unpack_from("<HH", dados, dir_off + 12)
    out = []
    entrada = dir_off + 16
    for i in range(n_name + n_id):
        ident, off = struct.unpack_from("<II", dados, entrada + i * 8)
        e_dir = bool(off & 0x80000000)
        out.append((ident, base_res_off + (off & 0x7FFFFFFF), e_dir))
    return out


def coletar_recursos(dados, res_rva, secoes, tipo):
    """id do recurso -> bytes, para um tipo (RT_ICON ou RT_GROUP_ICON)."""
    base = rva_para_off(res_rva, secoes)
    recursos = {}
    for t_id, t_off, t_dir in entradas_dir(dados, base, base):
        if t_id != tipo or not t_dir:
            continue
        for name_id, name_off, name_dir in entradas_dir(dados, base, t_off):
            if not name_dir:
                continue
            for lang_id, lang_off, lang_dir in entradas_dir(dados, base, name_off):
                # folha: data entry (RVA + size)
                data_rva, size = struct.unpack_from("<II", dados, lang_off)
                off = rva_para_off(data_rva, secoes)
                recursos[name_id] = dados[off:off + size]
                break
    return recursos


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        return 1
    exe, saida = sys.argv[1], sys.argv[2]
    dados = open(exe, "rb").read()

    res_rva, secoes = ler_pe(dados)
    grupos = coletar_recursos(dados, res_rva, secoes, RT_GROUP_ICON)
    icones = coletar_recursos(dados, res_rva, secoes, RT_ICON)
    if not grupos or not icones:
        print("nenhum icone encontrado no exe", file=sys.stderr)
        return 1

    # usa o primeiro grupo de icone (o principal do app)
    grupo = grupos[min(grupos)]
    # cabecalho GRPICONDIR: reserved(2) type(2) count(2), depois GRPICONDIRENTRY
    _, tipo, count = struct.unpack_from("<HHH", grupo, 0)
    entradas = []
    dados_icones = []
    offset = 6 + count * 16  # onde comecam os dados no .ico final
    for i in range(count):
        base = 6 + i * 14
        w, h, cores, _r, planos, bpp, tam, ordinal = struct.unpack_from(
            "<BBBBHHIH", grupo, base)
        img = icones.get(ordinal)
        if img is None:
            continue
        # ICONDIRENTRY (.ico): igual, mas com offset(4) no lugar do ordinal(2)
        entradas.append(struct.pack("<BBBBHHII", w, h, cores, 0, planos, bpp,
                                    len(img), offset))
        dados_icones.append(img)
        offset += len(img)

    with open(saida, "wb") as f:
        f.write(struct.pack("<HHH", 0, 1, len(entradas)))
        for e in entradas:
            f.write(e)
        for d in dados_icones:
            f.write(d)

    print(f"{len(entradas)} tamanhos -> {saida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
