-- Gazer PH - Haunted Nexus (Temple) -- hunt revisada #3.
-- GERADO POR tools/mapa/gerar_instancia.py. Os numeros vem do JSON
-- conferido no mapeador, nao de estimativa.

HuntInstances = HuntInstances or {}

HuntInstances.gazerPhHauntedNexusTemple = {
	slug = "gazer_ph_haunted_nexus_temple",
	nome = "Gazer PH - Haunted Nexus (Temple)",
	enabled = true,

	template = {
		caminho = "/world/hunt_instances/gazer_ph_haunted_nexus_temple_instance.otbm",
		origem = Position(32565, 32592, 0),
		largura = 180,
		altura = 106,
		andares = { 7, 8, 9 },
	},

	-- A hunt dentro do recorte. O resto e' margem, que existe para ser
	-- VISTA: o beforeLeave para o jogador na borda da hunt, e o que ele
	-- enxerga alem disso e' terreno de verdade, nao o vazio.
	margemRecorte = 16,
	fronteira = { x0 = 16, y0 = 16, x1 = 163, y1 = 89 },

	-- Os andares que SAO a hunt. O recorte tem mais: inclui o andar por
	-- onde se sai, para a escada existir. Pisar nele e' sair da hunt, e a
	-- zona nao o cobre justamente para o dialogo disparar la'.
	andaresHunt = { 7, 8, 9 },

	slotOrigens = {
		Position(36864, 39936, 0),
		Position(37376, 39936, 0),
		Position(37888, 39936, 0),
		Position(38400, 39936, 0),
		Position(38912, 39936, 0),
		Position(39424, 39936, 0),
	},

	-- Onde o jogador aparece, relativo ao slot. Sai do `inicio` marcado
	-- no mapeador; os vizinhos foram conferidos como pisaveis.
	entradasRelativas = {
		{ x = 107, y = 54, z = 7 },
		{ x = 108, y = 54, z = 7 },
		{ x = 108, y = 55, z = 7 },
	},

	seletor = {
		posicao = Position(32670, 32653, 7),
		itemId = 2199,
		actionId = 65004,
	},

	-- Tiles onde os membros da party sobem para consentir: presenca
	-- fisica e' o consentimento, porque a ModalWindow morre ao andar.
	playerPositions = {
		Position(32670, 32652, 7),
		Position(32669, 32653, 7),
		Position(32669, 32652, 7),
		Position(32669, 32654, 7),
	},

	retornoGlobal = Position(32670, 32652, 7),
	retornoEmergencia = Position(32369, 32241, 7),   -- revisar: nao e' o templo mais proximo
	raioRetorno = 2,

	maximoSlots = 6,

	duracaoMaximaMinutos = 180,
	graceVazioMinutos = 3,
	cooldownMinutos = 5,

	permiteSolo = true,
	permiteParty = true,
	minimoMembrosParty = 2,
	maximoMembros = 5,
	mesmoAndar = true,
	exigeTodosOsMembros = true,

	permiteEntradaTardia = false,
	permiteReentrada = false,
	mantemAposSaidaDoLider = true,
	mantemAposPartyDesfeita = true,

	multiplicadorExp = 1.0,
	multiplicadorLoot = 1.0,
	multiplicadorSpawn = 1.0,

	skullsBloqueadas = { SKULL_WHITE, SKULL_RED, SKULL_BLACK },
	bloqueiaComPvpLock = true,
	removeItensNoChaoAoLimpar = true,
}
