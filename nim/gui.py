"""
Tkinter interface for playing Nim against the Q-learning AI.

Run from this folder with:
    python gui.py
"""

import contextlib
import io
import os
import random
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from nim import Nim, SAVE_PATH, load_game, save_game, train

TRAINING_GAMES = 10000
AI_THINK_MS = 600   # pause before the AI reveals its move
AI_REVEAL_MS = 800  # how long the AI's chosen objects stay highlighted

# Limits for the setup screen
MIN_PILES, MAX_PILES = 3, 8
MIN_SIZE, MAX_SIZE = 1, 10

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

# Board geometry, in pixels; boards larger than the maximum are scaled down
FONT = "Segoe UI"
RADIUS = 18
SPACING = 54
ROW_HEIGHT = 74
MARGIN = 36
LABEL_WIDTH = 70
MIN_BOARD_WIDTH = 7 * SPACING
MAX_BOARD_WIDTH = 10 * SPACING
MAX_BOARD_HEIGHT = 6 * ROW_HEIGHT

# Top moves window
TOP_MOVES = 5
METER_WIDTH = 300
METER_ROW = 46
BAR_HEIGHT = 8

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


def read_int(var, low, high):
    """
    Return the whole number held in `var` if it lies
    between `low` and `high`, otherwise None.
    """
    try:
        value = int(var.get())
    except ValueError:
        return None
    return value if low <= value <= high else None


def describe(action):
    pile, count = action
    return f"take {count} from pile {pile}"


def top_moves(ai, state):
    """
    Return the `TOP_MOVES` best actions in `state` as `(action, q)` pairs,
    best first. Ties keep the order `choose_action` sees them in,
    so the first entry is the move the AI plays.
    """
    actions = list(Nim.available_actions(state))
    ranked = sorted(actions, key=lambda action: ai.get_q_value(state, action), reverse=True)
    return [(action, ai.get_q_value(state, action)) for action in ranked[:TOP_MOVES]]


class TopMovesWindow():
    """
    Small window in the top-left corner of the screen listing the
    AI's highest-valued moves, each with a bar showing its Q-value.
    """

    def __init__(self, root, on_close):
        self.window = tk.Toplevel(root, bg=BG, padx=18, pady=14)
        self.window.title("AI's top moves")
        self.window.resizable(False, False)
        self.window.transient(root)
        self.window.geometry("+0+0")
        self.window.protocol("WM_DELETE_WINDOW", on_close)

        tk.Label(
            self.window, text="AI'S TOP MOVES", font=(FONT, 9, "bold"),
            fg=MUTED, bg=BG
        ).pack(anchor="w")
        self.title = tk.Label(
            self.window, font=(FONT, 12, "bold"), fg=TEXT, bg=BG, anchor="w"
        )
        self.title.pack(fill="x")
        self.subtitle = tk.Label(
            self.window, font=(FONT, 10), fg=MUTED, bg=BG, anchor="w"
        )
        self.subtitle.pack(fill="x")
        self.canvas = tk.Canvas(
            self.window, width=METER_WIDTH, height=TOP_MOVES * METER_ROW + 24,
            bg=PANEL, highlightthickness=0
        )
        self.canvas.pack(pady=(10, 8))
        tk.Label(
            self.window,
            text="Q-value for the player to move:\n+1 = winning move, −1 = losing move",
            font=(FONT, 9), fg=MUTED, bg=BG, justify="left"
        ).pack(anchor="w")

    def show(self, title, subtitle, rows=(), mark=None, mark_color=None):
        """
        Display `rows` of `(action, q)` pairs, best first.
        The row for action `mark` is outlined in `mark_color`.
        """
        self.title.config(text=title)
        self.subtitle.config(text=subtitle)
        self.canvas.delete("all")
        if not rows:
            self.canvas.create_text(
                METER_WIDTH / 2, (TOP_MOVES * METER_ROW + 24) / 2,
                text="No moves to show", fill=MUTED, font=(FONT, 10)
            )
            return

        pad = 14
        zero = METER_WIDTH / 2
        half = zero - pad
        for rank, (action, q) in enumerate(rows):
            top = 6 + rank * METER_ROW
            if action == mark:
                self.canvas.create_rectangle(
                    4, top, METER_WIDTH - 4, top + METER_ROW - 4,
                    outline=mark_color, width=2
                )
            y = top + 13
            self.canvas.create_text(
                pad, y, text=rank + 1, anchor="w", fill=MUTED,
                font=(FONT, 10, "bold")
            )
            self.canvas.create_text(
                pad + 18, y, text=describe(action).capitalize(), anchor="w",
                fill=TEXT, font=(FONT, 10)
            )
            self.canvas.create_text(
                METER_WIDTH - pad, y, text=f"{q:+.2f}", anchor="e",
                fill=TEXT, font=(FONT, 10, "bold")
            )

            # Track for the -1..+1 range, a tick at zero, then the bar
            y = top + 31
            self.canvas.create_line(pad, y, METER_WIDTH - pad, y, fill=GHOST)
            self.canvas.create_line(zero, y - 7, zero, y + 7, fill=MUTED)
            self.bar(zero, zero + q * half, y, GOOD if q > 0 else BAD)

        bottom = 6 + TOP_MOVES * METER_ROW + 4
        for x, label in [(pad, "−1"), (zero, "0"), (METER_WIDTH - pad, "+1")]:
            self.canvas.create_text(x, bottom, text=label, fill=MUTED, font=(FONT, 8))

    def bar(self, x0, x1, y, color):
        """
        Horizontal bar from the baseline `x0` to `x1`, rounded at the `x1` end.
        """
        r = BAR_HEIGHT / 2
        if abs(x1 - x0) < BAR_HEIGHT:
            if x1 != x0:
                self.canvas.create_rectangle(
                    min(x0, x1), y - r, max(x0, x1), y + r, fill=color, outline=""
                )
            return
        inner = x1 - r if x1 > x0 else x1 + r
        self.canvas.create_rectangle(
            min(x0, inner), y - r, max(x0, inner), y + r, fill=color, outline=""
        )
        self.canvas.create_oval(inner - r, y - r, inner + r, y + r, fill=color, outline="")


class NimApp():

    def __init__(self, root):
        self.root = root
        self.screen = None
        self.ai = None
        self.game = None
        self.initial = Nim().piles
        self.human_player = 0
        self.hover = None    # (pile, index) of the object under the cursor
        self.ai_pick = None  # action the AI is about to make
        self.pending = None  # id of a scheduled AI step
        self.score = {"human": 0, "ai": 0}
        self.last_decision = None  # (state, action) of the AI's latest move
        self.top_moves = None
        self.first_var = tk.StringVar(value="random")
        self.hints_var = tk.BooleanVar(value=False)
        self.top_moves_var = tk.BooleanVar(value=True)
        self.digits_only = root.register(
            lambda text: text == "" or (text.isdigit() and len(text) <= 2)
        )

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

        # Top moves window in the top-left corner, game window to its right
        self.toggle_top_moves()
        root.update_idletasks()
        root.geometry(f"+{self.top_moves.window.winfo_reqwidth() + 40}+0")

        self.show_setup()

    def new_screen(self, **padding):
        """
        Replace the window's contents with a new, empty frame and return it.
        """
        if self.screen is not None:
            self.screen.destroy()
        self.screen = tk.Frame(self.root, bg=BG, **padding)
        self.screen.pack()
        return self.screen

    def show_setup(self):
        """
        Let the player choose the number of piles and the size of each.
        """
        self.game = None
        self.update_top_moves()
        frame = self.new_screen(padx=70, pady=40)
        tk.Label(
            frame, text="NIM", font=(FONT, 36, "bold"), fg=TEXT, bg=BG
        ).pack()
        tk.Label(
            frame, text="Choose the piles. The AI trains on them before you play.",
            font=(FONT, 11), fg=MUTED, bg=BG
        ).pack(pady=(4, 20))

        form = tk.Frame(frame, bg=PANEL, padx=24, pady=16)
        form.pack(fill="x")
        form.columnconfigure(0, weight=1)
        self.sizes_frame = tk.Frame(form, bg=PANEL)
        self.sizes_frame.grid(row=2, column=0, columnspan=2, sticky="ew")
        self.sizes_frame.columnconfigure(0, weight=1)

        self.count_var = tk.StringVar(value=len(self.initial))
        self.size_vars = [tk.StringVar(value=size) for size in self.initial]
        self.count_var.trace_add("write", self.show_size_inputs)

        tk.Label(
            form, text="Number of piles", font=(FONT, 11, "bold"),
            fg=TEXT, bg=PANEL
        ).grid(row=0, column=0, sticky="w")
        self.spinbox(form, self.count_var, MIN_PILES, MAX_PILES).grid(row=0, column=1)
        tk.Label(
            form, text="OBJECTS PER PILE", font=(FONT, 9, "bold"),
            fg=MUTED, bg=PANEL
        ).grid(row=1, column=0, sticky="w", pady=(14, 4))
        self.show_size_inputs()

        tk.Label(
            frame, text="Piles are sorted from smallest to largest when the game starts.",
            font=(FONT, 10), fg=MUTED, bg=BG
        ).pack(pady=(12, 0))
        self.setup_error = tk.Label(frame, font=(FONT, 10), fg=BAD, bg=BG)
        self.setup_error.pack()
        self.button(frame, "Train AI and play", self.start).pack(fill="x", pady=(6, 0))
        if os.path.exists(SAVE_PATH):
            self.button(
                frame, "Load saved game", self.load, primary=False
            ).pack(fill="x", pady=(8, 0))

    def show_size_inputs(self, *args):
        """
        Show one size input per pile. Values already typed are kept
        if the number of piles goes down and back up again.
        """
        count = read_int(self.count_var, MIN_PILES, MAX_PILES)
        if count is None:
            return
        while len(self.size_vars) < count:
            default = min(2 * len(self.size_vars) + 1, MAX_SIZE)
            self.size_vars.append(tk.StringVar(value=default))

        for widget in self.sizes_frame.winfo_children():
            widget.destroy()
        for i, var in enumerate(self.size_vars[:count]):
            tk.Label(
                self.sizes_frame, text=f"Pile {i}", font=(FONT, 10),
                fg=TEXT, bg=PANEL
            ).grid(row=i, column=0, sticky="w")
            self.spinbox(self.sizes_frame, var, MIN_SIZE, MAX_SIZE).grid(row=i, column=1, pady=2)

    def start(self):
        """
        Check the setup form, then train a new AI on the chosen piles.
        """
        count = read_int(self.count_var, MIN_PILES, MAX_PILES)
        if count is None:
            self.setup_error.config(text=f"Choose between {MIN_PILES} and {MAX_PILES} piles.")
            return
        sizes = [read_int(var, MIN_SIZE, MAX_SIZE) for var in self.size_vars[:count]]
        if None in sizes:
            self.setup_error.config(
                text=f"Each pile needs between {MIN_SIZE} and {MAX_SIZE} objects."
            )
            return

        self.initial = sorted(sizes)
        self.score = {"human": 0, "ai": 0}
        self.show_training()

    def show_training(self):
        """
        Train the AI in a background thread while showing a progress bar.
        """
        frame = self.new_screen(padx=70, pady=50)
        tk.Label(
            frame, text="NIM", font=(FONT, 36, "bold"), fg=TEXT, bg=BG
        ).pack()
        tk.Label(
            frame,
            text=f"Training the AI on {TRAINING_GAMES:,} games of self-play…\n"
                 f"Piles: {', '.join(map(str, self.initial))}",
            font=(FONT, 11), fg=MUTED, bg=BG
        ).pack(pady=(4, 20))
        self.progress = ttk.Progressbar(
            frame, length=340, maximum=TRAINING_GAMES,
            style="Nim.Horizontal.TProgressbar"
        )
        self.progress.pack()

        self.ai = None
        self.counter = TrainingProgress()
        threading.Thread(target=self.run_training, daemon=True).start()
        self.poll_training()

    def run_training(self):
        with contextlib.redirect_stdout(self.counter):
            self.ai = train(TRAINING_GAMES, self.initial)

    def poll_training(self):
        self.progress["value"] = self.counter.games
        if self.ai is None:
            self.root.after(50, self.poll_training)
            return
        self.build_board()
        self.new_game()

    def build_board(self):
        """
        Create the header, pile canvas, side panel and status bar.
        """
        frame = self.new_screen()
        header = tk.Frame(frame, bg=BG, padx=24, pady=16)
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

        body = tk.Frame(frame, bg=BG, padx=24)
        body.pack(fill="x")

        scale = min(
            1,
            MAX_BOARD_WIDTH / (max(self.initial) * SPACING),
            MAX_BOARD_HEIGHT / (len(self.initial) * ROW_HEIGHT)
        )
        self.spacing = SPACING * scale
        self.row_height = ROW_HEIGHT * scale
        self.radius = RADIUS * scale
        self.area = max(max(self.initial) * self.spacing, MIN_BOARD_WIDTH)

        self.canvas = tk.Canvas(
            body, bg=PANEL, highlightthickness=0,
            width=2 * MARGIN + LABEL_WIDTH + self.area,
            height=2 * MARGIN + len(self.initial) * self.row_height
        )
        self.canvas.pack(side="left", fill="y")
        self.canvas.bind("<Motion>", self.on_motion)
        self.canvas.bind("<Leave>", self.on_leave)
        self.canvas.bind("<Button-1>", self.on_click)

        panel = tk.Frame(body, bg=PANEL, padx=18, pady=8)
        panel.pack(side="left", fill="y", padx=(16, 0))

        self.section(panel, "Who moves first")
        for label, value in [("You", "human"), ("AI", "ai"), ("Random", "random")]:
            tk.Radiobutton(
                panel, text=label, value=value, variable=self.first_var,
                **TOGGLE
            ).pack(anchor="w")

        self.section(panel, "Options")
        tk.Checkbutton(
            panel, text="Show AI hints", variable=self.hints_var,
            command=self.refresh, **TOGGLE
        ).pack(anchor="w")
        tk.Checkbutton(
            panel, text="Top moves window", variable=self.top_moves_var,
            command=self.toggle_top_moves, **TOGGLE
        ).pack(anchor="w")

        self.button(panel, "New game", self.new_game).pack(fill="x", pady=(16, 0))
        self.button(
            panel, "Change piles", self.change_piles, primary=False
        ).pack(fill="x", pady=(8, 0))

        files = tk.Frame(panel, bg=PANEL)
        files.pack(fill="x", pady=(8, 0))
        files.columnconfigure((0, 1), weight=1, uniform="files")
        self.save_button = self.button(files, "Save", self.save, primary=False)
        self.save_button.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.load_button = self.button(files, "Load", self.load, primary=False)
        self.load_button.grid(row=0, column=1, sticky="ew", padx=(4, 0))

        self.section(panel, "Moves")
        self.log = tk.Listbox(
            panel, height=7, width=24, bg=BG, fg=TEXT, font=(FONT, 10),
            borderwidth=0, highlightthickness=0, activestyle="none",
            selectbackground=GHOST
        )
        self.log.pack(fill="both", expand=True, pady=(0, 10))

        self.status_label = tk.Label(frame, font=(FONT, 12), bg=BG, pady=14)
        self.status_label.pack(fill="x")

        # The canvas stretches to the side panel's height; centre the piles in it
        self.root.update_idletasks()
        self.top = (self.canvas.winfo_height() - len(self.initial) * self.row_height) / 2

    def section(self, parent, title):
        tk.Label(
            parent, text=title.upper(), font=(FONT, 9, "bold"),
            fg=MUTED, bg=PANEL
        ).pack(anchor="w", pady=(12, 4))

    def button(self, parent, text, command, primary=True):
        return tk.Button(
            parent, text=text, command=command, font=(FONT, 11, "bold"),
            bg=OBJECT if primary else GHOST, fg=BG if primary else TEXT,
            activebackground=OBJECT_EDGE if primary else MUTED,
            activeforeground=BG if primary else TEXT,
            disabledforeground=MUTED, relief="flat", cursor="hand2", pady=4
        )

    def spinbox(self, parent, var, low, high):
        return tk.Spinbox(
            parent, textvariable=var, from_=low, to=high, width=4,
            font=(FONT, 11), justify="center", bg=BG, fg=TEXT,
            buttonbackground=GHOST, insertbackground=TEXT, relief="flat",
            highlightthickness=1, highlightbackground=GHOST,
            highlightcolor=OBJECT, validate="key",
            validatecommand=(self.digits_only, "%P")
        )

    def cancel_pending(self):
        if self.pending is not None:
            self.root.after_cancel(self.pending)
            self.pending = None

    def change_piles(self):
        self.cancel_pending()
        self.show_setup()

    def save(self):
        """
        Save the current game, the AI and the player order to the save file.
        """
        try:
            save_game(self.game, self.ai, self.human_player)
        except OSError as error:
            messagebox.showerror("Save failed", f"Couldn't save the game:\n{error}", parent=self.root)
            return
        self.add_log("Game saved", MUTED)
        self.refresh()

    def load(self):
        """
        Restore the game, the AI and the player order from the save file,
        skipping setup and training.
        """
        try:
            data = load_game()
        except Exception as error:  # unreadable or incompatible save file
            messagebox.showerror("Load failed", f"Couldn't load the saved game:\n{error}", parent=self.root)
            return
        if data is None:
            messagebox.showerror("Load failed", "No saved game found.", parent=self.root)
            return

        self.cancel_pending()
        self.ai = data["ai"]
        self.game = data["game"]
        self.human_player = data["human_player"]
        # Saves made before Nim kept its starting piles only have the current ones
        self.initial = getattr(self.game, "initial", self.game.piles.copy())
        self.hover = None
        self.ai_pick = None
        self.last_decision = None
        self.build_board()
        self.add_log("Game loaded", MUTED)
        self.advance()

    def new_game(self):
        self.cancel_pending()

        first = self.first_var.get()
        if first == "random":
            first = random.choice(["human", "ai"])

        self.game = Nim(self.initial)
        self.human_player = 0 if first == "human" else 1
        self.hover = None
        self.ai_pick = None
        self.last_decision = None
        self.log.delete(0, "end")
        self.add_log("You move first" if first == "human" else "AI moves first", MUTED)
        self.advance()

    def add_log(self, text, color):
        self.log.insert("end", text)
        self.log.itemconfig("end", fg=color)
        self.log.see("end")

    def play(self, action, who):
        """
        Apply `action` to the game, log it, and hand over to the next player.
        """
        pile, count = action
        self.game.move(action)
        self.add_log(f"{who} took {count} from pile {pile}", HOVER if who == "You" else AI_PICK)

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
        self.last_decision = (self.game.piles.copy(), self.ai_pick)
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
        left = MARGIN + LABEL_WIDTH + (self.area - self.initial[pile] * self.spacing) / 2
        x = left + index * self.spacing + self.spacing / 2
        y = self.top + pile * self.row_height + self.row_height / 2
        return x, y

    def object_at(self, x, y):
        """
        Return `(pile, index)` of the remaining object under `(x, y)`, or None.
        """
        for pile, size in enumerate(self.game.piles):
            for index in range(size):
                cx, cy = self.position(pile, index)
                if (x - cx) ** 2 + (y - cy) ** 2 <= (self.radius + 4) ** 2:
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
        self.save_button.config(state="normal" if self.game.winner is None else "disabled")
        self.load_button.config(state="normal" if os.path.exists(SAVE_PATH) else "disabled")
        self.update_top_moves()

    def toggle_top_moves(self):
        if self.top_moves_var.get():
            self.top_moves = TopMovesWindow(self.root, on_close=self.close_top_moves)
            self.update_top_moves()
        else:
            self.close_top_moves()

    def close_top_moves(self):
        self.top_moves_var.set(False)
        if self.top_moves is not None:
            self.top_moves.window.destroy()
            self.top_moves = None

    def update_top_moves(self):
        """
        Rank the moves in whichever position is most useful right now:
        the AI's turn, the player's turn when hints are on, and
        otherwise the position where the AI last moved.
        """
        if self.top_moves is None:
            return
        if self.game is None:
            self.top_moves.show("No game yet", "Start a game to see what the AI is thinking.")
            return

        over = self.game.winner is not None
        if not over and self.game.player != self.human_player:
            state, mark, color = self.game.piles, self.ai_pick, AI_PICK
            title = "AI is choosing…" if mark is None else f"AI picks: {describe(mark)}"
        elif not over and self.hints_var.get():
            state, color = self.game.piles, HOVER
            mark = self.hover_action() if self.hover else None
            title = "Your options (hints are on)"
        elif self.last_decision is not None:
            state, mark = self.last_decision
            color = AI_PICK
            title = f"AI's last move: {describe(mark)}"
        else:
            self.top_moves.show(
                "Waiting for the AI's turn", "Turn on AI hints to rank your own moves."
            )
            return

        self.top_moves.show(
            title, f"Piles: {', '.join(map(str, state))}",
            top_moves(self.ai, state), mark, color
        )

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
                    self.circle(x, y, self.radius, fill=PANEL, outline=GHOST)
                elif (pile, index) in selected:
                    self.circle(x, y, self.radius + 5, fill="", outline=color)
                    self.circle(x, y, self.radius, fill=color, outline=color)
                else:
                    self.circle(x, y, self.radius, fill=OBJECT, outline=OBJECT_EDGE)

    def circle(self, x, y, r, **options):
        self.canvas.create_oval(x - r, y - r, x + r, y + r, width=2, **options)


if __name__ == "__main__":
    root = tk.Tk()
    NimApp(root)
    root.mainloop()
