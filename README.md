# Pokémon Battle Factory AI: Neuroevolution with NEAT

This repository contains my personal project to train an AI to play the Pokémon Platinum Battle Factory minigame using the NEAT (NeuroEvolution of Augmenting Topologies) algorithm. The AI interfaces with the BizHawk-2.9.1 emulator via Lua scripts, reading game states from memory (e.g., Pokémon stats, moves, HP) and making decisions for battles and trades. It processes serialized game states and evolves neural networks to select moves, switch Pokémon, and trade team members. Trained over 154 generations with a population of 250 genomes, the AI achieved a best fitness of 1894.0 (equivalent to multiple battles won), demonstrating robust performance in a stochastic, turn-based environment.

## Table of Contents
- [Pokémon Battle Factory AI: Neuroevolution with NEAT](#pokémon-battle-factory-ai-neuroevolution-with-neat)
  - [Project Overview](#project-overview)
  - [Approach](#approach)
  - [Tools and Technologies](#tools-and-technologies)
  - [Results](#results)
  - [Skills Demonstrated](#skills-demonstrated)
  - [Setup and Usage](#setup-and-usage)
  - [References](#references)

## Project Overview
The Battle Factory in Pokémon Platinum is a challenging minigame where players rent a team of three Pokémon, battle opponents, and trade Pokémon after each battle to improve their team. This project uses NEAT to evolve neural networks that autonomously play the Battle Factory by:
- Reading game states (e.g., Pokémon HP, moves, stats) from emulator memory.
- Making battle decisions (move selection, Pokémon switching).
- Strategically trading Pokémon to optimize the team.
- Handling dynamic game states, including encrypted memory blocks and turn-based mechanics.

The AI was trained on a population of 250 genomes for 154 generations, with fitness based on enemy knockouts, battles won, and rounds completed.

## Approach
The project is structured as a client-server system:
- **Python Server (`main.py`, `eval_server.py`)**: Runs the NEAT algorithm, manages a population of genomes, and evaluates their fitness. It communicates with the BizHawk emulator via TCP sockets, processing game states and sending decisions. The server spawns 10 concurrent emulator clients for parallel evaluation, optimizing training time.
- **Lua Client (`eval_battlefactory.lua`)**: Interfaces with the BizHawk emulator, reading game memory (e.g., Pokémon data, battle states) and sending serialized states to the server. It executes AI decisions (e.g., move selection, trades) by simulating touchscreen inputs.
- **State Encoding (`encoder.py`)**: Converts complex game states (e.g., Pokémon stats, moves, status effects) into numerical vectors for neural network input, handling categorical (e.g., Pokémon IDs) and numerical (e.g., HP) features.
- **NEAT Configuration (`neat_battlefactory.cfg`)**: Defines the neural network architecture (317 inputs, 10 outputs) and evolution parameters (e.g., mutation rates, population size).

The AI processes game states in three modes:
1. **Initial Team Selection**: Chooses the starting team of three Pokémon.
2. **Battle Mode**: Selects moves or switches Pokémon based on the current battle state.
3. **Trade Mode**: Trades team members to improve the roster after each battle.

Fitness is calculated as:  
`fitness = (enemy_deaths²) + (battles_won × 2.5) + (rounds_won × 5.0)`, rewarding knockouts and progression.

## Tools and Technologies
- **Python**: NEAT-Python, NumPy, SciPy, scikit-image for neural network training, state encoding, and image processing.
- **Lua**: Scripts for emulator interfacing, memory reading, and input simulation.
- **BizHawk-2.9.1**: Emulator for running Pokémon Platinum and executing Lua scripts.
- **Socket Programming**: TCP sockets for client-server communication between Python and Lua.
- **Memory Manipulation**: Reading and decrypting Pokémon data from emulator memory.
- **Logging**: Custom logging for debugging and tracking training progress.
- **Multithreading**: Parallel evaluation of genomes using 10 emulator clients.

## Results
- **Best Fitness**: 1894.0 (Generation 154, Genome ID 3739), equivalent to multiple battles won and significant enemy knockouts.
- **Population**: 250 genomes across 4 species, with an average fitness of 116.20 (stdev: 314.44).
- **Training Time**: ~5596 seconds per generation (average: 5533.54 seconds over 10 generations).
- **Performance**: The AI learned to select effective moves, switch Pokémon strategically, and make informed trades, handling the Battle Factory’s stochastic nature and encrypted memory.

## Skills Demonstrated
- **Machine Learning**: Implemented neuroevolution with NEAT to train AI in a complex game environment.
- **Game AI Development**: Designed an AI to handle turn-based strategy, state parsing, and decision-making.
- **Emulator Interfacing**: Used Lua to read and manipulate emulator memory, including decrypting Pokémon data.
- **Socket Programming**: Built a client-server architecture for real-time communication between Python and Lua.
- **State Encoding**: Engineered feature vectors for neural network input, handling categorical and numerical data.
- **Parallel Processing**: Optimized training with multithreaded emulator clients.
- **Debugging and Logging**: Developed robust logging for training and evaluation diagnostics.

## Setup and Usage
1. **Prerequisites**:
   - Clone the project repository: `git clone git@github.com:JavenZ/Pokemon-Battle-Factory-NEAT.git`
   - Install BizHawk-2.9.1 (see [BizHawk GitHub](https://github.com/TASEmulators/BizHawk)).
   - Install Python dependencies: `pip3 install -r requirements.txt`
   - Place Pokémon Platinum ROM in the emulator directory: `emu/Pokemon - Platinum Version (USA) (Rev 1).nds`
3. **Configuration**:
   - Update `neat_battlefactory.cfg` for NEAT parameters (e.g., population size, mutation rates).
   - Set `LOAD_SLOT` in `eval_battlefactory.lua` to the desired save slot.
4. **Running**:
   - `python main.py`
   - The script spawns 10 BizHawk instances, runs the NEAT algorithm, and logs results to `./logs/`.
5. **Checkpoints**:
   - Training checkpoints are saved in ./checkpoints/ and can be restored by setting restore_ckpt = True in main.py.

## References
- [NEAT Paper](https://nn.cs.utexas.edu/?stanley:ec02)
- [Battle Factory (Generation IV)](https://bulbapedia.bulbagarden.net/wiki/Battle_Factory_(Generation_IV))
- [BizHawk Emulator](https://github.com/TASEmulators/BizHawk)
- [NEAT-Python Documentation](https://neat-python.readthedocs.io/en/latest/)
