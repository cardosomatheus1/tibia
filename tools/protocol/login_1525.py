#!/usr/bin/env python3
"""Login com protocolo Tibia 15.25 no Canary — handshake completo, sem client grafico."""
import socket, struct, os, subprocess, zlib, time
from collections import Counter

HOST, PORT, VERSION = "127.0.0.1", 7172, 1525
SESSION, CHAR = "@god\ngod", "Claude"     # authType=password => session key = email\nsenha
M32 = 0xFFFFFFFF; DELTA = 0x9E3779B9

mod = subprocess.run(["openssl", "rsa", "-in", "/home/user/tibia/key.pem", "-noout", "-modulus"],
                     capture_output=True, text=True).stdout.strip()
N = int(mod.split("=")[1], 16); E = 65537

def xtea_decrypt(data, k):
    out = bytearray()
    for i in range(0, len(data) - len(data) % 8, 8):
        v0, v1 = struct.unpack_from("<II", data, i); s = (DELTA * 32) & M32
        for _ in range(32):
            v1 = (v1 - ((((v0 << 4) & M32) ^ (v0 >> 5)) + v0 ^ (s + k[(s >> 11) & 3]))) & M32
            s = (s - DELTA) & M32
            v0 = (v0 - ((((v1 << 4) & M32) ^ (v1 >> 5)) + v1 ^ (s + k[s & 3]))) & M32
        out += struct.pack("<II", v0, v1)
    return bytes(out)

def s_str(t):
    b = t.encode("latin1"); return struct.pack("<H", len(b)) + b

def recv_n(s, n):
    b = b""
    while len(b) < n:
        c = s.recv(n - len(b))
        if not c: break
        b += c
    return b

print(f"=== LOGIN COM PROTOCOLO TIBIA {VERSION//100}.{VERSION%100} ===\n")
s = socket.create_connection((HOST, PORT), timeout=20)

blocos = struct.unpack("<H", recv_n(s, 2))[0]
chal = recv_n(s, blocos * 8 + 4)
ts, rnd = struct.unpack_from("<IB", chal, 6)
print(f"[1] challenge do servidor: timestamp={ts} random={rnd}")

xtea = [int.from_bytes(os.urandom(4), "little") for _ in range(4)]
inner  = b"\x00" + b"".join(struct.pack("<I", k) for k in xtea) + b"\x00"
inner += s_str(SESSION) + s_str(CHAR) + struct.pack("<IB", ts, rnd) + struct.pack("<H", 0)
inner += b"\x00" * (128 - len(inner))
rsa_block = pow(int.from_bytes(inner, "big"), E, N).to_bytes(128, "big")
print(f"[2] chave XTEA cifrada com o RSA do servidor ({N.bit_length()} bits)")

body  = struct.pack("<H", 2)         # OS
body += struct.pack("<H", VERSION)   # protocolo
body += struct.pack("<H", VERSION)   # version field
body += struct.pack("<I", VERSION)   # client version u32
body += s_str("15.25") + s_str("") + b"\x00"
body += rsa_block
if len(body) % 8:
    body += b"\x00" * (8 - len(body) % 8)
s.sendall(struct.pack("<H", len(body) // 8) + struct.pack("<I", zlib.adler32(body) & M32) + body)
print(f"[3] login enviado: personagem '{CHAR}'")

time.sleep(4)
s.setblocking(False)
buf = b""
try:
    while True:
        c = s.recv(65535)
        if not c: break
        buf += c
except Exception:
    pass
s.close()
print(f"[4] servidor enviou {len(buf)} bytes\n")

pos = 0; pacotes = 0; ops = Counter(); textos = []
while pos + 2 <= len(buf):
    blocos = struct.unpack_from("<H", buf, pos)[0]
    fim = pos + 2 + blocos * 8 + 4
    corpo = buf[pos + 2 + 4:fim]
    if len(corpo) < 8: break
    dec = xtea_decrypt(corpo, xtea)
    ln = struct.unpack_from("<H", dec, 0)[0]
    payload = dec[2:2 + ln] if 0 < ln <= len(dec) - 2 else dec[2:]
    pacotes += 1
    if payload:
        ops[payload[0]] += 1
        legivel = "".join(chr(b) if 32 <= b < 127 else "" for b in payload)
        for palavra in ("Welcome", "Thais", "OTServBR"):
            if palavra in legivel:
                textos.append(legivel[max(0, legivel.find(palavra) - 5):legivel.find(palavra) + 60])
    pos = fim

print(f"[5] {pacotes} pacotes decodificados")
NOMES = {0x17: "login OK (id do jogador, batida do servidor)", 0x0A: "id do jogador",
         0x64: "descricao do mapa", 0xA0: "status do jogador", 0xA1: "skills",
         0x82: "luz do mundo", 0x8D: "luz da criatura", 0x83: "efeito magico",
         0x78: "inventario", 0x79: "inventario vazio", 0xB4: "mensagem de texto",
         0xAD: "canal privado", 0x9F: "dados do jogador", 0x6D: "movimento",
         0xF3: "capacidades do cliente", 0xDD: "marcador no mapa", 0x32: "features do protocolo"}
print("\n[6] opcodes recebidos:")
for op, qtd in ops.most_common(14):
    print(f"    0x{op:02X} x{qtd:<3} {NOMES.get(op, '')}")
if textos:
    print("\n[7] textos no fluxo:")
    for t in dict.fromkeys(textos):
        print(f"    {t}")
