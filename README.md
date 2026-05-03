# Injera — The Board Game

A hexagonal tile-eating board game inspired by Ethiopian cuisine, playable in your browser against a heuristic AI opponent.

📖 **New to the game? Read the [full game rules (PDF)](docs/injera_rules.pdf) before playing.**  
🃏 **Printable cards and tiles for the physical version are in the [`docs/`](docs/) folder.**

---

## Play Now (GitHub Codespaces)

No installation needed — GitHub gives every account free cloud compute you can use straight from this page.

**Step 1 — Open a Codespace**

Click the green **Code** button at the top of this repository, select the **Codespaces** tab, then click **Create codespace on main**.

> GitHub will spin up a cloud machine with all the files. This takes about 30–60 seconds.

**Step 2 — Install dependencies**

In the terminal that opens inside the Codespace, run:

```bash
pip install -r requirements.txt
```

**Step 3 — Configure players**

Run the interactive setup tool to choose how many players, their names, and which seats are controlled by the AI:

```bash
python setup_players.py
```

You will be asked:
- **Number of players** (2–6)
- **Name** for each player (or press Enter to accept the default)
- **Human or AI** for each seat — enter `y` to make a seat AI-controlled
- **Special cards** — optional secret objective cards; if enabled, each player is dealt 3 and keeps 2

The script updates `injera_game.html` in place. You can re-run it any time to reconfigure.

> **Example:** 1 human + 1 AI, no special cards:
> ```
> How many players? 2
> Player 1 — Name: Alice   Is AI? n
> Player 2 — Name:         Is AI? y
> Enable special cards? n
> ```

**Step 4 — Start the AI server**

```bash
python server.py
```

You should see:
```
🤖 INJERA AI SERVER STARTING
Server will run on: http://localhost:5000
```

Leave this terminal running.

**Step 5 — Open the game**

Once the server is running, Codespaces will show a pop-up saying **"Your application on port 5000 is available"** — click **Open in Browser**. If you miss it, go to the **Ports** tab (bottom panel), find port 5000, and click the globe icon.

The game loads directly from the server. You are ready to play.

> **Note:** The first time an AI takes its turn it may pause briefly while the server warms up.

---

## The Game

Injera is a board game for 2–6 players set on a hexagonal grid covered with Ethiopian dishes. Players move across the board eating dishes to score points, managing a hand of cards and drink tokens to handle hot food.

### Goal

Score the most points when all dishes are eaten or when no player can eat for a full round.

### The Board

The board is a hex grid with dish tiles arranged in concentric rings. Each tile shows a dish — some are hot 🔥, some extra-hot (Berbere 🔥🔥), and some tiles are empty. Your reachable tiles are highlighted in green.

### Dishes and Points

| Dish | Points | Hot? |
|---|---|---|
| Gomen (collard greens) | 1 | — |
| Azifa (lentil salad) | 1 | — |
| Shiro (chickpea stew) | 2 | — |
| Kik Alicha (split peas) | 2 | 🔥 |
| Misir Wot (red lentils) | 2 | 🔥 |
| Tikel Gomen (cabbage) | 2 | 🔥 |
| Key Sir (beetroot) | 3 | 🔥🔥 Berbere |

Eating 7 of the same dish earns a **+7 completion bonus**.  
Eating at least one of every dish type earns a **+4 variety bonus**.

### Your Hand

You hold a hand of cards (default size 4). Each time you eat a dish you must **discard one card** from your hand first. Card types:

- **Clean Injera** — used to pay for hotness (1 card = absorb 1 heat level), or as the resource tile when eating
- **Rotate** — rotate a ring of the board clockwise, repositioning dishes
- **Tahini** — place a tahini token on a tile, reducing its heat and adding +1 point when that tile is eaten
- **Beer / Coffee / Water** — drink cards that give you token-based heat protection for several turns

### Eating a Dish

To eat a dish you must:

1. Select a reachable tile with a dish
2. **Discard** one card from your hand
3. Provide a **resource** — either spend an Injera card or consume an adjacent empty tile
4. If the dish is hot, cover the remaining heat with **drink tokens** and/or **Injera cards**

### Hotness

Each hot dish has an effective heat level (base heat + awaze tokens − tahini tokens):

- **Regular hot (🔥):** heat level 1
- **Berbere / Key Sir (🔥🔥):** heat level 2

To eat it you need: `drink tokens + injera cards ≥ effective heat level`

Drink tokens refill every few turns; Injera cards are a limited shared resource.

### Drinks

Playing a Beer, Coffee, or Water card gives you a drink with several tokens. Each token can absorb one level of heat per turn. When a drink runs dry your turn ends immediately.

### Empty Tiles

Empty tiles can be consumed as a resource instead of an Injera card. They may carry **tahini** (reduces heat, scores bonus points) or be hot themselves, which adds to the heat you must handle.

### End of Game

The game ends when:
- All dish tiles are eaten, **or**
- A full round passes with nobody eating a single dish

Scores are totalled including variety bonus, completion bonus, and secret card bonuses.

---

## Secret Cards

At the start of the game each player is dealt 3 secret objective cards and keeps 2. These are hidden from opponents and scored at the end. Examples:

- **Picky Eater** — +15 pts if you ate exactly 3 dish types
- **Tasting Menu** — bonus for eating 5, 6, or 7 distinct dish types
- **Tahini Queen** — bonus for consuming more tahini than anyone else
- **Too Hot To Handle** — bonus for eating more hot tiles than anyone else
- **Consolation Prize** — bonus for eating fewer dishes than everyone else
- **Healthy Appetite** — bonus for eating more dishes than everyone else

The full list of 19 secret cards is in [`docs/special_cards.txt`](docs/special_cards.txt).

---

## Controls

| Action | How |
|---|---|
| Eat a dish | Click a green-outlined dish tile, then click **Eat Dish 🍴** |
| Play a card | Click a card in your hand panel |
| End your turn | Click **Next Turn ▶️** |
| Undo last action | Click **↩️ Undo** |
| New game | Click **🎮 New Game** |

---

## Developer Version

`injera_game_dev.html` is an unobfuscated version that shows AI players' full hand, secret cards, and action probabilities — useful for debugging and AI development.

---

## Local Setup (without Codespaces)

```bash
git clone https://github.com/OfirBlumer/injera.git
cd injera
pip install -r requirements.txt
python setup_players.py   # configure players and AI seats
python server.py          # keep this terminal running
# open injera_game.html in your browser
```
