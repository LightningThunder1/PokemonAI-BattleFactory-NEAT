import json
import os
import socket
import random
from collections.abc import MutableMapping

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
    ACTIONS = ['B', 'A', 'Y', 'X', 'Up', 'Down', 'Left', 'Right', 'Null']
    EVAL_SCRIPT = None
    PNG_HEADER = b"\x89PNG"
    READY_STATE = b"5 READY"
    FINISH_STATE = b"8 FINISHED"

    def __init__(self, game_mode: str):
        if game_mode == "open_world":
            self.EVAL_SCRIPT = "./src/eval_openworld.lua"
        if game_mode == "battle_factory":
            self.EVAL_SCRIPT = "./src/eval_battlefactory.lua"

    def eval_genomes(self, genomes: [FeedForwardNetwork]) -> None:
        """
        Evaluates a population of genomes.
        """
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            print("Initializing socket server...")
            # bind socket server
            s.bind((self.HOST, self.PORT))
            s.listen()

            # spawn agent
            self.spawn_client()
            print("Spawned emulator client.")

            # wait for agent to connect to socket
            client, addr = s.accept()
            with client:
                print(f"Connected by {addr}.")
                try:
                    # evaluate each genome
                    for genome in genomes:
                        # wait for client to be ready
                        while True:
                            data = client.recv(1024)
                            if not data:
                                raise Exception("Connection closed before finishing evaluation.")
                            if data == self.READY_STATE:
                                print("Client is ready to evaluate next genome.")
                                client.sendall(self.READY_STATE)
                                break

                        # begin genome evaluation
                        fitness = self._eval(client, genome)
                        genome.fitness = fitness

                    # send finish state to client
                    client.sendall(self.FINISH_STATE)

                except Exception as e:
                    print(e)

            # close server
            s.shutdown(socket.SHUT_RDWR)
            s.close()

    def _eval(self, client, genome: FeedForwardNetwork) -> float:
        """
        Evaluates a single genome.
        """
        print("\nEvaluating genome...")
        # init fitness
        fitness = 0.0

        # repeat game loop
        while True:
            # receive client buffered message
            data = client.recv(30000)

            # client finished sending data
            # print(len(data), data)
            if not data:
                raise Exception("Connection closed before finishing evaluation.")
            if data == self.FINISH_STATE:
                print("Client is finished evaluating genome.")
                break

            # calculate message data index
            m_index = self.calculate_mindex(data)

            # did client send a PNG?
            if data[m_index:m_index + 4] == self.PNG_HEADER:
                print("Processing image...")
                outputs = self._ff_screenshot(data[6:], genome)
                decision = self.ACTIONS[outputs.index(max(outputs))]
                # decision = random.choice(self.DECISIONS)

                # respond to client with decision
                print(f"Decision: {decision}")
                client.sendall(b'' + bytes(f"{len(decision)} {decision}", 'utf-8'))

        # return fitness score
        print(f"Genome fitness: {fitness}")
        return fitness

    def _ff_screenshot(self, png_data, genome):
        """
        Forward-feeds screenshot data through genome neural network.
        """
        # read image and convert to grayscale
        img = PIL.Image.open(io.BytesIO(png_data)).convert('L')
        # img.show()
        im = np.array(img)

        # convolve image
        im = correlate(im, self.KERNEL)
        # PIL.Image.fromarray(np.uint8(im * 255)).show()

        # reduce image dimensions
        im = block_reduce(im, block_size=(4, 4), func=np.average)
        # print(im.shape)
        # PIL.Image.fromarray(im).show()

        # forward feed
        im = im.reshape(-1)
        outputs = genome.activate(im)
        return outputs

    @classmethod
    def sort_dict(cls, item: dict):
        """
        Recursively sorts a nested dictionary.
        """
        for k, v in sorted(item.items()):
            item[k] = sorted(v) if isinstance(v, list) else v
        return {k: cls.sort_dict(v) if isinstance(v, dict) else v for k, v in sorted(item.items())}

    @classmethod
    def flatten_dict(cls, d: MutableMapping, parent_key: str = '', sep: str = '.') -> MutableMapping:
        items = []
        for k, v in d.items():
            new_key = parent_key + sep + k if parent_key else k
            if isinstance(v, MutableMapping):
                items.extend(cls.flatten_dict(v, new_key, sep=sep).items())
            else:
                items.append((new_key, v))
        return dict(items)

    @staticmethod
    def calculate_mindex(data):
        """
        Calculates the message index for the received data.
        """
        return data.find(b" ") + 1

    def spawn_client(self) -> None:
        """
        Spawns the emulator process and starts the eval_client.lua script.
        :return: None
        """
        subprocess.Popen([
            self.EMU_PATH,
            f'--socket_port={self.PORT}',
            f'--socket_ip={self.HOST}',
            f'--lua={os.path.abspath(self.EVAL_SCRIPT)}'
        ])
