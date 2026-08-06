-- Brain Grounds - Jakundaf - -1-2-3 -- hunt revisada #1.
-- GERADO POR tools/mapa/gerar_instancia.py. Os numeros vem do JSON
-- conferido no mapeador, nao de estimativa.

HuntInstances = HuntInstances or {}

HuntInstances.brainGroundsJakundaf123 = {
	slug = "brain_grounds_jakundaf_1_2_3",
	nome = "Brain Grounds - Jakundaf - -1-2-3",
	enabled = true,

	template = {
		caminho = "/world/hunt_instances/brain_grounds_jakundaf_1_2_3_instance.otbm",
		origem = Position(31882, 32272, 0),
		largura = 155,
		altura = 109,
		andares = { 7, 8, 9, 10 },
	},

	-- A hunt dentro do recorte. O resto e' margem, que existe para ser
	-- VISTA: o beforeLeave para o jogador na borda da hunt, e o que ele
	-- enxerga alem disso e' terreno de verdade, nao o vazio.
	margemRecorte = 16,
	fronteira = { x0 = 16, y0 = 16, x1 = 138, y1 = 92 },

	-- Os andares que SAO a hunt. O recorte tem mais: inclui o andar por
	-- onde se sai, para a escada existir. Pisar nele e' sair da hunt, e a
	-- zona nao o cobre justamente para o dialogo disparar la'.
	andaresHunt = { 8, 9, 10 },

	slotOrigens = {
		Position(36864, 37888, 0),
		Position(37376, 37888, 0),
		Position(37888, 37888, 0),
		Position(38400, 37888, 0),
		Position(38912, 37888, 0),
		Position(39424, 37888, 0),
	},

	-- Onde o jogador aparece, relativo ao slot. Sai do `inicio` marcado
	-- no mapeador; os vizinhos foram conferidos como pisaveis.
	entradasRelativas = {
		{ x = 30, y = 85, z = 8 },
		{ x = 30, y = 84, z = 8 },
		{ x = 30, y = 86, z = 8 },
		{ x = 31, y = 85, z = 8 },
		{ x = 29, y = 84, z = 8 },
	},

	seletor = {
		posicao = Position(32623, 32077, 7),
		itemId = 2199,
		actionId = 65002,
	},

	-- Tiles onde os membros da party sobem para consentir: presenca
	-- fisica e' o consentimento, porque a ModalWindow morre ao andar.
	playerPositions = {
		Position(32623, 32078, 7),
		Position(32624, 32077, 7),
		Position(32624, 32076, 7),
		Position(32624, 32078, 7),
	},

	retornoGlobal = Position(32623, 32078, 7),
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
