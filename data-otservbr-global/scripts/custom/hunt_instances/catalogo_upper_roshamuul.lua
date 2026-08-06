-- Upper Roshamuul -- hunt revisada #5.
-- GERADO POR tools/mapa/gerar_instancia.py. Os numeros vem do JSON
-- conferido no mapeador, nao de estimativa.

HuntInstances = HuntInstances or {}

HuntInstances.upperRoshamuul = {
	slug = "upper_roshamuul",
	nome = "Upper Roshamuul",
	enabled = true,

	template = {
		caminho = "/world/hunt_instances/upper_roshamuul_instance.otbm",
		origem = Position(33472, 32418, 0),
		largura = 282,
		altura = 157,
		andares = { 6, 7 },
	},

	-- A hunt dentro do recorte. O resto e' margem, que existe para ser
	-- VISTA: o beforeLeave para o jogador na borda da hunt, e o que ele
	-- enxerga alem disso e' terreno de verdade, nao o vazio.
	margemRecorte = 16,
	fronteira = { x0 = 16, y0 = 16, x1 = 265, y1 = 140 },

	-- Os andares que SAO a hunt. O recorte tem mais: inclui o andar por
	-- onde se sai, para a escada existir. Pisar nele e' sair da hunt, e a
	-- zona nao o cobre justamente para o dialogo disparar la'.
	andaresHunt = { 6, 7 },

	slotOrigens = {
		Position(36864, 41984, 0),
		Position(37376, 41984, 0),
		Position(37888, 41984, 0),
		Position(38400, 41984, 0),
		Position(38912, 41984, 0),
		Position(39424, 41984, 0),
	},

	-- Onde o jogador aparece, relativo ao slot. Sai do `inicio` marcado
	-- no mapeador; os vizinhos foram conferidos como pisaveis.
	entradasRelativas = {
		{ x = 66, y = 56, z = 7 },
		{ x = 66, y = 55, z = 7 },
		{ x = 66, y = 57, z = 7 },
		{ x = 65, y = 56, z = 7 },
		{ x = 67, y = 56, z = 7 },
	},

	seletor = {
		posicao = Position(33541, 32479, 6),
		itemId = 2199,
		actionId = 65006,
	},

	-- Tiles onde os membros da party sobem para consentir: presenca
	-- fisica e' o consentimento, porque a ModalWindow morre ao andar.
	playerPositions = {
		Position(33540, 32479, 6),
		Position(33540, 32478, 6),
		Position(33540, 32480, 6),
	},

	retornoGlobal = Position(33540, 32479, 6),
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
