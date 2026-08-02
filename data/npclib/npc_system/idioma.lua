-- Camada de idioma dos NPCs.
--
-- Em vez de traduzir os 1036 arquivos de NPC, a tradução entra em dois
-- pontos por onde tudo passa:
--
--   saída   `Npc:say`  — todo NPC fala por aqui, inclusive o caminho com
--                        atraso (`SayEvent`) e o `sendMessage`. O texto é
--                        trocado pelo do idioma **daquele jogador**, então
--                        dois jogadores lado a lado leem cada um no seu.
--   entrada `NpcHandler:onSay` — o que o jogador digita é normalizado para
--                        inglês antes de qualquer comparação, então "oi",
--                        "depositar tudo" e "sim" caem nas mesmas regras
--                        que "hi", "deposit all" e "yes". O inglês continua
--                        funcionando: a normalização só acrescenta.
--
-- O idioma fica no KV do jogador (`idioma`), então acompanha o personagem
-- e não depende de client nenhum. Sem dicionário para o texto, ele sai em
-- inglês — nunca vazio.

Idioma = {
	PADRAO = "en",
	CHAVE_KV = "idioma",
	dicionarios = {},   -- [codigo] = { nome, textos = {}, palavras = {} }
	entrada = {},       -- palavra traduzida (qualquer idioma) -> palavra em ingles
}

-- Registra (ou completa) um idioma. Pode ser chamado várias vezes, o que
-- permite quebrar um dicionário grande em vários arquivos.
function Idioma.registrar(codigo, dados)
	local d = Idioma.dicionarios[codigo]
	if not d then
		d = { nome = dados.nome or codigo, bandeira = dados.bandeira, textos = {}, palavras = {} }
		Idioma.dicionarios[codigo] = d
	end
	if dados.nome then
		d.nome = dados.nome
	end
	for original, traduzido in pairs(dados.textos or {}) do
		d.textos[original] = traduzido
	end
	for original, traduzido in pairs(dados.palavras or {}) do
		d.palavras[original] = traduzido
		-- o caminho de volta: o que o jogador digita vira o termo em inglês
		Idioma.entrada[traduzido:lower()] = original:lower()
	end
	-- Apelidos valem **só na entrada**. É o caso de nome de magia e nome de
	-- cidade: o jogador pode dizer "cura suprema", mas o NPC continua
	-- dizendo {ultimate healing}, porque é assim que o nome aparece na
	-- spellbook, na hotkey e na encantação. Traduzir a saída aí inventaria
	-- um nome que não existe em nenhum outro lugar do jogo.
	for original, apelido in pairs(dados.apelidos or {}) do
		Idioma.entrada[apelido:lower()] = original:lower()
	end
end

function Idioma.existe(codigo)
	return codigo == "en" or Idioma.dicionarios[codigo] ~= nil
end

function Idioma.lista()
	local saida = { { codigo = "en", nome = "English", bandeira = "us" } }
	for codigo, d in pairs(Idioma.dicionarios) do
		table.insert(saida, { codigo = codigo, nome = d.nome, bandeira = d.bandeira })
	end
	return saida
end

function Idioma.do_jogador(player)
	if not player then
		return Idioma.PADRAO
	end
	local codigo = player:kv():get(Idioma.CHAVE_KV)
	return (codigo and Idioma.existe(codigo)) and codigo or Idioma.PADRAO
end

function Idioma.definir(player, codigo)
	if not player or not Idioma.existe(codigo) then
		return false
	end
	player:kv():set(Idioma.CHAVE_KV, codigo)
	return true
end

-- ------------------------------------------------------------------ saída

-- Troca as palavras-chave que aparecem entre chaves. O client destaca e
-- deixa clicável o que está em {...}, então isso também precisa sair
-- traduzido — e é o motivo de a normalização de entrada existir, senão o
-- jogador clicaria em {negociar} e o NPC não entenderia.
local function traduzir_chaves(texto, palavras)
	return (texto:gsub("{(.-)}", function(dentro)
		local pt = palavras[dentro:lower()]
		if not pt then
			return "{" .. dentro .. "}"
		end
		-- preserva a primeira letra maiúscula do original
		if dentro:sub(1, 1):match("%u") then
			pt = pt:sub(1, 1):upper() .. pt:sub(2)
		end
		return "{" .. pt .. "}"
	end))
end

-- Chave tolerante: minúscula, espaço colapsado, pontuação de borda fora.
-- Serve para uma frase não perder a tradução porque o upstream mexeu numa
-- vírgula ou num espaço duplo. Mudança de palavra continua não casando de
-- propósito — para isso existe o `verificar.py`, que mostra o quase-igual e
-- deixa a decisão com uma pessoa, em vez de arriscar mostrar a fala errada.
function Idioma.chave_tolerante(texto)
	return (texto:lower():gsub("%s+", " "):gsub("^[%p%s]+", ""):gsub("[%p%s]+$", ""))
end

function Idioma.saida(texto, player)
	if type(texto) ~= "string" or texto == "" then
		return texto
	end
	local codigo = Idioma.do_jogador(player)
	local d = Idioma.dicionarios[codigo]
	if not d then
		return texto
	end
	local traduzido = d.textos[texto]
	if traduzido then
		return traduzido
	end
	if d.tolerantes then
		traduzido = d.tolerantes[Idioma.chave_tolerante(texto)]
		if traduzido then
			return traduzido
		end
	end
	-- sem tradução da frase inteira, ainda dá para traduzir o que é clicável
	return traduzir_chaves(texto, d.palavras)
end

-- ---------------------------------------------------------------- entrada

-- Normaliza o que o jogador digitou para o termo em inglês que as regras
-- dos NPCs esperam. Tenta a frase inteira primeiro (para "depositar tudo"
-- não virar "depositar" + "tudo") e depois palavra a palavra.
function Idioma.entrada_normalizada(msg)
	if type(msg) ~= "string" or msg == "" then
		return msg
	end
	local baixo = msg:lower()
	local inteiro = Idioma.entrada[baixo]
	if inteiro then
		return inteiro
	end
	-- troca o maior trecho conhecido, da esquerda para a direita
	local partes = {}
	for palavra in baixo:gmatch("%S+") do
		table.insert(partes, palavra)
	end
	local saida, i, mudou = {}, 1, false
	while i <= #partes do
		local casou = false
		for tamanho = math.min(4, #partes - i + 1), 1, -1 do
			local trecho = table.concat(partes, " ", i, i + tamanho - 1)
			local traduzido = Idioma.entrada[trecho]
			if traduzido then
				table.insert(saida, traduzido)
				i = i + tamanho
				casou, mudou = true, true
				break
			end
		end
		if not casou then
			table.insert(saida, partes[i])
			i = i + 1
		end
	end
	return mudou and table.concat(saida, " ") or msg
end

-- ------------------------------------------------------------------ ganchos

-- Um wrapper em Npc:say pega toda a fala de NPC dirigida a um jogador.
-- Fala sem destinatário (os gritos ociosos) não passa por aqui de
-- propósito: não há para quem escolher idioma.
if not Idioma._enganchado then
	Idioma._enganchado = true

	local say_original = Npc.say
	function Npc:say(texto, tipo, ghost, alvo, posicao)
		if alvo and type(texto) == "string" then
			texto = Idioma.saida(texto, alvo)
		end
		return say_original(self, texto, tipo, ghost, alvo, posicao)
	end
end
