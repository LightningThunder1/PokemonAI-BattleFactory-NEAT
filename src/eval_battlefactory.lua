-- input layer data structure
local state_struct = {
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

-- read pokemon data
local function read_pokemon(mode)
    local pk = { ID=0, HeldItem=0, Ability=0, Moves={}, Stats={} }
    pk.ID = 0x123
    pk.HeldItem = 0x123
    pk.Ability = 0x123
    pk.Moves = {
        Move1 = {
            ID = 0x1,
            PP = 0xF
        };
        Move2 = {
            ID = 0x2,
            PP = 0xF
        };
        Move3 = {
            ID = 0x3,
            PP = 0xF
        };
        Move4 = {
            ID = 0x4,
            PP = 0xF
        };
    }
    pk.Stats = {
        HP = 0x10,
        MAXHP = 0x10,
        ATK = 0xF,
        DEF = 0xF,
        SPEED = 0xF,
        SPA = 0xF,
        SPD = 0xF,
    }
    return pk
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


-- ### GAME LOOP ###
print("Is client connected to socket server?")
print(comm.socketServerIsConnected())
print(comm.socketServerGetInfo())

function GameLoop()
    print("Beginning game loop...")
    -- load save state
    print("Loading save slot 1...")
    savestate.loadslot(1)
    local input_keys = {}
    while true do
        if emu.framecount() % 5500 == 0 then
            break
        end
        if emu.framecount() % 500 == 0 then
            -- read game state
            state_struct.Mode = 0
            state_struct.Ally1 = read_pokemon(0)
            state_struct.Ally2 = read_pokemon(0)
            state_struct.Ally3 = read_pokemon(0)
            state_struct.Ally4 = read_pokemon(0)
            state_struct.Ally5 = read_pokemon(0)
            state_struct.Ally6 = read_pokemon(0)
            state_struct.Enemy1 = read_pokemon(0)
            state_struct.Enemy2 = read_pokemon(0)
            state_struct.Enemy3 = read_pokemon(0)
            -- process game state
            comm.socketServerSend("BF_STATE"..serialize_table(state_struct))
            local outputs = comm.socketServerResponse()
            print(outputs)
        end
        -- advance frame
        emu.frameadvance()
        -- joypad.set(input_keys)
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