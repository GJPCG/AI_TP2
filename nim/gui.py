"""
Tkinter interface for playing Nim against the Q-learning AI.

Run from this folder with:
    python gui.py
"""

import contextlib
import io
import random
import threading
import tkinter as tk
from tkinter import ttk

from nim import Nim, train

TRAINING_GAMES = 10000
AI_THINK_MS = 600   # pause before the AI reveals its move
AI_REVEAL_MS = 800  # how long the AI's chosen objects stay highlighted

# Colours
BG = "#1a1b26"
PANEL = "#24283b"
TEXT = "#c0caf5"
MUTED = "#737aa2"
OBJECT = "#7aa2f7"
OBJECT_EDGE = "#a9c1ff"
GHOST = "#3b4261"
HOVER = "#e0af68"
AI_PICK = "#bb9af7"
GOOD = "#9ece6a"
BAD = "#f7768e"

# Board geometry, in pixels
FONT = "Segoe UI"
RADIUS = 18
SPACING = 54
ROW_HEIGHT = 74
MARGIN = 36
LABEL_WIDTH = 70

TOGGLE = dict(
    bg=PANEL, fg=TEXT, selectcolor=BG, activebackground=PANEL,
    activeforeground=TEXT, font=(FONT, 10), highlightthickness=0
)


class TrainingProgress(io.TextIOBase):
    """
    Stand-in for stdout that counts the
    "Playing training game N" lines printed by `train`.
    """

    def __init__(self):
        self.games = 0

    def write(self, text):
        self.games += text.count("Playing training game")
        return len(text)


class NimApp():

    def __init__(self, root):
        self.root = root
        self.ai = None
        self.game = None
        self.initial = Nim().piles
        self.human_player = 0
        self.hover = None    # (pile, index) of the object under the cursor
        self.ai_pick = None  # action the AI is about to make
        self.pending = None  # id of a scheduled AI step
        self.score = {"human": 0, "ai": 0}

        root.title("Nim")
        root.configure(bg=BG)
        root.resizable(False, False)

        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure(
            "Nim.Horizontal.TProgressbar", troughcolor=PANEL,
            background=OBJECT, bordercolor=PANEL,
            lightcolor=OBJECT, darkcolor=OBJECT
        )

        self.show_training()

    def show_training(self):
        """
        Train the AI in a background thread while showing a progress bar.
        """
        self.training_frame = tk.Frame(self.root, bg=BG, padx=70, pady=50)
        self.training_frame.pack()
        tk.Label(
            self.training_frame, text="NIM", font=(FONT, 36, "bold"),
            fg=TEXT, bg=BG
        ).pack()
        tk.Label(
            self.training_frame,
            text=f"Training the AI on {TRAINING_GAMES:,} games of self-play…",
            font=(FONT, 11), fg=MUTED, bg=BG
        ).pack(pady=(4, 20))
        self.progress = ttk.Progressbar(
            self.training_frame, length=340, maximum=TRAINING_GAMES,
            style="Nim.Horizontal.TProgressbar"
        )
        self.progress.pack()

        self.counter = TrainingProgress()
        threading.Thread(target=self.run_training, daemon=True).start()
        self.poll_training()

    def run_training(self):
        with contextlib.redirect_stdout(self.counter):
            self.ai = train(TRAINING_GAMES)

    def poll_training(self):
        self.progress["value"] = self.counter.games
        if self.ai is None:
            self.root.after(50, self.poll_training)
            return
        self.training_frame.destroy()
        self.build_board()
        self.new_game()

    def build_board(self):
        """
        Create the header, pile canvas, side panel and status bar.
        """
        header = tk.Frame(self.root, bg=BG, padx=24, pady=16)
        header.pack(fill="x")
        tk.Label(
            header, text="NIM", font=(FONT, 26, "bold"), fg=TEXT, bg=BG
        ).pack(side="left")
        tk.Label(
            header,
            text="Take any number of objects from one pile.\n"
                 "Whoever takes the last object loses.",
            font=(FONT, 10), fg=MUTED, bg=BG, justify="left"
        ).pack(side="left", padx=18)
        self.score_label = tk.Label(
            header, font=(FONT, 16, "bold"), fg=TEXT, bg=BG
        )
        self.score_label.pack(side="right")

        body = tk.Frame(self.root, bg=BG, padx=24)
        body.pack(fill="x")

        self.canvas = tk.Canvas(
            body, bg=PANEL, highlightthickness=0,
            width=2 * MARGIN + LABEL_WIDTH + max(self.initial) * SPACING,
            height=2 * MARGIN + len(self.initial) * ROW_HEIGHT
        )
        self.canvas.pack(side="left", fill="y")
        self.canvas.bind("<Motion>", self.on_motion)
        self.canvas.bind("<Leave>", self.on_leave)
        self.canvas.bind("<Button-1>", self.on_click)

        panel = tk.Frame(body, bg=PANEL, padx=18, pady=8)
        panel.pack(side="left", fill="y", padx=(16, 0))

        self.section(panel, "Who moves first")
        self.first_var = tk.StringVar(value="random")
        for label, value in [("You", "human"), ("AI", "ai"), ("Random", "random")]:
            tk.Radiobutton(
                panel, text=label, value=value, variable=self.first_var,
                **TOGGLE
            ).pack(anchor="w")

        self.section(panel, "Options")
        self.hints_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            panel, text="Show AI hints", variable=self.hints_var,
            command=self.refresh, **TOGGLE
        ).pack(anchor="w")

        tk.Button(
            panel, text="New game", command=self.new_game,
            font=(FONT, 11, "bold"), bg=OBJECT, fg=BG,
            activebackground=OBJECT_EDGE, activeforeground=BG,
            relief="flat", cursor="hand2", pady=4
        ).pack(fill="x", pady=(16, 0))

        self.section(panel, "Moves")
        self.log = tk.Listbox(
            panel, height=7, width=24, bg=BG, fg=TEXT, font=(FONT, 10),
            borderwidth=0, highlightthickness=0, activestyle="none",
            selectbackground=GHOST
        )
        self.log.pack(fill="both", expand=True, pady=(0, 10))

        self.status_label = tk.Label(
            self.root, font=(FONT, 12), bg=BG, pady=14
        )
        self.status_label.pack(fill="x")

        # The canvas stretches to the side panel's height; centre the piles in it
        self.root.update_idletasks()
        self.top = (self.canvas.winfo_height() - len(self.initial) * ROW_HEIGHT) / 2

    def section(self, parent, title):
        tk.Label(
            parent, text=title.upper(), font=(FONT, 9, "bold"),
            fg=MUTED, bg=PANEL
        ).pack(anchor="w", pady=(12, 4))

    def new_game(self):
        if self.pending is not None:
            self.root.after_cancel(self.pending)
            self.pending = None

        first = self.first_var.get()
        if first == "random":
            first = random.choice(["human", "ai"])

        self.game = Nim()
        self.human_player = 0 if first == "human" else 1
        self.hover = None
        self.ai_pick = None
        self.log.delete(0, "end")
        self.log.insert("end", "You move first" if first == "human" else "AI moves first")
        self.log.itemconfig("end", fg=MUTED)
        self.advance()

    def play(self, action, who):
        """
        Apply `action` to the game, log it, and hand over to the next player.
        """
        pile, count = action
        self.game.move(action)
        self.log.insert("end", f"{who} took {count} from pile {pile}")
        self.log.itemconfig("end", fg=HOVER if who == "You" else AI_PICK)
        self.log.see("end")

        if self.game.winner is not None:
            winner = "human" if self.game.winner == self.human_player else "ai"
            self.score[winner] += 1
        self.advance()

    def advance(self):
        """
        Redraw, and schedule the AI's move if it is the AI's turn.
        """
        self.refresh()
        if self.game.winner is None and self.game.player != self.human_player:
            self.pending = self.root.after(AI_THINK_MS, self.ai_choose)

    def ai_choose(self):
        self.ai_pick = self.ai.choose_action(self.game.piles, epsilon=False)
        self.refresh()
        self.pending = self.root.after(AI_REVEAL_MS, self.ai_move)

    def ai_move(self):
        action, self.ai_pick = self.ai_pick, None
        self.pending = None
        self.play(action, "AI")

    def humans_turn(self):
        return self.game.winner is None and self.game.player == self.human_player

    def on_motion(self, event):
        hover = self.object_at(event.x, event.y) if self.humans_turn() else None
        if hover != self.hover:
            self.hover = hover
            self.refresh()

    def on_leave(self, event):
        if self.hover is not None:
            self.hover = None
            self.refresh()

    def on_click(self, event):
        if not self.humans_turn():
            return
        target = self.object_at(event.x, event.y)
        if target is None:
            return
        pile, index = target
        self.hover = None
        self.play((pile, self.game.piles[pile] - index), "You")

    def position(self, pile, index):
        """
        Canvas coordinates of the centre of object `index` in pile `pile`.
        Each pile is centred so the board forms a pyramid.
        """
        area = max(self.initial) * SPACING
        left = MARGIN + LABEL_WIDTH + (area - self.initial[pile] * SPACING) / 2
        x = left + index * SPACING + SPACING / 2
        y = self.top + pile * ROW_HEIGHT + ROW_HEIGHT / 2
        return x, y

    def object_at(self, x, y):
        """
        Return `(pile, index)` of the remaining object under `(x, y)`, or None.
        """
        for pile, size in enumerate(self.game.piles):
            for index in range(size):
                cx, cy = self.position(pile, index)
                if (x - cx) ** 2 + (y - cy) ** 2 <= (RADIUS + 4) ** 2:
                    return pile, index
        return None

    def hover_action(self):
        """
        The action the human makes by clicking the hovered object:
        take it and every object to its right.
        """
        pile, index = self.hover
        return pile, self.game.piles[pile] - index

    def hint(self):
        """
        The AI's Q-value for the hovered move, or None if hints are off.
        """
        if self.hover is None or not self.hints_var.get():
            return None
        return self.ai.get_q_value(self.game.piles, self.hover_action())

    def highlight(self):
        """
        Return the objects to highlight and their colour: either the
        AI's pending move or the move the human is hovering over.
        """
        if self.ai_pick is not None:
            action, color = self.ai_pick, AI_PICK
        elif self.hover is not None:
            q = self.hint()
            action = self.hover_action()
            color = HOVER if not q else GOOD if q > 0 else BAD
        else:
            return set(), None

        pile, count = action
        size = self.game.piles[pile]
        return {(pile, k) for k in range(size - count, size)}, color

    def status(self):
        """
        Return the status bar text and colour for the current state.
        """
        if self.game.winner is not None:
            if self.game.winner == self.human_player:
                return "You win! The AI took the last object.", GOOD
            return "The AI wins: you took the last object. Press New game for a rematch.", BAD
        if self.ai_pick is not None:
            pile, count = self.ai_pick
            return f"AI takes {count} from pile {pile}.", AI_PICK
        if self.game.player != self.human_player:
            return "AI is thinking…", MUTED
        if self.hover is None:
            return "Your turn: click an object to take it and everything to its right.", TEXT

        pile, count = self.hover_action()
        text = f"Take {count} from pile {pile}"
        q = self.hint()
        if q is not None:
            text += f"   ·   AI rates this move {q:+.2f}"
        return text, TEXT

    def refresh(self):
        self.draw()
        text, color = self.status()
        self.status_label.config(text=text, fg=color)
        self.score_label.config(
            text=f"You {self.score['human']}  –  {self.score['ai']} AI"
        )
        self.canvas.config(cursor="hand2" if self.hover else "")

    def draw(self):
        self.canvas.delete("all")
        selected, color = self.highlight()

        for pile, size in enumerate(self.initial):
            _, y = self.position(pile, 0)
            self.canvas.create_text(
                MARGIN, y, text=f"Pile {pile}", anchor="w",
                fill=MUTED, font=(FONT, 11)
            )
            for index in range(size):
                x, y = self.position(pile, index)
                if index >= self.game.piles[pile]:
                    self.circle(x, y, RADIUS, fill=PANEL, outline=GHOST)
                elif (pile, index) in selected:
                    self.circle(x, y, RADIUS + 5, fill="", outline=color)
                    self.circle(x, y, RADIUS, fill=color, outline=color)
                else:
                    self.circle(x, y, RADIUS, fill=OBJECT, outline=OBJECT_EDGE)

    def circle(self, x, y, r, **options):
        self.canvas.create_oval(x - r, y - r, x + r, y + r, width=2, **options)


if __name__ == "__main__":
    root = tk.Tk()
    NimApp(root)
    root.mainloop()
