import json
import logging
import math
import os
import signal
import socket
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
from encoder import Encoder
import threading


class EvaluationServer:
    # consts
    HOST = "127.0.0.1"  # Standard loopback interface address (localhost)
    PORT = 0  # Port to listen on (non-privileged ports are > 1023)
    EMU_PATH = '../BizHawk-2.9.1-linux-x64/EmuHawkMono.sh'
    N_CLIENTS = 5  # number of concurrent clients to evaluate genomes
    DEBUG_ID = -1  # for debugging specific genomes

    KERNEL = np.array([[-1, -1, -1], [-1, 8, -1], [-1, -1, -1]])  # Edge Detection Kernel
    PNG_HEADER = (b"\x89PNG", 7)
    BF_STATE_HEADER = (b"BF_STATE", 8)
    READY_STATE = b"5 READY"
    FINISH_STATE = b"8 FINISHED"
    FITNESS_HEADER = (b"FITNESS:", 8)
    LOG_HEADER = (b"LOG:", 4)

    def __init__(self, game_mode: str):
        # default socket timeout
        socket.setdefaulttimeout(300)

        # gen evaluation vars
        self.evaluated_genomes = []  # track evaluated genomes if socket timeout occurs
        self.client_pids = None  # emulator client process ID(s)
        self.eval_idx = None  # thread-safe evaluation index
        self.genomes = None  # list of genomes to evaluate
        self.config = None  # config obj for creating networks
        self.mutex = None  # for thread-safe eval_idx access
        self.logger = None  # evaluation server logger
        self.gen_id = None  # generation ID
        self.eval_failure = False

        # set game mode params
        if game_mode == "open_world":
            self.EVAL_SCRIPT = "./src/eval_openworld.lua"
            self.ACTIONS = ['B', 'A', 'Y', 'X', 'Up', 'Down', 'Left', 'Right', 'Null']
        if game_mode == "battle_factory":
            self.EVAL_SCRIPT = "./src/eval_battlefactory.lua"
            self.ACTIONS = ['Move1', 'Move2', 'Move3', 'Move4', 'Poke1', 'Poke2', 'Poke3', 'Poke4', 'Poke5', 'Poke6']

    def eval_genomes(self, genomes, config, gen_id) -> bool:
        """
        Evaluates a population of genomes.
        """
        # set generation vars
        self.logger = self._init_logger(gen_id)  # init the logger for this generation
        self.mutex = threading.Lock()
        self.client_pids = []
        self.eval_idx = 0
        self.config = config
        self.genomes = genomes
        self.gen_id = gen_id

        # initial gen logs
        self.logger.info(f"****** Evaluating Generation {gen_id} ******")
        self.logger.info(f"completed={len(self.evaluated_genomes)}, total={len(genomes)}")

        # init socket server
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # TODO move to init()
        self.logger.debug("Initializing socket server...")

        # bind socket server
        self.PORT = 0  # reset port
        server.bind((self.HOST, self.PORT))
        self.PORT = server.getsockname()[1]

        # listen for incoming connections
        self.logger.debug(f'Socket server: listening on port {self.PORT }')
        server.listen()

        # handle client thread exceptions
        def handle_exceptions(args):
            self.logger.error(args.exc_value)
            self.eval_failure = True
            self.close_server(server)  # TODO impl kill_clients()
        threading.excepthook = handle_exceptions

        # spawn client processes and evaluate genomes
        client_threads = []
        for _ in range(self.N_CLIENTS):
            # create client process and record pid
            self.spawn_client()

            # wait for agent process to connect to socket
            client, addr = server.accept()
            self.logger.debug(f"Connected by {addr}.")

            # start a new thread to handle the client process
            t = threading.Thread(target=self._handle_client, args=(client,))
            client_threads.append(t)
            t.start()

        # wait for all client processes to finish
        try:
            for t in client_threads:
                t.join()
        except KeyboardInterrupt:  # TODO move outside of eval_server
            self.logger.error("KeyboardInterrupt")
            self.close_server(server)
            sys.exit()

        # exit program if an evaluation failure occurred
        if self.eval_failure:
            self.logger.error("An evaluation exception occurred!")
            sys.exit()

        # exit program if debugging
        if self.DEBUG_ID >= 0:
            logging.info("Finished debugging genome.")
            self.close_server(server)
            sys.exit()

        # successful generation evaluation
        self.close_server(server)
        self.evaluated_genomes = []  # reset evaluated genomes
        return True

    def _handle_client(self, client) -> None:
        """
        Handles the client process in asynchronously evaluating genomes.
        """
        while True:
            # evaluate next genome
            idx, _id, genome = self._get_next(self.genomes)
            if not genome:
                self.logger.debug("No genomes are left for client to evaluate...")
                break

            # create NN from genome
            net = neat.nn.FeedForwardNetwork.create(genome, self.config)
            self.logger.info(
                f"[Gen #: {self.gen_id}, Index #: {idx}/{len(self.genomes) - 1}, Genome #: {_id}]")

            # wait for client to be ready
            while True:
                data = client.recv(1024)
                if not data:
                    raise ConnectionClosedException
                if data == self.READY_STATE:
                    self.logger.debug("Client is ready to evaluate next genome.")
                    client.sendall(self.READY_STATE)
                    break

            # begin genome evaluation
            genome.fitness = self._eval(client, net)
            self.evaluated_genomes.append(_id)  # successful evaluation
            self.logger.info(f"Genome #{_id} fitness: {genome.fitness}")

        # send finish state to client
        # data = client.recv(1024)
        client.sendall(self.FINISH_STATE)

    def _eval(self, client, net: FeedForwardNetwork) -> float:
        """
        Evaluates a single genome.
        """
        self.logger.debug("Evaluating genome...")
        # init fitness
        fitness = 0.0
        genome_finished = False

        # repeat game loop
        while not genome_finished:
            # receive client buffered message
            data = client.recv(8192)

            # client finished sending data
            if not data:
                raise ConnectionClosedException

            # Parse received data into individual message(s) and process
            for msg in self._parse_msgs(data):

                # is msg a fitness score?
                if msg[:self.FITNESS_HEADER[1]] == self.FITNESS_HEADER[0]:
                    self.logger.debug("Client is finished evaluating genome.")
                    fitness = float(msg[self.FITNESS_HEADER[1]:])
                    genome_finished = True

                # is msg a log?
                elif msg[:self.LOG_HEADER[1]] == self.LOG_HEADER[0]:
                    self.logger.debug(msg[self.LOG_HEADER[1]:])

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
        return fitness

    def _get_next(self, genomes):
        """
        Retrieves the next genome to evaluate in a thread-safe way.
        :returns (genome index, genome ID, genome), or None if no available genomes are remaining.
        """
        idx, _id, genome = None, None, None
        self.mutex.acquire()
        while genome is None and self.eval_idx < len(genomes):
            t_id, t_genome = genomes[self.eval_idx]
            # find next available genome
            if t_genome not in self.evaluated_genomes and not (0 <= self.DEBUG_ID != t_id):
                idx, _id, genome = self.eval_idx, t_id, t_genome
                # if debug genome was found, prevent other evaluations
                if 0 <= self.DEBUG_ID == t_id:
                    self.eval_idx = len(genomes)
            self.eval_idx += 1
        self.mutex.release()
        return idx, _id, genome

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
        self.logger.debug("Evaluating game state...")
        # read and sort input state
        bf_state = json.loads(state)
        bf_state = self.sort_dict(bf_state)
        self.logger.debug(bf_state)

        # vectorize input state
        input_layer = Encoder.vectorize_state(bf_state)
        # self.logger.debug(input_layer)

        # forward feed
        output_layer = net.activate(input_layer)
        output_msg = "{ " + ", ".join(["{:.32f}".format(x) for x in output_layer]) + " }"
        self.logger.debug(output_msg)
        return output_msg

    def _ff_screenshot(self, png: bytes, net: FeedForwardNetwork):
        """
        Forward-feeds screenshot data through genome neural network.
        """
        self.logger.debug("Evaluating game screenshot...")
        # read image and convert to grayscale
        img = PIL.Image.open(io.BytesIO(png)).convert('L')
        # img.show()
        im = np.array(img)

        # convolve image
        im = correlate(im, self.KERNEL)
        # PIL.Image.fromarray(np.uint8(im * 255)).show()

        # reduce image dimensions
        im = block_reduce(im, block_size=(4, 4), func=np.average)
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
    def _init_logger(cls, gen_id: int):
        """
        Initializes the EvaluationServer logger.
        Logs NEAT training results to logs/trainer.log and debug logs to console.
        """
        logger = logging.getLogger("eval_server")
        logger.setLevel(logging.DEBUG)
        log_format = logging.Formatter('%(asctime)s %(levelname)s %(message)s', datefmt='%H:%M:%S')

        # remove any existing handlers
        if logger.hasHandlers():
            logger.handlers.clear()

        # create and add handlers
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(log_format)
        stream_handler.setLevel(logging.INFO)
        logger.addHandler(stream_handler)

        info_handler = logging.FileHandler(f"./logs/eval_server-{gen_id}.log")
        info_handler.setFormatter(log_format)
        info_handler.setLevel(logging.DEBUG)
        logger.addHandler(info_handler)

        return logger

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
        self.logger.debug("Spawning emulator client process...")
        pid = subprocess.Popen([
                self.EMU_PATH,
                f'--chromeless',
                f'--socket_port={self.PORT}',
                f'--socket_ip={self.HOST}',
                f'--lua={os.path.abspath(self.EVAL_SCRIPT)}'
            ],
            preexec_fn=os.setsid,
        ).pid
        self.client_pids.append(pid)
        return pid

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
        self.logger.debug("Closing server...")
        try:
            for pid in self.client_pids:
                self.kill_client(pid)
            s.shutdown(socket.SHUT_RDWR)
            s.close()
        except Exception:
            # self.logger.error("close_server() failed.")
            return


class ConnectionClosedException(Exception):
    def __init__(self, message="Client connection closed before finishing evaluation."):
        self.message = message
        super().__init__(self.message)
