import os
import neat
from eval_server import EvaluationServer
import logging
import reporter


class Trainer:
    def __init__(self, config, eval_server: EvaluationServer):
        """
        Runs the NEAT algorithm and orchestrates the evaluation process.
        """
        self.eval_server = eval_server
        self.config = config
        self.t = 100  # number of generations
        self.restore_ckpt = True  # restore from the last checkpoint?
        self.ckpt_prefix = "./checkpoints/neat-ckpt-"
        self.p = None  # population instance
        self.logger = self._init_logger()  # trainer logger

    def run(self):
        # Create or restore the population, which is the top-level object for a NEAT run.
        if self.restore_ckpt:
            last_ckpt = self.get_last_ckpt()
            if last_ckpt >= 0:
                self.logger.debug(f"Restoring population from checkpoint {last_ckpt}...")
                self.p = neat.Checkpointer.restore_checkpoint(f'{self.ckpt_prefix}{last_ckpt}')
                self.p.generation += 1
        if not self.p:
            self.logger.debug("Creating initial population...")
            self.p = neat.Population(self.config)

        # init checkpointer
        checkpointer = neat.Checkpointer(
            generation_interval=1,
            filename_prefix=self.ckpt_prefix
        )

        # Add a stdout reporter to show progress in the terminal.
        self.p.add_reporter(reporter.ResultsReporter(self.logger))
        stats = neat.StatisticsReporter()
        self.p.add_reporter(stats)
        self.p.add_reporter(checkpointer)
        self.logger.debug(f"Init generation #: {self.p.generation}")
        self.logger.debug(f"Init population size #: {len(self.p.population)}")

        # Run for up to 300 generations.
        self.logger.debug("Starting run...\n")
        winner = self.p.run(self._eval, self.t)

        # Display the winning genome.
        # print('\nBest genome:\n{!s}'.format(winner))

        # Show output of the most fit genome against training data.
        # print('\nOutput:')
        # winner_net = neat.nn.FeedForwardNetwork.create(winner, self.config)
        # for xi, xo in zip(xor_inputs, xor_outputs):
        #     output = winner_net.activate(xi)
        #     print("input {!r}, expected output {!r}, got {!r}".format(xi, xo, output))
        #
        # node_names = {-1: 'A', -2: 'B', 0: 'A XOR B'}
        # visualize.draw_net(config, winner, True, node_names=node_names)
        # visualize.draw_net(config, winner, True, node_names=node_names, prune_unused=True)
        # visualize.plot_stats(stats, ylog=False, view=True)
        # visualize.plot_species(stats, view=True)

        # p.run(self.eval_genomes, 10)

    def _eval(self, genomes, config):
        """
        Wrapper function for EvaluationServer evaluate_generation().
        """
        success = False
        while not success:
            success = self.eval_server.eval_genomes(genomes, config, self.p.generation)

    @classmethod
    def get_last_ckpt(cls) -> int:
        highest_idx = -1
        for f in os.listdir("./checkpoints/"):
            split = f.split("neat-ckpt-")
            if len(split) == 2:
                highest_idx = max(highest_idx, int(split[1]))
        return highest_idx

    @classmethod
    def _init_logger(cls):
        """
        Initializes the Trainer logger.
        Logs NEAT training results to logs/trainer.log and debug logs to console.
        """
        logger = logging.getLogger("trainer")
        logger.setLevel(logging.DEBUG)
        log_format = logging.Formatter('%(message)s')

        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(log_format)
        stream_handler.setLevel(logging.DEBUG)
        logger.addHandler(stream_handler)

        info_handler = logging.FileHandler('./logs/trainer.log')
        info_handler.setFormatter(log_format)
        info_handler.setLevel(logging.INFO)
        logger.addHandler(info_handler)
        return logger


if __name__ == "__main__":
    # TODO parse env vars
    game_mode = "battle_factory"

    # load configuration for game mode
    config_path = os.path.join(os.curdir, f'src/neat_{game_mode.replace("_","")}.cfg')
    _config = neat.Config(
        neat.DefaultGenome, neat.DefaultReproduction,
        neat.DefaultSpeciesSet, neat.DefaultStagnation,
        config_path
    )

    # init trainer & run
    _eval_server = EvaluationServer(game_mode=game_mode)
    trainer = Trainer(_config, _eval_server)
    trainer.run()
