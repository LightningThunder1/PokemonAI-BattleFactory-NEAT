import os
import socket
from neat.nn import FeedForwardNetwork
import subprocess


class EvaluationServer:

    HOST = "127.0.0.1"  # Standard loopback interface address (localhost)
    PORT = 65432  # Port to listen on (non-privileged ports are > 1023)
    EMU_PATH = '/home/javen/Desktop/PokeDS/BizHawk-2.9.1-linux-x64/EmuHawkMono.sh'

    def __init__(self):
        pass

    def eval_genome(self, genome: FeedForwardNetwork) -> float:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            print("Initializing socket server...")
            # bind socket server
            s.bind((self.HOST, self.PORT))
            s.listen()

            # spawn agent
            self.spawn_agent()
            print("Spawned agent.")

            # wait for agent to connect to socket
            conn, addr = s.accept()
            with conn:
                print(f"Connected by {addr}")
                while True:
                    data = conn.recv(1024)
                    print(data)
                    if not data:
                        break
                    conn.sendall(data)
        return 0.0

    def spawn_agent(self) -> None:
        """
        Spawns the emulator process and starts the eval_client.lua script.
        :return: None
        """
        subprocess.Popen([
            self.EMU_PATH,
            f'--socket_port={self.PORT}',
            f'--socket_ip={self.HOST}',
            f'--lua={os.path.abspath("./src/eval_client.lua")}'
        ])

