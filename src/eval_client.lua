print("Is client connected to socket server?")
print(comm.socketServerIsConnected())
print(comm.socketServerGetInfo())

print("Loading save slot 1...")
savestate.loadslot(1)

Input = {}
while true do
    if emu.framecount() % 5000 == 0 then
        print("Breaking loop.")
    	break
    end
    if emu.framecount() % 60 == 0 then
        -- print("Sending screenshot to server...")
        local decision = comm.socketServerScreenShotResponse()
        print(decision)
        Input = {}
        if decision ~= "Null" then
            Input[decision] = "True"
        end
    end
    -- advance frame
    -- print("Advancing frame...")
    emu.frameadvance()
    joypad.set(Input)
end

-- Close emulator
comm.socketServerSend("")
client.exit()