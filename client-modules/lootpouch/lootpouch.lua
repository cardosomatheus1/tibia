-- Botao de AutoLoot na janela da Loot Pouch.
--
-- Ao abrir a Loot Pouch, este modulo acrescenta um botao na janela dela:
-- borda VERDE quando o AutoLoot esta ligado, VERMELHA quando desligado.
-- Clicar alterna.
--
-- Por que o estado viaja por mensagem de texto e nao por extended opcode:
-- o Canary RECEBE extended opcode do client (parseExtendedOpcode) mas nao
-- consegue ENVIAR -- o unico 0x32 que ele manda e' no handshake de login, e
-- nao ha sendExtendedOpcode exposto ao Lua do servidor. Expor isso exigiria
-- recompilar o servidor. Entao o servidor responde por mensagem marcada com
-- "[LP] <temPouch> <estado>", que este modulo le e esconde do chat.
--
-- Quem manda e' sempre o servidor: o botao so pede a mudanca com !autoloot e
-- repinta quando a resposta chega. Assim a borda nunca mente sobre o estado
-- real, mesmo se o jogador digitar o comando na mao.

local ID_LOOT_POUCH = 23721
local MARCA = "%[LP%]"          -- padrao Lua (colchetes precisam de escape)
local COR_LIGADO = "#00cc00"
local COR_DESLIGADO = "#cc0000"

-- Mana e' o modo silencioso combinado com o servidor; os demais sao rede de
-- seguranca caso a traducao de tipo do protocolo mude entre versoes.
local MODOS_ESCUTADOS = {
    MessageModes.Mana,
    MessageModes.Look,
    MessageModes.Game,
}

local temPouch = false
local estado = 0                -- 0 desligado, 1 ligado, 2 ligado com boss
local botoes = {}               -- janela -> botao, para repintar todos
local conexoes = nil

local function pintar(botao)
    if not botao then return end
    local ligado = estado > 0
    botao:setImageColor(ligado and COR_LIGADO or COR_DESLIGADO)
    botao:setText(ligado and tr("AutoLoot: ON") or tr("AutoLoot: OFF"))
    botao:setTooltip(temPouch
        and tr("Clique para ligar/desligar o AutoLoot desta Loot Pouch")
        or tr("Voce precisa de uma Loot Pouch para usar o AutoLoot"))
end

local function repintarTodos()
    for janela, botao in pairs(botoes) do
        if janela:isDestroyed() then
            botoes[janela] = nil
        else
            pintar(botao)
        end
    end
end

local function alternar()
    if not g_game.isOnline() then return end
    -- pede ao servidor; a borda so muda quando ele confirmar
    g_game.talk(estado > 0 and "!autoloot off" or "!autoloot on")
end

-- Le "[LP] <temPouch> <estado>". Chega pelo MessageModes.Mana, que o client
-- nao desenha -- por isso nada aparece na tela do jogador. O retorno aqui e'
-- ignorado pelo onTextMessage (ele chama todos os callbacks e nao olha o
-- resultado); quem garante o silencio e' o modo escolhido, nao este return.
local function aoReceberTexto(modo, texto)
    if type(texto) ~= "string" then return end
    local p, e = texto:match("^" .. MARCA .. "%s+(%d+)%s+(%d+)")
    if not p then return end

    temPouch = (tonumber(p) or 0) > 0
    estado = tonumber(e) or 0
    repintarTodos()
end

local function aoAbrirContainer(container)
    if not container then return end

    local item = container:getContainerItem()
    if not item or item:getId() ~= ID_LOOT_POUCH then
        return
    end

    -- a janela criada pelo game_containers segue o id do container
    local janela = rootWidget:recursiveGetChildById("container" .. container:getId())
    if not janela or janela:getChildById("btAutoLoot") then
        return
    end

    local botao = g_ui.createWidget("LootPouchBotao", janela)
    botao:setId("btAutoLoot")
    botao.onClick = alternar
    botoes[janela] = botao
    pintar(botao)

    -- pergunta o estado ao servidor toda vez que abre: outro personagem, outro
    -- estado, e o jogador pode ter usado o comando digitado no meio do caminho
    if g_game.isOnline() then
        g_game.talk("!autoloot status")
    end
end

function init()
    conexoes = {
        onContainerOpen = aoAbrirContainer,
        onGameEnd = function()
            botoes = {}
            temPouch, estado = false, 0
        end,
    }
    connect(g_game, conexoes)

    -- Mana e' o modo que o servidor usa para o estado (silencioso, o client
    -- nao desenha). Os outros entram como rede de seguranca caso a traducao
    -- de tipo do protocolo caia noutro modo entre versoes.
    for _, modo in ipairs(MODOS_ESCUTADOS) do
        if modo then
            registerMessageMode(modo, aoReceberTexto)
        end
    end
end

function terminate()
    if conexoes then
        disconnect(g_game, conexoes)
        conexoes = nil
    end
    for _, modo in ipairs(MODOS_ESCUTADOS) do
        if modo then
            unregisterMessageMode(modo, aoReceberTexto)
        end
    end
    for janela, botao in pairs(botoes) do
        if not janela:isDestroyed() then
            botao:destroy()
        end
    end
    botoes = {}
end
