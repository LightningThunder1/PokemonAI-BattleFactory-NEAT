import os
import socket
import random
import PIL
import numpy as np
from scipy.signal import correlate
from skimage.measure import block_reduce
from neat.nn import FeedForwardNetwork
import subprocess
from PIL import Image
import io
import sys


class EvaluationServer:

    HOST = "127.0.0.1"  # Standard loopback interface address (localhost)
    PORT = 65432  # Port to listen on (non-privileged ports are > 1023)
    EMU_PATH = '/home/javen/Desktop/PokeDS/BizHawk-2.9.1-linux-x64/EmuHawkMono.sh'
    KERNEL = np.array([[-1, -1, -1], [-1, 8, -1], [-1, -1, -1]])  # Edge Detection Kernel
    DECISIONS = ['B', 'A', 'Y', 'X', 'Up', 'Down', 'Left', 'Right']

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
                print(f"Connected by {addr}.")
                try:
                    while True:
                        # receive client buffered message
                        data = conn.recv(30000)

                        # client finished sending data
                        # print(len(data), data)
                        if not data:
                            break

                        # calculate message data index
                        d_index = data.find(b" ") + 1
                        # print(len(data))

                        # did client send a PNG?
                        if data[d_index:d_index + 4] == b"\x89PNG":
                            print("Processing image...")
                            # read image and convert to grayscale
                            img = PIL.Image.open(io.BytesIO(data[6:])).convert('L')
                            # img.show()
                            im = np.array(img)

                            # convolve image
                            im = correlate(im, self.KERNEL)
                            # PIL.Image.fromarray(np.uint8(im * 255)).show()

                            # reduce image dimensions
                            im = block_reduce(im, block_size=(4, 4), func=np.average)
                            # print(im.shape)
                            # PIL.Image.fromarray(im).show()

                            # TODO forward feed
                            decision = random.choice(self.DECISIONS)

                            # respond to client with decision
                            print(f"Decision: {decision}")
                            conn.sendall(
                                b'' + bytes(f"{len(decision)} {decision}", 'utf-8')
                            )
                except Exception as e:
                    print(e)
                    # close server
                    s.shutdown(socket.SHUT_RDWR)
                    s.close()

            # close server
            s.shutdown(socket.SHUT_RDWR)
            s.close()

        # return fitness score
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
