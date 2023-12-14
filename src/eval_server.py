import socket
import neat
from neat.nn import FeedForwardNetwork


class EvaluationServer:

    HOST = "127.0.0.1"  # Standard loopback interface address (localhost)
    PORT = 65432  # Port to listen on (non-privileged ports are > 1023)

    def __init__(self):
        pass

    def eval_genome(self, genome: FeedForwardNetwork) -> float:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            # bind socket server
            s.bind((self.HOST, self.PORT))
            s.listen()

            # spawn agent

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
