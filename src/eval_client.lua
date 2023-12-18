print("Is client connected to socket server?")
print(comm.socketServerIsConnected())
print(comm.socketServerGetInfo())

print("Loading save slot 1...")
savestate.loadslot(1)

-- comm.socketServerSend("Hello!")
-- print(comm.socketServerResponse())
-- print("Server responded...")
print(client.screenwidth())
print(client.screenheight())

comm.socketServerSend("TEST!")
comm.socketServerScreenShot()
-- print(comm.socketServerScreenShotResponse())
-- print("Server responded...")

-- Close emulator
client.exit()