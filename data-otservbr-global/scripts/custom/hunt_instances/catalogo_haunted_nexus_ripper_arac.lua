-- Haunted Nexus - Ripper+Arac -- hunt revisada #2.
-- GERADO POR tools/mapa/gerar_instancia.py. Os numeros vem do JSON
-- conferido no mapeador, nao de estimativa.

HuntInstances = HuntInstances or {}

HuntInstances.hauntedNexusRipperArac = {
	slug = "haunted_nexus_ripper_arac",
	nome = "Haunted Nexus - Ripper+Arac",
	enabled = true,

	template = {
		caminho = "/world/hunt_instances/haunted_nexus_ripper_arac_instance.otbm",
		origem = Position(32659, 32207, 0),
		largura = 123,
		altura = 102,
		andares = { 8, 9, 10 },
	},

	-- A hunt dentro do recorte. O resto e' margem, que existe para ser
	-- VISTA: o beforeLeave para o jogador na borda da hunt, e o que ele
	-- enxerga alem disso e' terreno de verdade, nao o vazio.
	margemRecorte = 16,
	fronteira = { x0 = 16, y0 = 16, x1 = 106, y1 = 85 },

	-- Os andares que SAO a hunt. O recorte tem mais: inclui o andar por
	-- onde se sai, para a escada existir. Pisar nele e' sair da hunt, e a
	-- zona nao o cobre justamente para o dialogo disparar la'.
	andaresHunt = { 8, 9, 10 },

	slotOrigens = {
		Position(36864, 38912, 0),
		Position(37376, 38912, 0),
		Position(37888, 38912, 0),
		Position(38400, 38912, 0),
		Position(38912, 38912, 0),
		Position(39424, 38912, 0),
	},

	-- Onde o jogador aparece, relativo ao slot. Sai do `inicio` marcado
	-- no mapeador; os vizinhos foram conferidos como pisaveis.
	entradasRelativas = {
		{ x = 39, y = 36, z = 9 },
		{ x = 39, y = 37, z = 9 },
		{ x = 38, y = 36, z = 9 },
		{ x = 40, y = 36, z = 9 },
		{ x = 38, y = 37, z = 9 },
	},

	seletor = {
		posicao = Position(32698, 32244, 8),
		itemId = 2199,
		actionId = 65003,
	},

	-- Tiles onde os membros da party sobem para consentir: presenca
	-- fisica e' o consentimento, porque a ModalWindow morre ao andar.
	playerPositions = {
		Position(32698, 32245, 8),
		Position(32699, 32244, 8),
		Position(32699, 32245, 8),
	},

	retornoGlobal = Position(32698, 32245, 8),
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
