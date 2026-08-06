-- Falcon Bastion -- hunt revisada #8.
-- GERADO POR tools/mapa/gerar_instancia.py. Os numeros vem do JSON
-- conferido no mapeador, nao de estimativa.

HuntInstances = HuntInstances or {}

HuntInstances.falconBastion = {
	slug = "falcon_bastion",
	nome = "Falcon Bastion",
	enabled = true,

	template = {
		caminho = "/world/hunt_instances/falcon_bastion_instance.otbm",
		origem = Position(33264, 31247, 0),
		largura = 134,
		altura = 134,
		andares = { 2, 3, 4, 5, 6, 7, 8, 9 },
	},

	-- A hunt dentro do recorte. O resto e' margem, que existe para ser
	-- VISTA: o beforeLeave para o jogador na borda da hunt, e o que ele
	-- enxerga alem disso e' terreno de verdade, nao o vazio.
	margemRecorte = 16,
	fronteira = { x0 = 16, y0 = 16, x1 = 117, y1 = 117 },

	-- Os andares que SAO a hunt. O recorte tem mais: inclui o andar por
	-- onde se sai, para a escada existir. Pisar nele e' sair da hunt, e a
	-- zona nao o cobre justamente para o dialogo disparar la'.
	andaresHunt = { 2, 3, 4, 5, 6, 7, 8, 9 },

	slotOrigens = {
		Position(36864, 45056, 0),
		Position(37376, 45056, 0),
		Position(37888, 45056, 0),
		Position(38400, 45056, 0),
		Position(38912, 45056, 0),
		Position(39424, 45056, 0),
	},

	-- Onde o jogador aparece, relativo ao slot. Sai do `inicio` marcado
	-- no mapeador; os vizinhos foram conferidos como pisaveis.
	entradasRelativas = {
		{ x = 89, y = 103, z = 7 },
		{ x = 89, y = 102, z = 7 },
		{ x = 89, y = 104, z = 7 },
		{ x = 88, y = 103, z = 7 },
		{ x = 90, y = 103, z = 7 },
	},

	seletor = {
		posicao = Position(33346, 31346, 7),
		itemId = 2199,
		actionId = 65009,
	},

	-- Tiles onde os membros da party sobem para consentir: presenca
	-- fisica e' o consentimento, porque a ModalWindow morre ao andar.
	playerPositions = {
		Position(33346, 31345, 7),
		Position(33346, 31347, 7),
		Position(33345, 31346, 7),
		Position(33347, 31346, 7),
		Position(33345, 31345, 7),
	},

	retornoGlobal = Position(33346, 31345, 7),
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
