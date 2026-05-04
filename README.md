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

## Gameplay

The board is a hex grid of dish tiles. Each player sits at a vertex and can reach the tiles in their sector (highlighted in green). On your turn you may take one or more actions, then click **Next Turn**.

### Actions

**Eat Dish**  
Select a reachable dish tile and click **Eat Dish**. You must:
1. Discard one card from your hand
2. Provide a resource — either spend a Clean Injera card, or consume an adjacent reachable empty tile
3. If the dish is hot, cover its heat level with drink tokens and/or Clean Injera cards (`tokens + injera cards ≥ heat level`)

Each dish tile scores points equal to its base value plus any tahini tokens on it (+1 per token). If you used an empty tile as resource, its tahini tokens score too.

| Dish | Points | Heat |
|---|---|---|
| Gomen, Azifa, Shiro | 1 | — |
| Kik Alicha, Misir Wot, Tikel Gomen | 2 | 🔥 (level 1) |
| Key Sir | 3 | 🔥🔥 Berbere (level 2) |

Heat level = base heat + awaze tokens on the tile − tahini tokens on the tile.

Eating 5/6/7 tiles of the same dish type earns a completion bonus (+5/+10/+15). Eating 5/6/7 distinct dish types earns a variety bonus (+5/+12/+21).

---

**Eat Empty Tile**  
Select a reachable empty tile and click **Eat Empty Tile**. No card is required. You score any tahini tokens on that tile. This does **not** count as eating a dish.

---

**Order Drink**  
Play a Beer, Coffee, or Water card from your hand to fill a cup with 3 tokens. The cup stays active across turns. When the last token is consumed:
- **Beer** — +6 pts, your next hand refill at end-of-turn draws one fewer card. Turn ends.
- **Coffee** — +3 pts, your hand refills to max+1 immediately. Turn ends.
- **Water** — hand refills to max immediately. Turn continues (if it runs dry a second time in the same turn, turn ends instead).

---

**Drink Token**  
Consume one token from one of your active cups. Tokens are mainly used during eating to absorb dish heat, but can also be consumed as a standalone action.

---

**Add Tahini**  
Play a Tahini card and select a tile as the apex of a triangle. Adds +1 tahini token to all 3 tiles in the chosen triangle. Tahini reduces a tile's heat level and scores +1 point per token when that tile is eventually eaten.

---

**Add Awaze**  
Play an Awaze card and select a tile as the apex of a triangle. Adds +1 awaze token to all 3 tiles, increasing each tile's heat level by 1.

---

**Play Rotate Card**  
Play a Rotate card to rotate one ring of the board clockwise or counter-clockwise, repositioning dishes and empty tiles.

---

**Discard All & Draw N−1**  
Discard your entire hand and draw one fewer card than you discarded. Useful when you have no usable cards.

---

### End of Game

When the last dish tile is eaten, a **final round** begins — every player gets one more turn starting from the player who triggered it. The game also ends immediately if a full round passes with no dish eaten by anyone.

Final scores include base points, completion bonuses, variety bonus, and secret card bonuses.

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
