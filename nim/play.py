import os
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
else:
    ai = train(10000)
    play(ai)
