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