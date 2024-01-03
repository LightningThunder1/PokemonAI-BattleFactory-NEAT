import json
import logging
import os
import signal
import socket
import random
from collections.abc import MutableMapping
import PIL
import neat
import numpy as np
from scipy.signal import correlate
from skimage.measure import block_reduce
from neat.nn import FeedForwardNetwork
import subprocess
from PIL import Image
import io
import sys


class EvaluationServer:
    # consts
    HOST = "127.0.0.1"  # Standard loopback interface address (localhost)
    PORT = 0  # Port to listen on (non-privileged ports are > 1023)
    EMU_PATH = '/home/javen/Desktop/PokeDS/BizHawk-2.9.1-linux-x64/EmuHawkMono.sh'
    KERNEL = np.array([[-1, -1, -1], [-1, 8, -1], [-1, -1, -1]])  # Edge Detection Kernel
    PNG_HEADER = (b"\x89PNG", 7)
    BF_STATE_HEADER = (b"BF_STATE", 8)
    READY_STATE = b"5 READY"
    FINISH_STATE = b"8 FINISHED"
    FITNESS_HEADER = (b"FITNESS:", 8)
    LOG_HEADER = (b"LOG:", 4)

    def __init__(self, game_mode: str):
        self.client_pid = None  # emulator client process ID
        socket.setdefaulttimeout(30)  # default socket timeout
        self.evaluated_genomes = []  # track evaluated genomes if socket timeout occurs
        self.genome_finished = False  # global var for evaluating genomes

        logging.basicConfig(
            filename="./logs/eval_server.log",
            filemode='a',
            format='%(asctime)s %(levelname)s %(message)s',
            datefmt='%H:%M:%S',
            level=logging.DEBUG
        )

        # set game mode params
        if game_mode == "open_world":
            self.EVAL_SCRIPT = "./src/eval_openworld.lua"
            self.ACTIONS = ['B', 'A', 'Y', 'X', 'Up', 'Down', 'Left', 'Right', 'Null']
        if game_mode == "battle_factory":
            self.EVAL_SCRIPT = "./src/eval_battlefactory.lua"
            # self.ACTIONS = ['B', 'A', 'Up', 'Down', 'Left', 'Right']
            self.ACTIONS = ['Move1', 'Move2', 'Move3', 'Move4', 'Poke1', 'Poke2', 'Poke3', 'Poke4', 'Poke5', 'Poke6']

    def eval_genomes(self, genomes, config, gen_id) -> bool:
        """
        Evaluates a population of genomes.
        """
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            logging.info("Initializing socket server...")

            # bind socket server
            self.PORT = 0  # reset port
            s.bind((self.HOST, self.PORT))
            self.PORT = s.getsockname()[1]
            logging.info(f'Socket server: listening on port {self.PORT }')
            s.listen()

            # spawn agent
            self.client_pid = self.spawn_client().pid

            # wait for agent to connect to socket
            client, addr = s.accept()
            with client:
                logging.info(f"Connected by {addr}.")
                try:
                    logging.info(f"Beginning generation evaluation: completed={len(self.evaluated_genomes)}, total={len(genomes)}\n")
                    # evaluate each genome
                    for idx, (_id, genome) in enumerate(genomes):
                        # check if genome was already evaluated
                        if _id in self.evaluated_genomes:
                            continue

                        # create NN from genome
                        nn = neat.nn.FeedForwardNetwork.create(genome, config)
                        logging.info(f"[Gen #: {gen_id}, Index #: {len(self.evaluated_genomes)}/{len(genomes)-1}, Genome #: {_id}]")

                        # wait for client to be ready
                        while True:
                            data = client.recv(1024)
                            if not data:
                                raise ConnectionClosedException
                            if data == self.READY_STATE:
                                logging.info("Client is ready to evaluate next genome.")
                                client.sendall(self.READY_STATE)
                                break

                        # begin genome evaluation
                        fitness = self._eval(client, nn)
                        # successful evaluation
                        genome.fitness = fitness
                        self.evaluated_genomes.append(_id)

                    # send finish state to client
                    data = client.recv(1024)
                    client.sendall(self.FINISH_STATE)
                    logging.info("Finished evaluating genomes.\n")

                except (ConnectionClosedException, KeyboardInterrupt) as e:
                    self.close_server(s)
                    logging.error("Program interruption! Exiting...\n")
                    sys.exit(e)
                except socket.timeout as e:
                    logging.error("Socket timed out while evaluating genome!\n")
                    self.close_server(s)
                    return False
                except Exception as e:
                    logging.error(str(e))
                    self.close_server(s)
                    sys.exit(str(e))

            # successful generation evaluation
            self.close_server(s)
            self.evaluated_genomes = []  # reset evaluated genomes
            return True

    def _eval(self, client, net: FeedForwardNetwork) -> float:
        """
        Evaluates a single genome.
        """
        logging.info("Evaluating genome...")
        # init fitness
        fitness = 0.0
        self.genome_finished = False

        # repeat game loop
        while not self.genome_finished:
            # receive client buffered message
            data = client.recv(8192)

            # client finished sending data
            if not data:
                raise ConnectionClosedException

            # Parse received data into individual message(s) and process
            for msg in self._parse_msgs(data):

                # is msg a fitness score?
                if msg[:self.FITNESS_HEADER[1]] == self.FITNESS_HEADER[0]:
                    logging.info("Client is finished evaluating genome.")
                    fitness = float(msg[self.FITNESS_HEADER[1]:])
                    self.genome_finished = True

                # is msg a log?
                elif msg[:self.LOG_HEADER[1]] == self.LOG_HEADER[0]:
                    logging.debug(msg[self.LOG_HEADER[1]:])

                # is msg a battle factory input state?
                elif msg[:self.BF_STATE_HEADER[1]] == self.BF_STATE_HEADER[0]:
                    output_msg = self._ff_game_state(
                        msg[self.BF_STATE_HEADER[1]:], net
                    )
                    # respond with output message
                    client.sendall(b'' + bytes(f"{len(output_msg)} {output_msg}", 'utf-8'))

                # is msg a state screenshot?
                elif msg[:self.PNG_HEADER[1]] == self.PNG_HEADER[0]:
                    decision = self._ff_screenshot(msg, net)
                    # respond to client with decision
                    client.sendall(b'' + bytes(f"{len(decision)} {decision}", 'utf-8'))

        # return fitness score
        logging.info(f"Genome fitness: {fitness}\n")
        return fitness

    @classmethod
    def _parse_msgs(cls, _msg) -> [bytes]:
        """
        Parse received client data into individual message(s).
        """
        if not _msg:
            return []
        split = _msg.split(b" ", 1)
        size = int(split[0])
        return [split[1][:size]] + cls._parse_msgs(split[1][size:])

    def _ff_game_state(self, state: bytes, net: FeedForwardNetwork) -> str:
        """
        Forward-feeds game state bytes through genome neural network.
        """
        logging.info("Evaluating game state...")
        # read and sort input state
        bf_state = json.loads(state)
        bf_state = self.sort_dict(bf_state)
        # logging.info(json.dumps(bf_state, indent=4))

        # flatten input state
        bf_state = self.flatten_dict(bf_state)
        logging.debug(bf_state)
        input_layer = np.array(list(bf_state.values()))

        # forward feed
        output_layer = net.activate(input_layer)
        output_msg = "{ " + ", ".join([str(round(x, 10)) for x in output_layer]) + " }"
        logging.debug(output_msg)
        return output_msg

    def _ff_screenshot(self, png: bytes, net: FeedForwardNetwork):
        """
        Forward-feeds screenshot data through genome neural network.
        """
        logging.info("Evaluating game screenshot...")
        # read image and convert to grayscale
        img = PIL.Image.open(io.BytesIO(png)).convert('L')
        # img.show()
        im = np.array(img)

        # convolve image
        im = correlate(im, self.KERNEL)
        # PIL.Image.fromarray(np.uint8(im * 255)).show()

        # reduce image dimensions
        im = block_reduce(im, block_size=(4, 4), func=np.average)
        # logging.info(im.shape)
        # PIL.Image.fromarray(im).show()

        # forward feed
        im = im.reshape(-1)
        outputs = net.activate(im)
        decision = self.ACTIONS[outputs.index(max(outputs))]
        return decision

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

    def spawn_client(self):
        """
        Spawns the emulator process and starts the eval_client.lua script.
        :return: Process ID
        """
        logging.info("Spawning emulator client process...")
        return subprocess.Popen([
            self.EMU_PATH,
            f'--socket_port={self.PORT}',
            f'--socket_ip={self.HOST}',
            f'--lua={os.path.abspath(self.EVAL_SCRIPT)}'
        ], preexec_fn=os.setsid)

    def kill_client(self, pid):
        """
        Kills the emulator client process group.
        :return: None
        """
        # Send the signal to all the process groups
        os.killpg(os.getpgid(pid), signal.SIGTERM)

    def close_server(self, s):
        """
        Forcibly closes the socket server and client process.
        """
        self.kill_client(self.client_pid)
        s.shutdown(socket.SHUT_RDWR)
        s.close()


class ConnectionClosedException(Exception):
    def __init__(self, message="Client connection closed before finishing evaluation."):
        self.message = message
        super().__init__(self.message)
