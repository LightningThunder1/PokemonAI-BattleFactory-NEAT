import os
import neat
from eval_server import EvaluationServer


class Trainer:
    def __init__(self, config, eval_server: EvaluationServer):
        """
        Runs the NEAT algorithm and orchestrates the evaluation process.
        """
        self.eval_server = eval_server
        self.config = config

    def run(self):
        # Create the population, which is the top-level object for a NEAT run.
        print("Creating initial population...")
        p = neat.Population(self.config)

        # Add a stdout reporter to show progress in the terminal.
        p.add_reporter(neat.StdOutReporter(True))
        stats = neat.StatisticsReporter()
        p.add_reporter(stats)
        p.add_reporter(neat.Checkpointer(
            generation_interval=5,
            filename_prefix="./checkpoints/neat-ckpt-"
        ))

        # Run for up to 300 generations.
        print("Starting run...")
        winner = p.run(self.eval_server.eval_genomes, 100)

        # Display the winning genome.
        # print('\nBest genome:\n{!s}'.format(winner))

        # Show output of the most fit genome against training data.
        # print('\nOutput:')
        winner_net = neat.nn.FeedForwardNetwork.create(winner, self.config)
        # for xi, xo in zip(xor_inputs, xor_outputs):
        #     output = winner_net.activate(xi)
        #     print("input {!r}, expected output {!r}, got {!r}".format(xi, xo, output))
        #
        # node_names = {-1: 'A', -2: 'B', 0: 'A XOR B'}
        # visualize.draw_net(config, winner, True, node_names=node_names)
        # visualize.draw_net(config, winner, True, node_names=node_names, prune_unused=True)
        # visualize.plot_stats(stats, ylog=False, view=True)
        # visualize.plot_species(stats, view=True)

        # p = neat.Checkpointer.restore_checkpoint('neat-checkpoint-4')
        # p.run(self.eval_genomes, 10)


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
