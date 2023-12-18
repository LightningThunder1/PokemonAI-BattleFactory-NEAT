print("Is client connected to socket server?")
print(comm.socketServerIsConnected())
print(comm.socketServerGetInfo())

print("Loading save slot 1...")
savestate.loadslot(1)

-- comm.socketServerSend("Hello!")
-- print(comm.socketServerResponse())
-- print("Server responded...")
-- print(client.screenwidth())
-- print(client.screenheight())

while true do
    if emu.framecount() % 1000 == 0 then
        print("Breaking loop.")
    	break
    end
    if emu.framecount() % 180 == 0 then
        print("Sending screenshot to server...")
        comm.socketServerScreenShot()
        comm.socketServerScreenShotResponse()
    end
    -- advance frame
    -- print("Advancing frame...")
    emu.frameadvance()
end

-- Close emulator
client.exit()