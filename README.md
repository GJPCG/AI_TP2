# Nim with a Q-learning AI

Play Nim against an AI that teaches itself the game. Before you play, the AI plays 10,000 games against itself and uses Q-learning to work out which moves win. You can play in the terminal or in a desktop window.

This project extends the Nim project from [CS50's Introduction to Artificial Intelligence with Python](https://cs50.harvard.edu/ai/) with custom piles, saving and loading, and a Tkinter interface.

## Rules

The game starts with several piles of objects. Players take turns. On your turn, you remove one or more objects from a single pile. Whoever takes the last object loses.

## Requirements

- Python 3
- Tkinter, for the desktop version only. It comes with the standard Python installers for Windows and macOS. On Debian or Ubuntu, install it with `sudo apt install python3-tk`.

No other packages are needed.

## Running the game

Run both versions from the repository root. Saved games go in a `saves/` folder inside whichever folder you launch from, so always launching from the same place keeps them together.

### Desktop version

```
python nim/gui.py
```

1. Choose the number of piles (3 to 8) and the number of objects in each (1 to 10). The piles are sorted from smallest to largest.
2. Click **Train AI and play**. A progress bar tracks the 10,000 training games.
3. On your turn, click an object to take it along with every object to its right in the same pile. Hovering over an object highlights what you would take.

The side panel has:

- **Who moves first**: you, the AI, or random. The choice applies from the next new game.
- **Show AI hints**: colours the move under your cursor green or red, depending on how the AI rates it, and shows the rating in the status bar.
- **Top moves window**: a separate window listing the AI's five highest-rated moves, each with a bar showing its Q-value. On the AI's turn, it highlights the move the AI is about to make. On your turn, it ranks your options if hints are on, and otherwise shows the AI's last decision.
- **New game**, **Change piles**, **Save** and **Load** buttons.
- A log of every move. The score for the session appears at the top of the window.

### Terminal version

```
python nim/play.py
```

1. If a saved game exists, you are asked whether to load it.
2. Otherwise, enter the number of piles (at least 3) and the number of objects in each (at least 1). The piles are sorted from smallest to largest.
3. The AI trains on 10,000 games, and then the game begins. Who moves first is chosen at random.
4. On your turn, enter a pile number and then how many objects to take. At the pile prompt, you can also type `s` to save or `l` to load.

## Saving and loading

A save stores the board, whose turn it is, which side you are playing, and the trained AI, in `saves/savegame.pkl`. Loading restores all of this, so you skip setup and training. There is one save slot, and each save replaces the last one. Both versions use the same file, so you can save a game in one version and continue it in the other. In the desktop version, **Save** is disabled once a game has ended.

Save files use Python's `pickle` format. Only load save files you made yourself, because a tampered file can run code on your computer.

## How the AI learns

The AI keeps a table of Q-values. For each position (the sizes of the piles) and each possible move, it stores an estimate of how good that move is for the player making it, from −1 (a losing move) to +1 (a winning move). Pairs it has never seen count as 0.

During training, the AI plays both sides. After each move, it updates the table using:

```
Q(s, a) ← Q(s, a) + α × (reward + max Q(s′, a′) − Q(s, a))
```

- The move that takes the last object gets a reward of −1, and the opponent's previous move gets +1. All other moves get 0.
- The learning rate α is 0.5.
- While training, the AI makes a random move 10% of the time (ε = 0.1) so that it explores new positions. The rest of the time, it makes the best move it knows. Against you, it always makes the best move it knows.

### Limitations

The AI only knows the positions it reached during training. On small boards, such as the default piles of 1, 3, 5 and 7, 10,000 games cover nearly every position, and the AI is hard to beat. Large boards have far more positions than that: 8 piles of 10 objects allow over 200 million. On those boards, the AI often has to choose between moves it has never seen, so it is much easier to beat. Training also takes longer as the piles grow.

## Project structure

```
nim/
  nim.py    game rules, the Q-learning AI, training, save/load and the terminal game loop
  play.py   terminal version: pile setup, then training and play
  gui.py    Tkinter desktop version
saves/      created on the first save; holds savegame.pkl
```

## Credits

The game class, the training loop and the original terminal game loop come from CS50's distribution code for the Nim project. This project implements the AI's Q-learning methods and adds custom piles, saving and loading, and the desktop interface.
