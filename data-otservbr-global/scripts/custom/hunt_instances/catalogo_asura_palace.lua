-- Asura Palace -- hunt revisada #6.
-- GERADO POR tools/mapa/gerar_instancia.py. Os numeros vem do JSON
-- conferido no mapeador, nao de estimativa.

HuntInstances = HuntInstances or {}

HuntInstances.asuraPalace = {
	slug = "asura_palace",
	nome = "Asura Palace",
	enabled = true,

	template = {
		caminho = "/world/hunt_instances/asura_palace_instance.otbm",
		origem = Position(32904, 32648, 0),
		largura = 88,
		altura = 62,
		andares = { 0, 1, 2, 3, 4, 5, 6, 7, 8 },
	},

	-- A hunt dentro do recorte. O resto e' margem, que existe para ser
	-- VISTA: o beforeLeave para o jogador na borda da hunt, e o que ele
	-- enxerga alem disso e' terreno de verdade, nao o vazio.
	margemRecorte = 16,
	fronteira = { x0 = 16, y0 = 16, x1 = 71, y1 = 45 },

	-- Os andares que SAO a hunt. O recorte tem mais: inclui o andar por
	-- onde se sai, para a escada existir. Pisar nele e' sair da hunt, e a
	-- zona nao o cobre justamente para o dialogo disparar la'.
	andaresHunt = { 0, 1, 2, 3, 4, 5, 6, 7, 8 },

	slotOrigens = {
		Position(36864, 43008, 0),
		Position(37376, 43008, 0),
		Position(37888, 43008, 0),
		Position(38400, 43008, 0),
		Position(38912, 43008, 0),
		Position(39424, 43008, 0),
	},

	-- Onde o jogador aparece, relativo ao slot. Sai do `inicio` marcado
	-- no mapeador; os vizinhos foram conferidos como pisaveis.
	entradasRelativas = {
		{ x = 44, y = 40, z = 6 },
		{ x = 44, y = 39, z = 6 },
		{ x = 44, y = 41, z = 6 },
		{ x = 45, y = 40, z = 6 },
		{ x = 43, y = 39, z = 6 },
	},

	seletor = {
		posicao = Position(32950, 32689, 7),
		itemId = 2199,
		actionId = 65007,
	},

	-- Tiles onde os membros da party sobem para consentir: presenca
	-- fisica e' o consentimento, porque a ModalWindow morre ao andar.
	playerPositions = {
		Position(32950, 32690, 7),
		Position(32949, 32689, 7),
		Position(32951, 32689, 7),
		Position(32949, 32690, 7),
		Position(32951, 32690, 7),
	},

	retornoGlobal = Position(32950, 32690, 7),
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
