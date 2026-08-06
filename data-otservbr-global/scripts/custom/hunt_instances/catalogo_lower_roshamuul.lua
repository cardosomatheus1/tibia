-- Lower Roshamuul -- hunt revisada #4.
-- GERADO POR tools/mapa/gerar_instancia.py. Os numeros vem do JSON
-- conferido no mapeador, nao de estimativa.

HuntInstances = HuntInstances or {}

HuntInstances.lowerRoshamuul = {
	slug = "lower_roshamuul",
	nome = "Lower Roshamuul",
	enabled = true,

	template = {
		caminho = "/world/hunt_instances/lower_roshamuul_instance.otbm",
		origem = Position(33472, 32464, 0),
		largura = 133,
		altura = 104,
		andares = { 5, 6, 7 },
	},

	-- A hunt dentro do recorte. O resto e' margem, que existe para ser
	-- VISTA: o beforeLeave para o jogador na borda da hunt, e o que ele
	-- enxerga alem disso e' terreno de verdade, nao o vazio.
	margemRecorte = 16,
	fronteira = { x0 = 16, y0 = 16, x1 = 116, y1 = 87 },

	-- Os andares que SAO a hunt. O recorte tem mais: inclui o andar por
	-- onde se sai, para a escada existir. Pisar nele e' sair da hunt, e a
	-- zona nao o cobre justamente para o dialogo disparar la'.
	andaresHunt = { 5, 6 },

	slotOrigens = {
		Position(36864, 40960, 0),
		Position(37376, 40960, 0),
		Position(37888, 40960, 0),
		Position(38400, 40960, 0),
		Position(38912, 40960, 0),
		Position(39424, 40960, 0),
	},

	-- Onde o jogador aparece, relativo ao slot. Sai do `inicio` marcado
	-- no mapeador; os vizinhos foram conferidos como pisaveis.
	entradasRelativas = {
		{ x = 51, y = 83, z = 6 },
		{ x = 51, y = 82, z = 6 },
		{ x = 51, y = 84, z = 6 },
		{ x = 52, y = 83, z = 6 },
		{ x = 52, y = 82, z = 6 },
	},

	seletor = {
		posicao = Position(33521, 32548, 7),
		itemId = 2199,
		actionId = 65005,
	},

	-- Tiles onde os membros da party sobem para consentir: presenca
	-- fisica e' o consentimento, porque a ModalWindow morre ao andar.
	playerPositions = {
		Position(33521, 32549, 7),
		Position(33520, 32548, 7),
		Position(33522, 32548, 7),
		Position(33520, 32549, 7),
		Position(33522, 32549, 7),
	},

	retornoGlobal = Position(33521, 32549, 7),
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
