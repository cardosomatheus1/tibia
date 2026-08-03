-- Completa os personagens criados pela migracao 20260802120000 (gabriel/andre/
-- matheus) com mochila, dinheiro e as magias da propria vocacao - a migracao
-- anterior so cuidou de nivel/vocacao/equipamento, entao eles ficaram sem
-- nada disso (o mesmo motivo pelo qual Wheel/Charms nao apareciam: criados
-- direto no banco, sem os storages/dados que jogar de verdade concederia).

local MAGIAS = {}

MAGIAS.sorcerer = {
	"Animate Dead Rune", "Apprentice's Strike", "Avatar of Storm", "Blank Rune",
	"Buzz", "Cancel Magic Shield", "Chama do Mago", "Conjure Wand of Darkness",
	"Creature Illusion", "Cure Poison", "Curse", "Death Strike",
	"Destroy Field Rune", "Disintegrate Rune", "Electrify", "Enchant Party",
	"Enchant Staff", "Energy Beam", "Energy Bomb Rune", "Energy Field Rune",
	"Energy Strike", "Energy Wall Rune", "Energy Wave", "Explosion Rune",
	"Expose Weakness", "Find Fiend", "Find Person", "Fire Bomb Rune",
	"Fire Field Rune", "Fire Wall Rune", "Fire Wave", "Fireball Rune",
	"Flame Strike", "Great Death Beam", "Great Energy Beam", "Great Fire Wave",
	"Great Fireball Rune", "Great Light", "Haste", "Heavy Magic Missile Rune",
	"Hell's Core", "House Door List", "House Guest List", "House Kick",
	"House Subowner List", "Ice Strike", "Ignite", "Intense Healing",
	"Invisibility", "Levitate", "Light", "Light Healing",
	"Light Magic Missile Rune", "Light Stone Shower Rune",
	"Lightest Missile Rune", "Lightning", "Magic Patch", "Magic Rope",
	"Magic Shield", "Magic Wall Rune", "Poison Field Rune", "Poison Wall Rune",
	"Rage of the Skies", "Restoration", "Sap Strength", "Scorch",
	"Soulfire Rune", "Stalagmite Rune", "Strong Energy Strike",
	"Strong Flame Strike", "Strong Haste", "Sudden Death Rune",
	"Summon Creature", "Summon Sorcerer Familiar", "Terra Strike",
	"Thunderstorm Rune", "Ultimate Energy Strike", "Ultimate Flame Strike",
	"Ultimate Healing", "Ultimate Light",
}

MAGIAS.druid = {
	"Animate Dead Rune", "Apprentice's Strike", "Avalanche Rune",
	"Avatar of Nature", "Blank Rune", "Cancel Magic Shield", "Chama do Mago",
	"Chameleon Rune", "Chill Out", "Convince Creature Rune",
	"Creature Illusion", "Cure Bleeding", "Cure Burning",
	"Cure Electrification", "Cure Poison", "Cure Poison Rune",
	"Destroy Field Rune", "Disintegrate Rune", "Energy Field Rune",
	"Energy Strike", "Energy Wall Rune", "Envenom", "Eternal Winter",
	"Explosion Rune", "Find Fiend", "Find Person", "Fire Bomb Rune",
	"Fire Field Rune", "Fire Wall Rune", "Flame Strike", "Food",
	"Great Light", "Haste", "Heal Friend", "Heal Party",
	"Heavy Magic Missile Rune", "House Door List", "House Guest List",
	"House Kick", "House Subowner List", "Ice Burst", "Ice Strike",
	"Ice Wave", "Icicle Rune", "Intense Healing", "Intense Healing Rune",
	"Invisibility", "Levitate", "Light", "Light Healing",
	"Light Magic Missile Rune", "Light Stone Shower Rune",
	"Lightest Missile Rune", "Magic Patch", "Magic Rope", "Magic Shield",
	"Mass Healing", "Mud Attack", "Nature's Embrace", "Paralyze Rune",
	"Physical Strike", "Poison Bomb Rune", "Poison Field Rune",
	"Poison Wall Rune", "Restoration", "Soulfire Rune", "Stalagmite Rune",
	"Stone Shower Rune", "Strong Haste", "Strong Ice Strike",
	"Strong Ice Wave", "Strong Terra Strike", "Summon Creature",
	"Summon Druid Familiar", "Terra Burst", "Terra Strike", "Terra Wave",
	"Ultimate Healing", "Ultimate Healing Rune", "Ultimate Ice Strike",
	"Ultimate Light", "Ultimate Terra Strike", "Wild Growth Rune",
	"Wrath of Nature",
}

MAGIAS.knight = {
	"Annihilation", "Avatar of Steel", "Berserk", "Blood Rage", "Bruise Bane",
	"Brutal Strike", "Challenge", "Charge", "Chivalrous Challenge",
	"Cure Bleeding", "Cure Poison", "Executioner's Throw",
	"Fair Wound Cleansing", "Fierce Berserk", "Find Fiend", "Find Person",
	"Front Sweep", "Great Light", "Groundshaker", "Haste", "House Door List",
	"House Guest List", "House Kick", "House Subowner List", "Inflict Wound",
	"Intense Recovery", "Intense Wound Cleansing", "Lesser Front Sweep",
	"Levitate", "Light", "Magic Rope", "Protector", "Recovery",
	"Summon Knight Familiar", "Train Party", "Whirlwind Throw",
	"Wound Cleansing",
}

MAGIAS.paladin = {
	"Arrow Call", "Avatar of Light", "Blank Rune", "Cancel Invisibility",
	"Conjure Arrow", "Conjure Bolt", "Conjure Explosive Arrow",
	"Conjure Piercing Bolt", "Conjure Poisoned Arrow", "Conjure Power Bolt",
	"Conjure Royal Star", "Conjure Sniper Arrow", "Cure Curse", "Cure Poison",
	"Destroy Field Rune", "Disintegrate Rune", "Divine Caldera",
	"Divine Dazzle", "Divine Empowerment", "Divine Grenade", "Divine Healing",
	"Divine Missile", "Enchant Spear", "Ethereal Spear", "Find Fiend",
	"Find Person", "Great Light", "Haste", "Holy Flash", "Holy Missile Rune",
	"House Door List", "House Guest List", "House Kick", "House Subowner List",
	"Intense Healing", "Intense Recovery", "Lesser Ethereal Spear", "Levitate",
	"Light", "Light Healing", "Magic Patch", "Magic Rope", "Protect Party",
	"Recovery", "Salvation", "Sharpshooter", "Strong Ethereal Spear",
	"Summon Paladin Familiar", "Swift Foot",
}

MAGIAS.monk = {
	"Avatar of Balance", "Balanced Brawl", "Chained Penance", "Cure Poison",
	"Destroy Field Rune", "Devastating Knockout", "Disintegrate Rune",
	"Double Jab", "Enlighten Party", "Find Fiend", "Find Person",
	"Flurry of Blows", "Focus Harmony", "Focus Serenity", "Forceful Uppercut",
	"Great Light", "Greater Flurry of Blows", "Greater Tiger Clash", "Haste",
	"House Door List", "House Guest List", "House Kick", "House Subowner List",
	"Inflict Wound", "Intense Healing", "Levitate", "Light", "Light Healing",
	"Magic Patch", "Magic Rope", "Mass Spirit Mend", "Mentor Other",
	"Monk familiar", "Mystic Repulse", "Restore Balance", "Spirit Mend",
	"Spiritual Outburst", "Strong Haste", "Sweeping Takedown", "Swift Jab",
	"Tiger Clash", "Virtue of Harmony", "Virtue of Justice", "Virtue of Sustain",
}

local OWNERS = { "Gabriel", "Andre", "Matheus" }
local VOCACOES = { "Sorcerer", "Druid", "Paladin", "Knight", "Monk" }

local BACKPACK_ID = 9605 -- crown backpack, containersize 20 (o maior deste dataset)
local CRYSTAL_COIN_ID = 3043 -- 10.000 gold cada
local QTD_CRYSTAL_COINS = 100 -- 1.000.000 gold no total

local migration = Migration("20260803000000_complementar_personagens_teste")

function migration:onExecute()
	for _, dono in ipairs(OWNERS) do
		for _, voc in ipairs(VOCACOES) do
			local nome = dono .. " " .. voc
			local player = Game.getOfflinePlayer(nome)
			if not player then
				logger.warn("[complementar_personagens_teste] '{}' nao encontrado, pulando.", nome)
			else
				if not player:getSlotItem(CONST_SLOT_BACKPACK) then
					player:addItem(BACKPACK_ID, 1, false, 1, CONST_SLOT_BACKPACK)
				end

				player:addItem(CRYSTAL_COIN_ID, QTD_CRYSTAL_COINS, false)

				local magias = MAGIAS[voc:lower()] or {}
				for _, magia in ipairs(magias) do
					player:learnSpell(magia)
				end

				player:save()
				logger.info(
					"[complementar_personagens_teste] '{}' atualizado: mochila + {} crystal coins + {} magias.",
					nome, QTD_CRYSTAL_COINS, #magias
				)
			end
		end
	end
end

migration:register()
