
print(comm.socketServerIsConnected())
print(comm.socketServerGetInfo())

comm.socketServerSend("Hello!")

print(comm.socketServerResponse())
print("Server responded...")