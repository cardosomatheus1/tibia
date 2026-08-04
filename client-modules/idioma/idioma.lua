-- Bandeirinha de idioma.
--
-- Quem decide o idioma e o servidor: a escolha fica no KV do personagem,
-- porque e o servidor que monta a fala do NPC. Este modulo so manda o
-- comando `!idioma <codigo>` — nada e traduzido aqui.

janelaIdioma = nil
local botao = nil

local IDIOMAS = {
  { codigo = "br", rotulo = "Portugues (BR)" },
  { codigo = "us", rotulo = "English (US)" },
}

function init()
  janelaIdioma = g_ui.displayUI("idioma")
  janelaIdioma:hide()

  botao = modules.client_topmenu.addRightGameToggleButton("idiomaButton",
    tr("Idioma dos NPCs"), "/idioma/botao", alternar, false, 9)

  janelaIdioma:getChildById("btPt").onClick = function() escolher("br") end
  janelaIdioma:getChildById("btEn").onClick = function() escolher("us") end

  g_keyboard.bindKeyDown("Ctrl+Shift+I", alternar)
end

function terminate()
  g_keyboard.unbindKeyDown("Ctrl+Shift+I")
  if botao then botao:destroy() botao = nil end
  if janelaIdioma then janelaIdioma:destroy() janelaIdioma = nil end
end

function alternar()
  if not janelaIdioma then return end
  if janelaIdioma:isVisible() then
    janelaIdioma:hide()
  else
    janelaIdioma:show()
    janelaIdioma:raise()
    janelaIdioma:focus()
  end
end

function escolher(codigo)
  if not g_game.isOnline() then return end
  g_game.talk("!idioma " .. codigo)
  janelaIdioma:hide()
end
