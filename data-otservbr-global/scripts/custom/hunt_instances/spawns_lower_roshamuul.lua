-- Pontos de spawn de Lower Roshamuul.
-- GERADO POR tools/mapa/gerar_instancia.py -- NAO EDITE A MAO.
--
-- x/y sao RELATIVOS ao recorte e z e' ABSOLUTO, igual ao .otbm: a
-- posicao real e' origem do slot + isto. Coordenada absoluta aqui
-- somada ao offset do slot estouraria o uint16 (spec 3.1).
--
-- Bosses ja ficaram de fora na geracao do JSON, e o instance_spawns
-- barra de novo na hora de nascer.

HuntInstanceSpawns = HuntInstanceSpawns or {}

HuntInstanceSpawns["lower_roshamuul"] = {
	{ nome = "Frazzlemaw", x = 62, y = 25, z = 5, respawnMs = 90000 },
	{ nome = "Frazzlemaw", x = 63, y = 27, z = 5, respawnMs = 90000 },
	{ nome = "Frazzlemaw", x = 66, y = 24, z = 5, respawnMs = 90000 },
	{ nome = "Frazzlemaw", x = 35, y = 35, z = 5, respawnMs = 90000 },
	{ nome = "Frazzlemaw", x = 38, y = 33, z = 5, respawnMs = 90000 },
	{ nome = "Frazzlemaw", x = 37, y = 34, z = 5, respawnMs = 90000 },
	{ nome = "Frazzlemaw", x = 48, y = 33, z = 5, respawnMs = 90000 },
	{ nome = "Frazzlemaw", x = 51, y = 34, z = 5, respawnMs = 90000 },
	{ nome = "Frazzlemaw", x = 34, y = 47, z = 6, respawnMs = 90000 },
	{ nome = "Frazzlemaw", x = 33, y = 51, z = 6, respawnMs = 90000 },
	{ nome = "Frazzlemaw", x = 38, y = 55, z = 6, respawnMs = 90000 },
	{ nome = "Frazzlemaw", x = 29, y = 57, z = 6, respawnMs = 90000 },
	{ nome = "Frazzlemaw", x = 90, y = 57, z = 6, respawnMs = 90000 },
	{ nome = "Frazzlemaw", x = 45, y = 59, z = 6, respawnMs = 90000 },
	{ nome = "Frazzlemaw", x = 38, y = 59, z = 6, respawnMs = 90000 },
	{ nome = "Frazzlemaw", x = 54, y = 62, z = 6, respawnMs = 90000 },
	{ nome = "Frazzlemaw", x = 67, y = 58, z = 6, respawnMs = 90000 },
	{ nome = "Silencer", x = 66, y = 62, z = 6, respawnMs = 90000 },
	{ nome = "Frazzlemaw", x = 32, y = 63, z = 6, respawnMs = 90000 },
	{ nome = "Frazzlemaw", x = 43, y = 65, z = 6, respawnMs = 90000 },
	{ nome = "Frazzlemaw", x = 93, y = 65, z = 6, respawnMs = 90000 },
	{ nome = "Frazzlemaw", x = 95, y = 66, z = 6, respawnMs = 90000 },
	{ nome = "Frazzlemaw", x = 49, y = 67, z = 6, respawnMs = 90000 },
	{ nome = "Frazzlemaw", x = 56, y = 67, z = 6, respawnMs = 90000 },
	{ nome = "Frazzlemaw", x = 68, y = 68, z = 6, respawnMs = 90000 },
	{ nome = "Frazzlemaw", x = 75, y = 67, z = 6, respawnMs = 90000 },
	{ nome = "Frazzlemaw", x = 76, y = 68, z = 6, respawnMs = 90000 },
	{ nome = "Frazzlemaw", x = 101, y = 70, z = 6, respawnMs = 90000 },
	{ nome = "Frazzlemaw", x = 104, y = 70, z = 6, respawnMs = 90000 },
	{ nome = "Frazzlemaw", x = 108, y = 77, z = 6, respawnMs = 90000 },
	{ nome = "Frazzlemaw", x = 107, y = 79, z = 6, respawnMs = 90000 },
	{ nome = "Silencer", x = 66, y = 79, z = 6, respawnMs = 90000 },
}
