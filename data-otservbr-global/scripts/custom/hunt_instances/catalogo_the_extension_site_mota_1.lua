-- The Extension Site - MOTA -1 -- hunt revisada #7.
-- GERADO POR tools/mapa/gerar_instancia.py. Os numeros vem do JSON
-- conferido no mapeador, nao de estimativa.

HuntInstances = HuntInstances or {}

HuntInstances.theExtensionSiteMota1 = {
	slug = "the_extension_site_mota_1",
	nome = "The Extension Site - MOTA -1",
	enabled = true,

	template = {
		caminho = "/world/hunt_instances/the_extension_site_mota_1_instance.otbm",
		origem = Position(33186, 31987, 0),
		largura = 111,
		altura = 141,
		andares = { 8 },
	},

	-- A hunt dentro do recorte. O resto e' margem, que existe para ser
	-- VISTA: o beforeLeave para o jogador na borda da hunt, e o que ele
	-- enxerga alem disso e' terreno de verdade, nao o vazio.
	margemRecorte = 16,
	fronteira = { x0 = 16, y0 = 16, x1 = 94, y1 = 124 },

	-- Os andares que SAO a hunt. O recorte tem mais: inclui o andar por
	-- onde se sai, para a escada existir. Pisar nele e' sair da hunt, e a
	-- zona nao o cobre justamente para o dialogo disparar la'.
	andaresHunt = { 8 },

	slotOrigens = {
		Position(36864, 44032, 0),
		Position(37376, 44032, 0),
		Position(37888, 44032, 0),
		Position(38400, 44032, 0),
		Position(38912, 44032, 0),
		Position(39424, 44032, 0),
	},

	-- Onde o jogador aparece, relativo ao slot. Sai do `inicio` marcado
	-- no mapeador; os vizinhos foram conferidos como pisaveis.
	entradasRelativas = {
		{ x = 60, y = 109, z = 8 },
		{ x = 60, y = 108, z = 8 },
		{ x = 60, y = 110, z = 8 },
		{ x = 59, y = 109, z = 8 },
		{ x = 61, y = 109, z = 8 },
	},

	seletor = {
		posicao = Position(33247, 32112, 8),
		itemId = 2199,
		actionId = 65008,
	},

	-- Tiles onde os membros da party sobem para consentir: presenca
	-- fisica e' o consentimento, porque a ModalWindow morre ao andar.
	playerPositions = {
		Position(33247, 32113, 8),
		Position(33246, 32112, 8),
		Position(33246, 32111, 8),
		Position(33246, 32113, 8),
		Position(33248, 32113, 8),
	},

	retornoGlobal = Position(33247, 32113, 8),
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
