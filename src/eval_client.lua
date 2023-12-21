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
	HeldItem = 0x0,
	Ability = 0x0,
	EVs = {},
	Moves = {},
	PPs = {},
	IVs = {},
	Level = 0x0,
	HP = 0x0,
	MaxHP = 0x0,
	ATK = 0x0,
	DEF = 0x0,
	SPEED = 0x0,
	SPA = 0x0,
	SPD = 0x0,
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


-- ### POINTERS ###
gameID = memory.read_s32_le(0x23FFE0C) -- 0x45555043
gp = memory.read_s32_le(0x02101D2C)  -- game pointer
sbp = gp + 0xCFF4 -- small block pointer
pbp = sbp + 0xA0 -- party pokeblock pointer


-- ### PARTY POKEMON ###

-- party pokemon #1
pbp = pbp + (0xEC * 0) -- offset to pokemon-1 block
local pid = memory.read_u32_le(pbp + 0x00) -- personality value
local checksum = memory.read_u16_le(pbp + 0x06)-- pokeblock checksum
local shift = tostring(((pid & 0x3E000) >> 0xD) % 24) -- data block shift value
print("Shift Value: ", shift)
print("Shuffle Order:\n", shuffleOrder[shift])
print("Checksum: ", checksum)

-- decrypt pokemon data bytes
local X = { checksum }
local D = {}
for n = 1,65,1 do
	X[n+1] = mult32(X[n], 0x41C64E6D) + 0x6073
	D[n] = memory.read_u16_le(pbp + 0x06 + (n * 0x02))
	D[n] = D[n] ~ (X[n+1] >> 16)
	print(n, string.format("%X", D[n]))
end

local function fetch_v(block_offset, var_offset)
	return D[((block_offset + (var_offset - 0x08)) / 2) + 1]
end

-- calculate shuffled block offsets
local a_offset = (shuffleOrder[shift]["A"] - 1) * 0x20
local b_offset = (shuffleOrder[shift]["B"] - 1) * 0x20
local c_offset = (shuffleOrder[shift]["C"] - 1) * 0x20
local d_offset = (shuffleOrder[shift]["D"] - 1) * 0x20

-- instantiate new pokemon obj and populate vars
local pokemon = table.shallow_copy(pokemon_struct)
pokemon.ID = fetch_v(a_offset, 0x08)
pokemon.HeldItem = fetch_v(a_offset, 0x0A)
pokemon.Ability = fetch_v(a_offset, 0x15)

print(pokemon)


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

