import os
import sys
from nim import train, play, load_game, SAVE_PATH

data = None

# Step 3: Check for an existing save at start and offer to load it
if os.path.exists(SAVE_PATH):
    choice = input("Saved game found. Load it? (y/n): ").strip().lower()
    if choice == "y":
        data = load_game()

# If a save was loaded, skip setup and training entirely
if data:
    play(data["ai"], human_player=data["human_player"], game=data["game"])
    sys.exit(0)

# Step 1a: Ask for number of piles (must be >= 3)
while True:
    try:
        num_piles = int(input("How many piles? (minimum 3): "))
        if num_piles >= 3:
            break
        print("Please enter a number of at least 3.")
    except ValueError:
        print("Invalid input. Please enter a whole number.")

# Step 1b: Ask for size of each pile (must be >= 1)
initial = []
for i in range(num_piles):
    while True:
        try:
            size = int(input(f"How many objects in pile {i}? (minimum 1): "))
            if size >= 1:
                initial.append(size)
                break
            print("Please enter a size of at least 1.")
        except ValueError:
            print("Invalid input. Please enter a whole number.")

# Step 1c: Sort piles ascending and echo back to user
initial.sort()
print(f"\nYour piles (sorted): {initial}")

ai = train(10000, initial)
play(ai, initial=initial)
