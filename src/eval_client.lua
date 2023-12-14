print("Is client connected to socket server?")
print(comm.socketServerIsConnected())
print(comm.socketServerGetInfo())

print("Loading save slot 1...")
savestate.loadslot(1)

comm.socketServerSend("Hello!")

print(comm.socketServerResponse())
print("Server responded...")