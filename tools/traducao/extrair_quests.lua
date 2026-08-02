-- Carrega cada arquivo de quest com Storage/DATA_DIRECTORY dublados e
-- despeja a estrutura (nomes, descricoes, states) em JSON para o Python processar.

local mt = {}
mt.__index = function(t, k)
	local nt = setmetatable({}, mt)
	rawset(t, k, nt)
	return nt
end
Storage = setmetatable({}, mt)
configManager = setmetatable({}, { __index = function() return function() return 1 end end })
configKeys = setmetatable({}, mt)

local function jsonstr(s)
	s = s:gsub('\\', '\\\\'):gsub('"', '\\"'):gsub('\n', '\\n'):gsub('\r', ''):gsub('\t', '\\t')
	return '"' .. s .. '"'
end

local questModules = {}
local f = io.popen("ls data-otservbr-global/lib/core/quests/catalog/*.lua | sort")
for line in f:lines() do
	table.insert(questModules, line)
end
f:close()

print("[")
local first_q = true
for _, path in ipairs(questModules) do
	if path:match("init%.lua$") then
		goto continue
	end
	local ok, quest = pcall(dofile, path)
	if not ok then
		io.stderr:write("ERRO ao carregar " .. path .. ": " .. tostring(quest) .. "\n")
		goto continue
	end
	if type(quest) ~= "table" then
		goto continue
	end
	if not first_q then print(",") end
	first_q = false
	io.write('{"file":' .. jsonstr(path) .. ',"name":' .. jsonstr(quest.name or "") .. ',"missions":[')
	local missionKeys = {}
	for k in pairs(quest.missions or {}) do table.insert(missionKeys, k) end
	table.sort(missionKeys)
	local first_m = true
	for _, mk in ipairs(missionKeys) do
		local m = quest.missions[mk]
		if not first_m then io.write(",") end
		first_m = false
		io.write('{"idx":' .. tostring(mk) .. ',"missionId":' .. tostring(m.missionId or "null"))
		io.write(',"name":' .. jsonstr(m.name or ""))
		if type(m.description) == "string" then
			io.write(',"description":' .. jsonstr(m.description))
		elseif type(m.description) == "function" then
			io.write(',"description_is_function":true')
		end
		if type(m.states) == "table" then
			local stateKeys = {}
			for k in pairs(m.states) do table.insert(stateKeys, k) end
			table.sort(stateKeys)
			io.write(',"states":[')
			for i, sk in ipairs(stateKeys) do
				if i > 1 then io.write(",") end
				local sv = m.states[sk]
				if type(sv) == "string" then
					io.write('{"idx":' .. tostring(sk) .. ',"text":' .. jsonstr(sv) .. '}')
				else
					io.write('{"idx":' .. tostring(sk) .. ',"is_function":true}')
				end
			end
			io.write(']')
		end
		io.write('}')
	end
	io.write(']}')
	::continue::
end
print("")
print("]")
