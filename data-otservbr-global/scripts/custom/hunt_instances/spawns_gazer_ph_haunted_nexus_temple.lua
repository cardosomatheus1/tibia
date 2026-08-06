-- Pontos de spawn de Gazer PH - Haunted Nexus (Temple).
-- GERADO POR tools/mapa/gerar_instancia.py -- NAO EDITE A MAO.
--
-- x/y sao RELATIVOS ao recorte e z e' ABSOLUTO, igual ao .otbm: a
-- posicao real e' origem do slot + isto. Coordenada absoluta aqui
-- somada ao offset do slot estouraria o uint16 (spec 3.1).
--
-- Bosses ja ficaram de fora na geracao do JSON, e o instance_spawns
-- barra de novo na hora de nascer.

HuntInstanceSpawns = HuntInstanceSpawns or {}

HuntInstanceSpawns["gazer_ph_haunted_nexus_temple"] = {
	{ nome = "Thanatursus", x = 58, y = 31, z = 8, respawnMs = 90000 },
	{ nome = "Gazer Spectre", x = 64, y = 29, z = 8, respawnMs = 90000 },
	{ nome = "Thanatursus", x = 77, y = 49, z = 8, respawnMs = 90000 },
	{ nome = "Gazer Spectre", x = 97, y = 53, z = 8, respawnMs = 90000 },
	{ nome = "Gazer Spectre", x = 103, y = 53, z = 8, respawnMs = 90000 },
	{ nome = "Gazer Spectre", x = 137, y = 53, z = 8, respawnMs = 90000 },
	{ nome = "Gazer Spectre", x = 142, y = 53, z = 8, respawnMs = 90000 },
	{ nome = "Gazer Spectre", x = 88, y = 54, z = 8, respawnMs = 90000 },
	{ nome = "Gazer Spectre", x = 85, y = 58, z = 8, respawnMs = 90000 },
	{ nome = "Gazer Spectre", x = 148, y = 58, z = 8, respawnMs = 90000 },
	{ nome = "Gazer Spectre", x = 115, y = 60, z = 8, respawnMs = 90000 },
	{ nome = "Gazer Spectre", x = 119, y = 65, z = 8, respawnMs = 90000 },
	{ nome = "Gazer Spectre", x = 131, y = 60, z = 8, respawnMs = 90000 },
	{ nome = "Gazer Spectre", x = 128, y = 64, z = 8, respawnMs = 90000 },
	{ nome = "Gazer Spectre", x = 105, y = 64, z = 8, respawnMs = 90000 },
	{ nome = "Gazer Spectre", x = 108, y = 67, z = 8, respawnMs = 90000 },
	{ nome = "Gazer Spectre", x = 87, y = 63, z = 8, respawnMs = 90000 },
	{ nome = "Gazer Spectre", x = 151, y = 65, z = 8, respawnMs = 90000 },
	{ nome = "Gazer Spectre", x = 122, y = 69, z = 8, respawnMs = 90000 },
	{ nome = "Gazer Spectre", x = 139, y = 70, z = 8, respawnMs = 90000 },
	{ nome = "Gazer Spectre", x = 86, y = 71, z = 8, respawnMs = 90000 },
	{ nome = "Gazer Spectre", x = 84, y = 75, z = 8, respawnMs = 90000 },
	{ nome = "Gazer Spectre", x = 146, y = 70, z = 8, respawnMs = 90000 },
	{ nome = "Gazer Spectre", x = 125, y = 75, z = 8, respawnMs = 90000 },
	{ nome = "Gazer Spectre", x = 123, y = 80, z = 8, respawnMs = 90000 },
	{ nome = "Gazer Spectre", x = 102, y = 77, z = 8, respawnMs = 90000 },
	{ nome = "Gazer Spectre", x = 99, y = 81, z = 8, respawnMs = 90000 },
	{ nome = "Gazer Spectre", x = 86, y = 82, z = 8, respawnMs = 90000 },
	{ nome = "Gazer Spectre", x = 112, y = 83, z = 8, respawnMs = 90000 },
}
