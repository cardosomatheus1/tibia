-- Hunt instanciada -- catalogo de hunts.
-- Spec: docs/spec_hunt_instanciada_v2.md
--
-- Tudo aqui foi MEDIDO no mapa de producao com as ferramentas de tools/mapa,
-- nao estimado. Ver secao 21.1 da spec para como cada numero foi obtido.
--
-- Manifesto em Lua e nao YAML de proposito (secao 23.1): o Lua do Canary nao
-- tem parser de YAML, e tabela declarativa ja e o idioma do codebase -- e como
-- o BossLever configura 60 bosses.

HuntInstances = HuntInstances or {}

HuntInstances.thaisCyclops = {
	slug = "thais_cyclops",
	nome = "Ciclopes de Thais",
	enabled = true,

	-- ------------------------------------------------------------ geometria
	-- O recorte guarda x/y REBASEADOS para origem 0 e z ABSOLUTO, entao a
	-- carga usa sempre pos.z = 0. Coordenada absoluta no arquivo + offset
	-- estouraria o uint16 e corromperia o mapa em silencio (spec 3.1).
	template = {
		caminho = "/world/hunt_instances/thais_cyclops_instance.otbm",
		origem = Position(32384, 32016, 0),   -- de onde o recorte foi tirado
		largura = 169,
		altura = 121,
		andares = { 5, 6, 7, 8, 9 },
	},

	-- Faixa validada: o mapa oficial acaba em x 34304, e aqui sobra folga de
	-- 3841 tiles. A faixa da v1 (x 5000) estava OCUPADA.
	slotOrigens = {
		Position(36864, 36864, 0),
		Position(37376, 36864, 0),
		Position(37888, 36864, 0),
		Position(38400, 36864, 0),
		Position(38912, 36864, 0),
		Position(39424, 36864, 0),
	},

	-- ------------------------------------------------------------- entradas
	-- Relativas ao slot: posicao real = origem do slot + isto.
	-- Todas verificadas: tem chao, sem item bloqueante, nao e' tile de
	-- mudanca de andar, e a 4+ tiles de qualquer spawn.
	-- A CHEGADA E' A BOCA DA CAVERNA, no z=7, e nao o meio da hunt. A primeira
	-- versao caiu num canto do z=8 com um unico ciclope a vista, porque foi
	-- escolhida pelo centroide dos tiles seguros -- criterio mecanico, sem
	-- relacao com onde a hunt comeca. O jogador tem de chegar onde entraria a pe.
	--
	-- (80, 69, 7) relativo = (32464, 32085, 7) global, a entrada da caverna.
	-- As cinco verificadas: tem chao, sem item bloqueante, nao sao tile de
	-- mudanca de andar, e longe de spawn.
	entradasRelativas = {
		{ x = 80, y = 69, z = 7 },
		{ x = 80, y = 68, z = 7 },
		{ x = 81, y = 68, z = 7 },
		{ x = 81, y = 69, z = 7 },
		{ x = 81, y = 70, z = 7 },
	},

	-- --------------------------------------------------------- mundo global
	-- A entrada da hunt e o vao na rocha ao NORTE da cabana de pedra. A
	-- escada de dentro da cabana NAO leva a hunt -- foi um erro de leitura
	-- do mapa: o achar_acessos.py apontou o trapdoor dela como candidato,
	-- mas ele vai para outro lugar.
	seletor = {
		posicao = Position(32453, 32106, 7),
		itemId = 2199,          -- obelisk
		actionId = 65001,
	},

	-- Tiles onde os membros da party sobem para consentir (spec 9.2).
	-- Presenca fisica e o consentimento: a ModalWindow morre quando o
	-- jogador anda, o que inviabilizaria um ready check.
	playerPositions = {
		Position(32453, 32108, 7),
		Position(32452, 32107, 7),
		Position(32453, 32107, 7),
		Position(32452, 32108, 7),
		Position(32454, 32108, 7),
	},

	retornoGlobal = Position(32453, 32108, 7),
	retornoEmergencia = Position(32369, 32241, 7),   -- templo de Thais
	raioRetorno = 2,

	-- ------------------------------------------------------------- limites
	maximoSlots = 6,

	duracaoMaximaMinutos = 120,
	graceVazioMinutos = 3,        -- atraso de teardown, NAO janela de volta
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

	-- Sem multiplicador: a instancia e' equivalente a hunt publica.
	multiplicadorExp = 1.0,
	multiplicadorLoot = 1.0,
	multiplicadorSpawn = 1.0,

	skullsBloqueadas = { SKULL_WHITE, SKULL_RED, SKULL_BLACK },
	bloqueiaComPvpLock = true,
	removeItensNoChaoAoLimpar = true,
}
