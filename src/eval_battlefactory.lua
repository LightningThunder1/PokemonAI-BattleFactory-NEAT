---@diagnostic disable: trailing-space

-- global pointer offsets
local ACTIVE_ENEMY_OFFSET = 0x54658 -- BLOCK_B
local ACTIVE_ALLY_OFFSET = 0x54598 -- BLOCK_B
local FUTURE_ENEMY_OFFSET = 0x3CDCC -- BLOCK_A
local ALLY_OFFSET = 0x3D10C  -- Encrypted
local ENEMY_OFFSET = 0x3D6BC -- Encrypted
local MODE_OFFSET = 0x54600
local TRADEMENU_OFFSET = 0x62BEC

-- game state & game mode consts
local STATE_INIT = 0
local STATE_BATTLE = 1
local STATE_TRADE = 2
local STATE_NA = 3
local MODE_TRADE = 0x140
local MODE_TRADEMENU = 0x0000
local MODE_OUTSIDE = 0x57BC
local MODE_BATTLEROOM = 0x290
local MODE_NA = 0x0000

-- global vars for game loop
local ttl
local ally_deaths
local enemy_deaths
local last_dead_ally
local last_dead_enemy
local gp
local battle_number
local round_number
local fitness
local has_battled
local input_state

-- orderings of shuffled pokemon data blocks from shift-values
local SHUFFLE_ORDER = {
	["0"] = {A = 1, B = 2, C = 3, D = 4};
	["1"] = {A = 1, B = 2, C = 4, D = 3};
	["2"] = {A = 1, B = 3, C = 2, D = 4};
	["3"] = {A = 1, B = 4, C = 2, D = 3};
	["4"] = {A = 1, B = 3, C = 4, D = 2};
	["5"] = {A = 1, B = 4, C = 3, D = 2};
	["6"] = {A = 2, B = 1, C = 3, D = 4};
	["7"] = {A = 2, B = 1, C = 4, D = 3};
	["8"] = {A = 3, B = 1, C = 2, D = 4};
	["9"] = {A = 4, B = 1, C = 2, D = 3};
	["10"] = {A = 3, B = 1, C = 4, D = 2};
	["11"] = {A = 4, B = 1, C = 3, D = 2};
	["12"] = {A = 2, B = 3, C = 1, D = 4};
	["13"] = {A = 2, B = 4, C = 1, D = 3};
	["14"] = {A = 3, B = 2, C = 1, D = 4};
	["15"] = {A = 4, B = 2, C = 1, D = 3};
	["16"] = {A = 3, B = 4, C = 1, D = 2};
	["17"] = {A = 4, B = 3, C = 1, D = 2};
	["18"] = {A = 2, B = 3, C = 4, D = 1};
	["19"] = {A = 2, B = 4, C = 3, D = 1};
	["20"] = {A = 3, B = 2, C = 4, D = 1};
	["21"] = {A = 4, B = 2, C = 3, D = 1};
	["22"] = {A = 3, B = 4, C = 2, D = 1};
	["23"] = {A = 4, B = 3, C = 2, D = 1};
}

-- pokemon data structure
local POKEMON_STRUCT = {
	ID = 0x0,
	PID = 0x0,
	HeldItem = 0x0,
	Ability = 0x0,
	Active = 0x0,
	Moves = {
		["1"] = {ID = 0x0, PP = 0x0},
		["2"] = {ID = 0x0, PP = 0x0},
		["3"] = {ID = 0x0, PP = 0x0},
		["4"] = {ID = 0x0, PP = 0x0},
	},
	-- IVs = {
	-- 	HP = 0x0, ATK = 0x0, DEF = 0x0,
	--	SPEED = 0x0, SPA = 0x0, SPD = 0x0,
	--},
	EVs = {
		HP = 0x0, ATK = 0x0, DEF = 0x0,
		SPEED = 0x0, SPA = 0x0, SPD = 0x0,
	},
	Stats = {
		Status = 0x0, Level = 0x0, EXP = 0x0,
		HP = 0x0, MaxHP = 0x0, ATK = 0x0,
		DEF = 0x0, SPEED = 0x0, SPA = 0x0, SPD = 0x0,
	}
}

-- unencrypted pokemon memory block offsets
local BLOCK_A = {  -- 56 bytes
    SIZE = 0x38,
    ID = 0x0,
    HELD_ITEM = 0x2,
    MOVE1_ID = 0x4,
    MOVE2_ID = 0x6,
    MOVE3_ID = 0x8,
    MOVE4_ID = 0xA,
    ABILITY = 0x20,
}
local BLOCK_B = {  -- 192 bytes
    SIZE = 0xC0,
    ID = 0x0,
    HP = 0x4C,
    MOVE1_PP = 0x2C,
    MOVE2_PP = 0x2D,
    MOVE3_PP = 0x2E,
    MOVE4_PP = 0x2F,
}

-- input layer data structure
local STATE_STRUCT = {
    Mode = 0,  -- init=0, battle=1, trade=2
    Ally1 = {},
    Ally2 = {},
    Ally3 = {},
    Ally4 = {},
    Ally5 = {},
    Ally6 = {},
    Enemy1 = {},
    Enemy2 = {},
    Enemy3 = {},
}

-- copy table data structures
function table.shallow_copy(t)
	local t2 = {}
	for k,v in pairs(t) do
		t2[k] = v
	end
	return t2
end

-- multiply 4-byte values
local function mult32(a, b)
	local c = a >> 16
	local d = a % 0x10000
	local e = b >> 16
	local f = b % 0x10000
	local g = (c * f + d * e) % 0x10000
	local h = d * f
	local i = g * 0x10000 + h
	return i
end

-- decrypt pokemon bytes
local function decrypt(seed, addr, words)
	local X = { seed }
	local D = {}
	for n = 1, words+1, 1 do
		X[n+1] = mult32(X[n], 0x41C64E6D) + 0x6073
		D[n] = memory.read_u16_le(addr + ((n - 1) * 0x02))
		D[n] = D[n] ~ (X[n+1] >> 16)
		-- print(n, string.format("%X", D[n]))
	end
	return D
end

-- read encrypted pokemon data
local function read_pokemon(ptr, party_idx)
	-- offset pokemon pointer for party index
	ptr = ptr + (0xEC * party_idx)

	-- pokemon decryption vars
	local pid = memory.read_u32_le(ptr + 0x0)
	local checksum = memory.read_u16_le(ptr + 0x06)
	local shift = tostring(((pid & 0x3E000) >> 0xD) % 24)
	print("PID:", pid)
	print("Checksum:", checksum)
	print("Shift:", shift)

	-- decrypt pokemon bytes
	local D = decrypt(checksum, ptr + 0x08, 64) -- data
	local B = decrypt(pid, ptr + 0x88, 50) -- battle stats

	local function fetch_Dv(block_offset, var_offset)
		return D[((block_offset + var_offset) / 2) + 1]
	end

	local function fetch_Bv(var_offset)
		return B[((var_offset - 0x88) / 2) + 1]
	end

	-- calculate shuffled block offsets
	local a_offset = (SHUFFLE_ORDER[shift]["A"] - 1) * 0x20
	local b_offset = (SHUFFLE_ORDER[shift]["B"] - 1) * 0x20
	local c_offset = (SHUFFLE_ORDER[shift]["C"] - 1) * 0x20
	local d_offset = (SHUFFLE_ORDER[shift]["D"] - 1) * 0x20

	-- instantiate new pokemon obj and populate vars
	local pokemon = table.shallow_copy(POKEMON_STRUCT)
	pokemon.ID = fetch_Dv(a_offset, 0x08 - 0x08)
	pokemon.PID = pid
	pokemon.HeldItem = fetch_Dv(a_offset, 0x0A - 0x08)
	pokemon.Ability = fetch_Dv(a_offset, 0x15 - 0x08)
	pokemon.EXP = fetch_Dv(a_offset, 0x10 - 0x08) -- TODO
	pokemon.Moves = {
		["1"] = {
			ID = fetch_Dv(b_offset, 0x28 - 0x28) & 0xFFFF,
			PP = fetch_Dv(b_offset, 0x30 - 0x28) & 0x00FF,
		};
		["2"] = {
			ID = fetch_Dv(b_offset, 0x2A - 0x28) & 0xFFFF,
			PP = (fetch_Dv(b_offset, 0x30 - 0x28) & 0xFF00) >> 8,
		};
		["3"] = {
			ID = fetch_Dv(b_offset, 0x2C - 0x28) & 0xFFFF,
			PP = fetch_Dv(b_offset, 0x32 - 0x28) & 0x00FF,
		};
		["4"] = {
			ID = fetch_Dv(b_offset, 0x2E - 0x28) & 0xFFFF,
			PP = (fetch_Dv(b_offset, 0x32 - 0x28) & 0xFF00) >> 8,
		};
	}
	pokemon.IVs = {  -- TODO
		HP = 0x0,
		ATK = 0x0,
		DEF = 0x0,
		SPEED = 0x0,
		SPA = 0x0,
		SPD = 0x0,
	}
	pokemon.EVs = {
		HP = fetch_Dv(a_offset, 0x18 - 0x08) & 0x00FF,
		ATK = fetch_Dv(a_offset, 0x18 - 0x08) >> 8,
		DEF = fetch_Dv(a_offset, 0x1A - 0x08) & 0x00FF,
		SPEED = fetch_Dv(a_offset, 0x1A - 0x08) >> 8,
		SPA = fetch_Dv(a_offset, 0x1C - 0x08) & 0x00FF,
		SPD = fetch_Dv(a_offset, 0x1C - 0x08) >> 8,
	}
	pokemon.Stats = {
		Status = fetch_Bv(0x88) & 0x00FF, -- TODO test
		Level = fetch_Bv(0x8C) & 0x00FF,
		HP = fetch_Bv(0x8E) & 0xFFFF,
		MaxHP = fetch_Bv(0x90) & 0xFFFF,
		ATK = fetch_Bv(0x92) & 0xFFFF,
		DEF = fetch_Bv(0x94) & 0xFFFF,
		SPEED = fetch_Bv(0x96) & 0xFFFF,
		SPA = fetch_Bv(0x98) & 0xFFFF,
		SPD = fetch_Bv(0x9A) & 0xFFFF,
	}
	return pokemon
end

local function print_pokemon(pokemon)
    print(pokemon)
    print("MOVES")
    print(pokemon.Moves[1])
    print(pokemon.Moves[2])
    print(pokemon.Moves[3])
    print(pokemon.Moves[4])
    print("STATS")
    print(pokemon.Stats)
    print("EVs")
    print(pokemon.EVs)
    print("IVs")
    print(pokemon.IVs)
end

local function serialize_table(tabl, indent)
    local nl = string.char(10) -- newline
    indent = indent and (indent.."  ") or ""
    local str = ''
    str = str .. indent.."{"
    for key, value in pairs (tabl) do
        local pr = (type(key)=="string") and ('"'..key..'":') or ""
        if type (value) == "table" then
            str = str..nl..pr..serialize_table(value, indent)..','
        elseif type (value) == "string" then
            str = str..nl..indent..pr..'"'..tostring(value)..'",'
        else
            str = str..nl..indent..pr..tostring(value)..','
        end
    end
    str = str:sub(1, #str-1) -- remove last symbol
    str = str..nl..indent.."}"
    return str
end

local function refresh_gui()
    gui.cleartext()
	gui.drawText(150, 0, "Ally Deaths: "..ally_deaths, "#ED4C40", "#000000", 10)
	gui.drawText(150, 10, "Enemy Deaths: "..enemy_deaths, "#ED4C40", "#000000", 10)
	gui.drawText(150, 20, "TTL: "..ttl, "#ED4C40", "#000000", 10)
	gui.drawText(150, 30, "Battle #: "..battle_number, "#ED4C40", "#000000", 10)
	gui.drawText(150, 40, "Round #: "..round_number, "#ED4C40", "#000000", 10)
	gui.drawText(150, 50, "Fitness: "..fitness, "#ED4C40", "#000000", 10)
end

local function death_check()
    local reset_ttl = false

    -- game mode check | 0x140=trading, 0x57BC=done, 0x290=battle-room,
    local mode = memory.read_u16_le(gp + MODE_OFFSET)
    if mode == MODE_NA or mode == MODE_TRADE or mode == MODE_OUTSIDE or mode == MODE_BATTLEROOM then
    	return
    end

    -- checking active battle pokemon for deaths
    if has_battled == 0 then
    	reset_ttl = true
    end
    has_battled = 1

    -- enemy death check
    local enemy_id = memory.read_u16_le(gp + ACTIVE_ENEMY_OFFSET)
    local enemy_hp = memory.read_u16_le(gp + ACTIVE_ENEMY_OFFSET + BLOCK_B.HP)
    if enemy_id ~= 0x0 and enemy_id ~= last_dead_enemy and enemy_hp <= 0x0 then
    	enemy_deaths = enemy_deaths + 1
    	last_dead_enemy = enemy_id
    	reset_ttl = true
    	print("Enemy died! "..enemy_deaths)
    end

    -- ally death check
    local ally_id = memory.read_u16_le(gp + ACTIVE_ALLY_OFFSET)
    local ally_hp = memory.read_u16_le(gp + ACTIVE_ALLY_OFFSET + BLOCK_B.HP)
    if ally_id ~= 0x0 and ally_id ~= last_dead_ally and ally_hp <= 0x0 then
    	ally_deaths = ally_deaths + 1
    	last_dead_ally = ally_id
    	reset_ttl = true
    	print("Ally Died! "..ally_deaths)
    end

    -- reset TTL?
    if reset_ttl then
    	ttl = ttl + 5000
    	print("Refreshed TTL: "..ttl)
    end
end

local function in_battle_room()
    return memory.read_u16_le(gp + MODE_OFFSET) == MODE_BATTLEROOM
end

local function in_trade_menu()
    return memory.read_u16_le(gp + TRADEMENU_OFFSET) == MODE_TRADEMENU
end

local function is_outside()
    return memory.read_u16_le(gp + MODE_OFFSET) == MODE_OUTSIDE
end

local function is_trading()
    return memory.read_u16_le(gp + MODE_OFFSET) == MODE_TRADE
end

local function forfeit_check()
    return is_outside() and enemy_deaths < (3 * battle_number) and has_battled == 1
end

local function game_state()
	if in_trade_menu() and has_battled == 0 then
		return STATE_INIT
	elseif ((not is_outside()) and (not is_trading())) or in_battle_room() then
	    return STATE_BATTLE
	elseif is_trading() and in_trade_menu() then
	    return STATE_TRADE
	else
	    return STATE_NA
	end
end

local function calculate_fitness()
    fitness = (enemy_deaths * enemy_deaths) + ((battle_number - 1) * 5) + (has_battled * round_number)
end

local function advance_frames(instruct, cnt)
    cnt = cnt or 1
    instruct = instruct or {}
    for i=0, cnt, 1 do
        emu.frameadvance()
        joypad.set(instruct)
        -- ttl = ttl - 1
    end
end

-- ####################################
-- ####         GAME LOOP          ####
-- ####################################
print("Is client connected to socket server?")
print(comm.socketServerIsConnected())
print(comm.socketServerGetInfo())

function GameLoop()
    print("Beginning game loop...")

    -- initialize global vars
    local input_keys = {}
    ttl = 2500 -- 5000 -- 20000
    ally_deaths = 0
    enemy_deaths = 0
    last_dead_ally = nil
    last_dead_enemy = nil
    battle_number = 1
    round_number = 1
    fitness = 0
    has_battled = 0

    -- load save state
    print("Loading save slot 1...")
    savestate.loadslot(1)
    gp = memory.read_u32_le(0x02101D2C)
    refresh_gui()

    -- loop until a round is lost or TTL runs out
    while true do
        -- check game state
        if emu.framecount() % 5 == 0 then
            death_check()
            calculate_fitness()
            refresh_gui()
            -- battle lost?
            if ttl <= 0 or ally_deaths >= 3 then
                print("Battle lost.")
                break
            end
            -- battle forfeit?
            if forfeit_check() then
            	print("Battle forfeit.")
            	break
            end
            -- battle won?
            if enemy_deaths >= (3 * battle_number) then
                print("Battle won! "..battle_number)
                if battle_number % 7 == 0 then
                	print("Round won! "..round_number)
                	round_number = round_number + 1
                	has_battled = 0
                end
                battle_number = battle_number + 1
            	ally_deaths = 0
            	refresh_gui()
            end
        end

        -- manually move out of trivial states
        if is_outside() or is_trading() then
            while not (in_trade_menu() or in_battle_room()) do
            	advance_frames({A = "True"}, 1)
                advance_frames({}, 5)
                -- refresh_gui()
            end
        end

        -- forward-feed next decision
        if emu.framecount() % 55 == 0 then
            local decision = comm.socketServerScreenShotResponse()
            input_keys = {}
            input_keys[decision] = "True"
        end

        -- advance single frame
        advance_frames(input_keys)
        ttl = ttl - 1
    end

    -- end game loop
    print("Finished game loop.")
    print("Fitness: "..fitness)
    comm.socketServerSend("FITNESS:"..fitness)
    return fitness
end

-- repeat game loop until evaluation server finishes
while true do
    comm.socketServerSend("READY")
    local server_state = comm.socketServerResponse()
    print("Server State: "..server_state)
    if server_state == "READY" then
        -- start game loop
    	GameLoop()
    elseif server_state == "FINISHED" then
        -- Close emulator
        client.exit()
    end
end