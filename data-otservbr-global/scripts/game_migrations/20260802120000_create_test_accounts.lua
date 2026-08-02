-- Creates 3 test accounts (gabriel, andre, matheus), each with one level 2000
-- character per vocation (Sorcerer, Druid, Paladin, Knight, Monk), fully
-- geared with tier 7 equipment and skills appropriate for the level.
-- Runs once per server (tracked like any other game migration).

local OWNERS = {
	{ account = "gabriel", email = "gabriel@tibia.local", password = "gabriel123" },
	{ account = "andre", email = "andre@tibia.local", password = "andre123" },
	{ account = "matheus", email = "matheus@tibia.local", password = "matheus123" },
}

local BUILDS = {
	{
		suffix = "Sorcerer",
		vocation = 5, -- Master Sorcerer
		health = 10145,
		mana = 59850,
		cap = 20390,
		maglevel = 140,
		skills = { shielding = 110 },
		items = {
			{ id = 43883, slot = CONST_SLOT_LEFT, tier = 7 }, -- grand sanguine coil (weapon hand)
			{ id = 39152, slot = CONST_SLOT_RIGHT, tier = 0 }, -- arcanomancer folio (shield hand; spellbooks aren't forge-eligible)
			{ id = 39151, slot = CONST_SLOT_HEAD, tier = 7 }, -- arcanomancer regalia
			{ id = 34095, slot = CONST_SLOT_ARMOR, tier = 7 }, -- soulmantle
			{ id = 34092, slot = CONST_SLOT_LEGS, tier = 7 }, -- soulshanks
			{ id = 43884, slot = CONST_SLOT_FEET, tier = 7 }, -- sanguine boots
			{ id = 30402, slot = CONST_SLOT_NECKLACE, tier = 0 }, -- enchanted theurgic amulet
			{ id = 39183, slot = CONST_SLOT_RING, tier = 0 }, -- charged arcanomancer sigil
		},
	},
	{
		suffix = "Druid",
		vocation = 6, -- Elder Druid
		health = 10145,
		mana = 59850,
		cap = 20390,
		maglevel = 140,
		skills = { shielding = 110 },
		items = {
			{ id = 43886, slot = CONST_SLOT_LEFT, tier = 7 }, -- grand sanguine rod (weapon hand)
			{ id = 39154, slot = CONST_SLOT_RIGHT, tier = 0 }, -- arboreal tome (shield hand; spellbooks aren't forge-eligible)
			{ id = 39153, slot = CONST_SLOT_HEAD, tier = 7 }, -- arboreal crown
			{ id = 34096, slot = CONST_SLOT_ARMOR, tier = 7 }, -- soulshroud
			{ id = 34093, slot = CONST_SLOT_LEGS, tier = 7 }, -- soulstrider
			{ id = 43887, slot = CONST_SLOT_FEET, tier = 7 }, -- sanguine galoshes
			{ id = 30402, slot = CONST_SLOT_NECKLACE, tier = 0 }, -- enchanted theurgic amulet
			{ id = 39186, slot = CONST_SLOT_RING, tier = 0 }, -- charged arboreal ring
		},
	},
	{
		suffix = "Paladin",
		vocation = 7, -- Royal Paladin
		health = 20105,
		mana = 29970,
		cap = 40310,
		maglevel = 70,
		skills = { dist = 130, shielding = 100 },
		items = {
			{ id = 43880, slot = CONST_SLOT_LEFT, tier = 7 }, -- grand sanguine crossbow (two-handed, weapon hand)
			{ id = 39149, slot = CONST_SLOT_HEAD, tier = 7 }, -- alicorn headguard
			{ id = 34094, slot = CONST_SLOT_ARMOR, tier = 7 }, -- soulshell
			{ id = 43881, slot = CONST_SLOT_LEGS, tier = 7 }, -- sanguine greaves
			{ id = 39161, slot = CONST_SLOT_FEET, tier = 7 }, -- feverbloom boots
			{ id = 34158, slot = CONST_SLOT_NECKLACE, tier = 0 }, -- lion amulet
			{ id = 39180, slot = CONST_SLOT_RING, tier = 0 }, -- charged alicorn ring
		},
	},
	{
		suffix = "Knight",
		vocation = 8, -- Elite Knight
		health = 30065,
		mana = 10050,
		cap = 50270,
		maglevel = 25,
		skills = { sword = 130, shielding = 130 },
		items = {
			{ id = 43865, slot = CONST_SLOT_LEFT, tier = 7 }, -- grand sanguine blade (weapon hand)
			{ id = 34099, slot = CONST_SLOT_RIGHT, tier = 0 }, -- soulbastion (shield hand; shields aren't forge-eligible)
			{ id = 39148, slot = CONST_SLOT_HEAD, tier = 7 }, -- spiritthorn helmet
			{ id = 39147, slot = CONST_SLOT_ARMOR, tier = 7 }, -- spiritthorn armor
			{ id = 43876, slot = CONST_SLOT_LEGS, tier = 7 }, -- sanguine legs
			{ id = 39158, slot = CONST_SLOT_FEET, tier = 7 }, -- frostflower boots
			{ id = 39233, slot = CONST_SLOT_NECKLACE, tier = 0 }, -- enchanted turtle amulet
			{ id = 39177, slot = CONST_SLOT_RING, tier = 0 }, -- charged spiritthorn ring
		},
	},
	{
		suffix = "Monk",
		vocation = 10, -- Exalted Monk
		health = 20105,
		mana = 20010,
		cap = 50270,
		maglevel = 90,
		skills = { fist = 130, shielding = 60 },
		items = {
			{ id = 50158, slot = CONST_SLOT_LEFT, tier = 7 }, -- grand sanguine claws (dual wield weapon; second hand is a client-side visual, not a separate slot in this engine)
			{ id = 50188, slot = CONST_SLOT_HEAD, tier = 7 }, -- ethereal coned hat
			{ id = 50260, slot = CONST_SLOT_ARMOR, tier = 7 }, -- death oyoroi (genesis serenity armor/legs are missing body/legs slot data in this item pack and cannot be equipped)
			{ id = 51267, slot = CONST_SLOT_LEGS, tier = 7 }, -- norcferatu fleshguards
			{ id = 50240, slot = CONST_SLOT_FEET, tier = 7 }, -- soulsoles
			{ id = 50154, slot = CONST_SLOT_NECKLACE, tier = 0 }, -- enchanted merudri brooch
			{ id = 50147, slot = CONST_SLOT_RING, tier = 0 }, -- charged ethereal ring
		},
	},
}

local TOWN_ID = 8
local POS_X, POS_Y, POS_Z = 32369, 32241, 7
local OUTFIT = { body = 113, feet = 115, head = 95, legs = 39, looktype = 129, addons = 0, sex = 1 }
local LEVEL = 2000

local function capitalize(name)
	return name:sub(1, 1):upper() .. name:sub(2)
end

local migration = Migration("20260802120000_create_test_accounts")

function migration:onExecute()
	local createdPlayers = {}

	for _, owner in ipairs(OWNERS) do
		local accountId
		local existingAccount = db.storeQuery("SELECT `id` FROM `accounts` WHERE `name` = " .. db.escapeString(owner.account))
		if existingAccount then
			accountId = Result.getNumber(existingAccount, "id")
			Result.free(existingAccount)
			logger.info("[create_test_accounts] Account '{}' already exists (id {}), reusing it.", owner.account, accountId)
		else
			-- lastday (premium expiry timestamp), not premdays, is what Account::isPremium()
			-- actually checks; without it, premium-gated equips (top-tier weapons/shields) fail.
			local premiumExpires = os.time() + (10 * 365 * 86400)
			db.query(
				"INSERT INTO `accounts` (`name`, `password`, `email`, `type`, `premdays`, `lastday`, `creation`) VALUES ("
					.. db.escapeString(owner.account) .. ", "
					.. "SHA1(" .. db.escapeString(owner.password) .. "), "
					.. db.escapeString(owner.email) .. ", "
					.. "1, 3650, " .. premiumExpires .. ", " .. os.time() .. ")"
			)
			accountId = db.lastInsertId()
			logger.info("[create_test_accounts] Created account '{}' (id {}).", owner.account, accountId)
		end

		for _, build in ipairs(BUILDS) do
			local charName = capitalize(owner.account) .. " " .. build.suffix
			local existingPlayer = db.storeQuery("SELECT `id` FROM `players` WHERE `name` = " .. db.escapeString(charName))
			if existingPlayer then
				Result.free(existingPlayer)
				logger.warn("[create_test_accounts] Player '{}' already exists, skipping creation.", charName)
			else
				local experience = Game.getExperienceForLevel(LEVEL)
				local skillFist = build.skills.fist or 10
				local skillClub = build.skills.club or 10
				local skillSword = build.skills.sword or 10
				local skillAxe = build.skills.axe or 10
				local skillDist = build.skills.dist or 10
				local skillShielding = build.skills.shielding or 10
				local skillFishing = 20

				db.query(
					"INSERT INTO `players` ("
						.. "`name`, `group_id`, `account_id`, `level`, `vocation`, `health`, `healthmax`, `experience`, "
						.. "`lookbody`, `lookfeet`, `lookhead`, `looklegs`, `looktype`, `lookaddons`, "
						.. "`maglevel`, `mana`, `manamax`, `soul`, `town_id`, `posx`, `posy`, `posz`, `conditions`, `cap`, `sex`, "
						.. "`blessings1`, `blessings2`, `blessings3`, `blessings4`, `blessings5`, `blessings6`, `blessings7`, `blessings8`, "
						.. "`skill_fist`, `skill_club`, `skill_sword`, `skill_axe`, `skill_dist`, `skill_shielding`, `skill_fishing`"
						.. ") VALUES ("
						.. db.escapeString(charName) .. ", 1, " .. accountId .. ", " .. LEVEL .. ", " .. build.vocation .. ", "
						.. build.health .. ", " .. build.health .. ", " .. experience .. ", "
						.. OUTFIT.body .. ", " .. OUTFIT.feet .. ", " .. OUTFIT.head .. ", " .. OUTFIT.legs .. ", " .. OUTFIT.looktype .. ", " .. OUTFIT.addons .. ", "
						.. build.maglevel .. ", " .. build.mana .. ", " .. build.mana .. ", 200, " .. TOWN_ID .. ", " .. POS_X .. ", " .. POS_Y .. ", " .. POS_Z .. ", '', " .. build.cap .. ", " .. OUTFIT.sex .. ", "
						.. "1, 1, 1, 1, 1, 1, 1, 1, "
						.. skillFist .. ", " .. skillClub .. ", " .. skillSword .. ", " .. skillAxe .. ", " .. skillDist .. ", " .. skillShielding .. ", " .. skillFishing
						.. ")"
				)
				logger.info("[create_test_accounts] Created player '{}'.", charName)
				table.insert(createdPlayers, { name = charName, build = build })
			end
		end
	end

	for _, entry in ipairs(createdPlayers) do
		local player = Game.getOfflinePlayer(entry.name)
		if not player then
			logger.error("[create_test_accounts] Could not load '{}' to equip gear.", entry.name)
		else
			for _, item in ipairs(entry.build.items) do
				local result = player:addItem(item.id, 1, false, 1, item.slot, item.tier)
				if not result then
					logger.error("[create_test_accounts] Failed to add item {} to '{}' (slot {}).", item.id, entry.name, item.slot)
				end
			end
			player:save()
			logger.info("[create_test_accounts] Equipped and saved '{}'.", entry.name)
		end
	end
end

migration:register()
