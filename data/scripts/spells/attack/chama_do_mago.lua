-- Magia de exemplo do pipeline de sprites (tools/sprites/).
-- Usa o efeito 350 e o missile 70, que NÃO existem no Tibia original: os dois
-- foram criados com `tools/sprites/novo_efeito.py` e vivem no appearances.dat.
-- Sem rodar a ferramenta, o servidor derruba os dois para o efeito padrão.
local EFEITO_CHAMA = 350
local MISSILE_CHAMA = 70

local combat = Combat()
combat:setParameter(COMBAT_PARAM_TYPE, COMBAT_FIREDAMAGE)
combat:setParameter(COMBAT_PARAM_EFFECT,
	Game.hasEffect(EFEITO_CHAMA) and EFEITO_CHAMA or CONST_ME_FIREAREA)
combat:setParameter(COMBAT_PARAM_DISTANCEEFFECT,
	Game.hasDistanceEffect(MISSILE_CHAMA) and MISSILE_CHAMA or CONST_ANI_FIRE)

function onGetFormulaValues(player, level, maglevel)
	local min = (level / 5) + (maglevel * 1.403) + 8
	local max = (level / 5) + (maglevel * 2.203) + 13
	return -min, -max
end

combat:setCallback(CALLBACK_PARAM_LEVELMAGICVALUE, "onGetFormulaValues")

local spell = Spell("instant")

function spell.onCastSpell(creature, var)
	return combat:execute(creature, var)
end

spell:group("attack")
spell:id(4)
spell:name("Chama do Mago")
spell:words("exori chama")
spell:castSound(SOUND_EFFECT_TYPE_SPELL_OR_RUNE)
spell:impactSound(SOUND_EFFECT_TYPE_SPELL_FLAME_STRIKE)
spell:level(12)
spell:mana(20)
spell:range(5)
spell:needCasterTargetOrDirection(true)
spell:blockWalls(true)
spell:cooldown(2 * 1000)
spell:groupCooldown(2 * 1000)
spell:vocation("sorcerer;true", "master sorcerer;true", "druid;true", "elder druid;true")
spell:register()
