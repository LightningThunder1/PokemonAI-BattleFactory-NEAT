--[[
References:
	- https://bulbapedia.bulbagarden.net/wiki/Pok%C3%A9mon_data_structure_(Generation_IV)#Encrypted_bytes_2
	- https://bulbapedia.bulbagarden.net/wiki/Save_data_structure_(Generation_IV)
	- https://projectpokemon.org/home/docs/gen-4/platinum-save-structure-r81/
	- https://projectpokemon.org/docs/gen-4/pkm-structure-r65/
	- https://tasvideos.org/UserFiles/Info/45193606014900979
--]]


-- ### CONSTANTS ###

-- orderings of shuffled pokemon data blocks from shift-values
shuffleOrder = {
	["00"] = {A = 1, B = 2, C = 3, D = 4};
	["11"] = {B = 1, D = 2, C = 3, A = 4};
}

-- pokemon data structure
pokemon_struct = {
	ID = 0x0,
	PID = 0x0,
	HeldItem = 0x0,
	Ability = 0x0,
	Moves = {
		{ID = 0x0, PP = 0x0},
		{ID = 0x0, PP = 0x0},
		{ID = 0x0, PP = 0x0},
		{ID = 0x0, PP = 0x0},
	},
	IVs = {
		HP = 0x0,
		ATK = 0x0,
		DEF = 0x0,
		SPEED = 0x0,
		SPA = 0x0,
		SPD = 0x0,
	},
	EVs = {
		HP = 0x0,
		ATK = 0x0,
		DEF = 0x0,
		SPEED = 0x0,
		SPA = 0x0,
		SPD = 0x0,
	},
	Stats = {
		Status = 0x0,
		Level = 0x0,
		EXP = 0x0,
		HP = 0x0,
		MaxHP = 0x0,
		ATK = 0x0,
		DEF = 0x0,
		SPEED = 0x0,
		SPA = 0x0,
		SPD = 0x0,
	}
}

-- used in PRNG state calculation
function mult32(a, b)
	local c = a >> 16
	local d = a % 0x10000
	local e = b >> 16
	local f = b % 0x10000
	local g = (c * f + d * e) % 0x10000
	local h = d * f
	local i = g * 0x10000 + h
	return i
end

function table.shallow_copy(t)
	local t2 = {}
	for k,v in pairs(t) do
		t2[k] = v
	end
	return t2
end

function decrypt(seed, addr, words)
	-- decrypt pokemon data bytes
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

local function numberToBinary(x)
	ret = ""
	while x~=1 and x~=0 do
		ret = tostring(x % 2)..ret
		x = math.modf(x / 2)
	end
	ret = tostring(x)..ret
	return ret
end


-- ### PARTY POKEMON ###
local gameID = memory.read_s32_le(0x23FFE0C) -- 0x45555043
local gp = memory.read_s32_le(0x02101D2C)  -- game pointer
local sbp = gp + 0xCFF4 -- small block pointer
local pbp = sbp + 0xA0 -- party pokeblock pointer


local function read_pokemon(pp, party_idx)
	-- offset pokemon pointer for party index
	pp = pp + (0xEC * party_idx)

	-- pokemon decryption vars
	local pid = memory.read_u32_le(pp)
	local checksum = memory.read_u16_le(pp + 0x06)
	local shift = tostring(((pid & 0x3E000) >> 0xD) % 24)

	-- decrypt pokemon bytes
	local D = decrypt(checksum, pp + 0x08, 64) -- data
	local B = decrypt(pid, pp + 0x88, 50) -- battle stats

	local function fetch_Dv(block_offset, var_offset)
		return D[((block_offset + var_offset) / 2) + 1]
	end

	local function fetch_Bv(var_offset)
		return B[((var_offset - 0x88) / 2) + 1]
	end

	-- calculate shuffled block offsets
	local a_offset = (shuffleOrder[shift]["A"] - 1) * 0x20
	local b_offset = (shuffleOrder[shift]["B"] - 1) * 0x20
	local c_offset = (shuffleOrder[shift]["C"] - 1) * 0x20
	local d_offset = (shuffleOrder[shift]["D"] - 1) * 0x20

	-- instantiate new pokemon obj and populate vars
	local pokemon = table.shallow_copy(pokemon_struct)
	pokemon.ID = fetch_Dv(a_offset, 0x08 - 0x08)
	pokemon.PID = pid
	pokemon.HeldItem = fetch_Dv(a_offset, 0x0A - 0x08)
	pokemon.Ability = fetch_Dv(a_offset, 0x15 - 0x08)
	pokemon.EXP = fetch_Dv(a_offset, 0x10 - 0x08) -- TODO
	pokemon.Moves = {
		{
			ID = fetch_Dv(b_offset, 0x28 - 0x28) & 0xFFFF,
			PP = fetch_Dv(b_offset, 0x30 - 0x28) & 0x00FF,
		};
		{
			ID = fetch_Dv(b_offset, 0x2A - 0x28) & 0xFFFF,
			PP = fetch_Dv(b_offset, 0x30 - 0x28) >> 8,
		};
		{
			ID = fetch_Dv(b_offset, 0x2C - 0x28) & 0xFFFF,
			PP = fetch_Dv(b_offset, 0x32 - 0x28) & 0x00FF,
		};
		{
			ID = fetch_Dv(b_offset, 0x2E - 0x28) & 0xFFFF,
			PP = fetch_Dv(b_offset, 0x32 - 0x28) >> 8,
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

-- print(pokemon)

-- print("MOVES")
-- print(pokemon.Moves[1])
-- print(pokemon.Moves[2])
-- print(pokemon.Moves[3])
-- print(pokemon.Moves[4])

-- print("STATS")
-- print(pokemon.Stats)

-- print("EVs")
-- print(pokemon.EVs)

-- print("IVs")
-- -- print(fetch_Dv(b_offset, 0x38 - 0x28) & 0xFFFF)
-- -- print(fetch_Dv(b_offset, 0x3A - 0x28) & 0xFFFF)
-- print(pokemon.IVs)


-- ### GAME LOOP ###
print("Is client connected to socket server?")
print(comm.socketServerIsConnected())
print(comm.socketServerGetInfo())

function GameLoop()
    print("Beginning game loop...")
    -- load save state
    print("Loading save slot 1...")
    savestate.loadslot(1)
    local input = {}
    while true do
        -- break game loop
        if emu.framecount() % 1500 == 0 then
            break
        end
        -- get next decision
        if emu.framecount() % 60 == 0 then
            -- print("Sending screenshot to server...")
            local decision = comm.socketServerScreenShotResponse()
            print(decision)
            input = {}
            if decision ~= "Null" then
                input[decision] = "True"
            end
        end
        -- advance frame
        emu.frameadvance()
        joypad.set(input)
    end
    -- end game loop
    print("Finished game loop.")
    comm.socketServerSend("FINISHED")
end

-- repeat game loop until evaluation server finishes
while true do
    comm.socketServerSend("READY")
    local server_state = comm.socketServerResponse()
    if server_state == "READY" then
        -- start game loop
    	GameLoop()
    elseif server_state == "FINISHED" then
        -- Close emulator
        comm.socketServerSend("")
        client.exit()
    end
end

