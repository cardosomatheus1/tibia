#!/usr/bin/env python3
"""Servico de login HTTP que o client Tibia 12+/15 usa antes de entrar no jogo.
Com authType=password no Canary, a sessionkey e' simplesmente "email\\nsenha"."""
import json, http.server, socketserver, sys

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 80
IP, GAME_PORT = "127.0.0.1", 7998
LOG = "/tmp/claude-0/-home-user-tibia/1272ce98-8213-5673-9d72-675533d8c08a/scratchpad/loginweb.log"

CHARS = [("Claude", 100, "Sorcerer"), ("GOD", 2, "None"), ("Sorcerer Sample", 8, "Sorcerer")]

def resposta(email, senha):
    return {
        "session": {
            "sessionkey": f"{email}\n{senha}",
            "lastlogintime": 0, "ispremium": True, "premiumuntil": 2145916800,
            "status": "active", "returnernotification": False, "showrewardnews": False,
            "isreturner": False, "fpstracking": False, "optiontracking": False,
            "tournamentticketpurchasestate": 0, "emailcoderequest": False,
        },
        "playdata": {
            "worlds": [{
                "id": 0, "name": "OTServBR-Global",
                "externaladdress": IP, "externalport": GAME_PORT,
                "externaladdressprotected": IP, "externalportprotected": GAME_PORT,
                "externaladdressunprotected": IP, "externalportunprotected": GAME_PORT,
                "previewstate": 0, "location": "BRA", "anticheatprotection": False,
                "pvptype": 0, "istournamentworld": False, "restrictedstore": False,
                "currenttournamentphase": 2,
            }],
            "characters": [{
                "worldid": 0, "name": nome, "level": lvl, "vocation": voc,
                "ismale": True, "outfitid": 128, "headcolor": 78, "torsocolor": 106,
                "legscolor": 116, "detailcolor": 95, "addonsflags": 0,
                "ishidden": False, "istournamentparticipant": False,
                "tutorial": False,
                "ismaincharacter": nome == "Claude", "dailyrewardstate": 0,
                "remainingdailytournamentplaytime": 0,
            } for nome, lvl, voc in CHARS],
        },
    }

class H(http.server.BaseHTTPRequestHandler):
    def _envia(self, obj):
        b = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        corpo = self.rfile.read(n).decode("utf-8", "replace")
        with open(LOG, "a") as f:
            f.write(f"POST {self.path}\n{corpo}\n\n")
        try:
            d = json.loads(corpo)
        except Exception:
            d = {}
        tipo = d.get("type", "login")
        if tipo == "cacheinfo":
            self._envia({"playersonline": 1, "twitchstreams": 0, "twitchviewer": 0, "gamingyoutubestreams": 0, "gamingyoutubeviewer": 0})
            return
        email = d.get("email") or d.get("accountname") or "@god"
        senha = d.get("password", "god")
        self._envia(resposta(email, senha))

    def do_GET(self):
        self._envia({"status": "ok"})

    def log_message(self, *a):
        pass

socketserver.TCPServer.allow_reuse_address = True
print(f"servico de login em http://127.0.0.1:{PORT}/login.php")
socketserver.TCPServer(("0.0.0.0", PORT), H).serve_forever()
