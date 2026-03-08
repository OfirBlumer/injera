# 📦 COMPLETE FILE GUIDE - What Each File Does

This document explains EVERY file in the AI system, what it does, and how it communicates with other files.

## 📂 Directory Structure

```
injera_ai/
├── 📁 engine/                    ← Core game logic (Python)
│   ├── __init__.py
│   ├── game_state.py
│   └── action_generator.py
│
├── 📁 ai/                        ← AI players (Python)
│   ├── __init__.py
│   └── beginner_ai.py
│
├── 🌐 server.py                  ← Web server (Python)
├── 🧪 test_ai.py                 ← Test suite (Python)
├── 🚀 quick_start.py             ← Setup helper (Python)
│
├── 🎮 ai_support.js              ← ADD THIS TO YOUR HTML (JavaScript)
│
├── 📦 requirements.txt           ← Python dependencies
│
└── 📚 Documentation/
    ├── PROJECT_OVERVIEW.txt      ← Visual architecture diagram
    ├── SIMPLE_INTEGRATION.md     ← Quick start (5 min setup)
    ├── INTEGRATION_GUIDE.md      ← Detailed integration steps
    ├── SUMMARY.md                ← Complete reference
    └── README.md                 ← General overview
```

---

## 🔍 DETAILED FILE BREAKDOWN

### 1️⃣ engine/game_state.py
**Purpose:** Represents the complete game state
**Language:** Python
**Size:** ~300 lines

**What it does:**
- Defines data structures for the game (tiles, players, cards, etc.)
- Can convert game state to/from JSON (for sending to JavaScript)
- Tracks all game information: board, players, deck, scores

**Key Classes:**
- `GameState` - Complete game snapshot
- `TileState` - One hex tile
- `PlayerState` - One player
- `CardState` - One card
- `Action` - One possible move

**Communicates with:**
- `action_generator.py` - Uses GameState to find legal moves
- `server.py` - Converts GameState to/from JSON for web
- `beginner_ai.py` - Receives GameState, returns Action

**Data Flow:**
```
JavaScript (browser) → JSON → GameState object → AI → Action → JSON → JavaScript
```

---

### 2️⃣ engine/action_generator.py
**Purpose:** Finds all legal moves in any game state
**Language:** Python
**Size:** ~350 lines

**What it does:**
- Analyzes the current board and player state
- Generates list of every legal action a player can take
- Validates game rules (reachability, resources, hot handling)
- Used by AI to see what moves are possible

**Key Function:**
- `get_legal_actions(state, player_id)` → Returns list of Action objects

**Example:**
```python
# Input: Game state + player ID
state = GameState(...)
actions = ActionGenerator.get_legal_actions(state, player_id=0)

# Output: List of actions
[
    Action(type=EAT_DISH, tile=(2,3), resource='card'),
    Action(type=PLAY_DRINK, card_index=1),
    Action(type=END_TURN),
    ...
]
```

**Communicates with:**
- `game_state.py` - Reads GameState, returns Actions
- `beginner_ai.py` - AI calls this to see options
- `server.py` - Used by /legal_actions endpoint (debugging)

**Data Flow:**
```
GameState → ActionGenerator → List[Action] → AI chooses one
```

---

### 3️⃣ ai/beginner_ai.py
**Purpose:** Random AI player (beginner difficulty)
**Language:** Python
**Size:** ~100 lines

**What it does:**
- Receives current game state
- Gets all legal moves
- Randomly picks one (with slight preference for eating)
- Returns the chosen action

**Key Method:**
```python
def choose_action(self, state: GameState) -> Action:
    legal_actions = ActionGenerator.get_legal_actions(state, state.current_player_idx)
    # Prefer eating dishes (70%), drinks (20%), other (10%)
    return random.choice(eat_actions or drink_actions or other_actions)
```

**Communicates with:**
- `action_generator.py` - Gets legal moves
- `server.py` - Called when AI needs to move
- `game_state.py` - Receives GameState

**Data Flow:**
```
GameState → BeginnerAI.choose_action() → Action
```

---

### 4️⃣ server.py (MOST IMPORTANT!)
**Purpose:** Web API server that connects Python AI to JavaScript game
**Language:** Python (Flask)
**Size:** ~150 lines

**What it does:**
- Runs a web server on http://localhost:5000
- Receives game state from browser (as JSON)
- Converts JSON to GameState object
- Asks AI to choose a move
- Sends action back to browser (as JSON)

**Key Endpoints:**

**POST /ai_move**
```
Browser sends:
{
  "game_state": { board, players, deck, ... },
  "ai_level": "beginner"
}

Server responds:
{
  "action": { action_type: "eat_dish", tile_coord: [2,3], ... },
  "message": "Beginner AI is eating Gomen using Injera card"
}
```

**GET /health**
```
Browser sends: GET request

Server responds:
{
  "status": "ok",
  "message": "AI server is running"
}
```

**How to run:**
```bash
python server.py
```

**Communicates with:**
- `ai_support.js` - Receives HTTP requests from browser
- `beginner_ai.py` - Calls AI to get move
- `game_state.py` - Converts JSON ↔ GameState

**Data Flow:**
```
Browser (JS) → HTTP POST → server.py → GameState → AI → Action → JSON → Browser
```

**THIS IS THE BRIDGE between Python and JavaScript!**

---

### 5️⃣ ai_support.js (ADD THIS TO YOUR HTML!)
**Purpose:** JavaScript code that enables AI in your browser game
**Language:** JavaScript
**Size:** ~400 lines

**What it does:**
- Detects when it's an AI player's turn
- Sends current game state to Python server (HTTP)
- Receives AI's chosen action
- Executes that action in the browser game
- Shows "AI is thinking..." messages

**Key Functions:**

**handleAITurnIfNeeded()**
```javascript
// Called at end of nextTurn()
// Checks if current player is AI
// If yes, calls handleAITurn()
```

**handleAITurn()**
```javascript
// 1. Prepare game state as JSON
// 2. POST to http://localhost:5000/ai_move
// 3. Receive action
// 4. Execute action
// 5. Continue to next turn
```

**executeAIAction(action)**
```javascript
// Takes the action from Python
// Calls specific executor based on type
// Updates game state in browser
```

**How to use:**
Add to your HTML:
```html
<script src="ai_support.js"></script>
```

**Communicates with:**
- `injera_game.html` - Your existing game
- `server.py` - Sends HTTP requests

**Data Flow:**
```
Your HTML game → ai_support.js → HTTP → server.py → AI → HTTP → ai_support.js → Updates game
```

---

### 6️⃣ test_ai.py
**Purpose:** Automated tests to verify everything works
**Language:** Python
**Size:** ~200 lines

**What it does:**
- Creates test game states
- Tests ActionGenerator finds legal moves
- Tests AI can choose actions
- Tests JSON serialization works
- Runs automatically to verify system health

**How to run:**
```bash
python test_ai.py
```

**Output:**
```
✅ ALL TESTS PASSED!
```

**Communicates with:**
- `game_state.py` - Creates test states
- `action_generator.py` - Tests move generation
- `beginner_ai.py` - Tests AI decision making

---

### 7️⃣ quick_start.py
**Purpose:** Helper script to set everything up quickly
**Language:** Python
**Size:** ~100 lines

**What it does:**
- Checks Python version
- Installs dependencies
- Runs tests
- Offers to start the server

**How to run:**
```bash
python quick_start.py
```

**Communicates with:**
- `requirements.txt` - Installs packages
- `test_ai.py` - Runs tests
- `server.py` - Can launch server

---

### 8️⃣ requirements.txt
**Purpose:** Lists Python packages needed
**Language:** Plain text
**Size:** 2 lines

**Contents:**
```
flask==3.0.0
flask-cors==4.0.0
```

**How to use:**
```bash
pip install -r requirements.txt
```

---

### 9️⃣ __init__.py files
**Purpose:** Make folders into Python packages
**Language:** Python
**Size:** ~10 lines each

**What they do:**
- Allow `from engine import GameState`
- Allow `from ai import BeginnerAI`
- Required by Python to import modules

---

## 🔄 COMPLETE COMMUNICATION FLOW

Here's how everything works together:

### Scenario: AI's Turn in Browser

```
STEP 1: Player clicks "Next Turn"
├─ injera_game.html
│  └─ nextTurn() function runs
│     └─ Calls: handleAITurnIfNeeded()  ← from ai_support.js

STEP 2: Check if AI player
├─ ai_support.js
│  └─ handleAITurnIfNeeded()
│     └─ Checks: playersData[currentPlayerIdx].isAI === true?
│        └─ YES → Call handleAITurn()

STEP 3: Send game state to Python
├─ ai_support.js
│  └─ handleAITurn()
│     └─ Prepares JSON: { board, players, deck, ... }
│     └─ fetch('http://localhost:5000/ai_move', { ... })
│        │
│        ▼
├─ 🌐 HTTP REQUEST (over network, localhost)
│        │
│        ▼
├─ server.py
│  └─ @app.route('/ai_move')
│     └─ Receives JSON
│     └─ GameState.from_dict(json)  ← Converts to Python object
│        │
│        ▼
├─ engine/game_state.py
│  └─ Creates GameState object
│     │
│     ▼
├─ server.py
│  └─ ai = BeginnerAI()
│  └─ action = ai.choose_action(state)
│     │
│     ▼
├─ ai/beginner_ai.py
│  └─ choose_action(state)
│     └─ legal_actions = ActionGenerator.get_legal_actions(state, player_id)
│        │
│        ▼
├─ engine/action_generator.py
│  └─ get_legal_actions()
│     └─ Returns: [Action(...), Action(...), ...]
│        │
│        ▼
├─ ai/beginner_ai.py
│  └─ chosen_action = random.choice(legal_actions)
│     └─ Returns Action to server
│        │
│        ▼
├─ server.py
│  └─ Converts Action to JSON
│  └─ response = { "action": {...}, "message": "..." }
│     │
│     ▼
├─ 🌐 HTTP RESPONSE
│        │
│        ▼
├─ ai_support.js
│  └─ Receives JSON
│  └─ executeAIAction(action)
│     └─ executeAIEatDish(action) or executeAIPlayDrink(action) etc.
│        └─ Updates: boardData, playersData
│        └─ Calls: updatePlayersPanel(), drawBoard()
│           │
│           ▼
├─ injera_game.html
│  └─ Game state updated!
│  └─ Board redraws with AI's move
│  └─ setTimeout(() => nextTurn(), 500)  ← Next player's turn

DONE! 🎉
```

---

## 📥 WHAT TO DOWNLOAD

Download these files to your computer:

### Essential (Required):
1. **engine/game_state.py** - Game state representation
2. **engine/action_generator.py** - Legal move finder
3. **engine/__init__.py** - Package marker
4. **ai/beginner_ai.py** - AI player
5. **ai/__init__.py** - Package marker
6. **server.py** - Web API server ⭐ MOST IMPORTANT
7. **ai_support.js** - Browser integration ⭐ ADD TO YOUR HTML
8. **requirements.txt** - Dependencies

### Helpful (Recommended):
9. **test_ai.py** - Verify everything works
10. **quick_start.py** - Easy setup
11. **SIMPLE_INTEGRATION.md** - 5-minute setup guide ⭐ START HERE

### Documentation (Optional but useful):
12. **PROJECT_OVERVIEW.txt** - Visual diagram
13. **README.md** - Overview
14. **SUMMARY.md** - Complete reference
15. **INTEGRATION_GUIDE.md** - Detailed guide
16. **FILE_GUIDE.md** - This file!

---

## 🚀 SETUP CHECKLIST

Once you've downloaded everything:

```
□ Create folder: injera_ai/
□ Put all Python files inside
□ Create subfolders: engine/, ai/
□ Put ai_support.js in same folder as your injera_game.html
□ Open terminal in injera_ai/ folder
□ Run: pip install -r requirements.txt
□ Run: python test_ai.py  (should say ✅ ALL TESTS PASSED!)
□ Run: python server.py   (keep this running!)
□ Modify injera_game.html (see SIMPLE_INTEGRATION.md)
□ Open injera_game.html in browser
□ Play against AI! 🎮
```

---

## ❓ COMMON QUESTIONS

**Q: Which files do I need to modify?**
A: Only ONE! Your `injera_game.html` (add 2 lines, see SIMPLE_INTEGRATION.md)

**Q: Which Python files should I run?**
A: Only `server.py` - the others are libraries it uses

**Q: Where does the AI logic live?**
A: `ai/beginner_ai.py` - this is where you'd add smarter AI later

**Q: How does JavaScript talk to Python?**
A: Through `server.py` using HTTP requests (like visiting a website)

**Q: Can I see what the AI is thinking?**
A: Check browser console (F12) - it logs every action

**Q: How do I make the AI smarter?**
A: Create `ai/intermediate_ai.py` (copy beginner_ai.py and improve the logic)

---

## 🎯 KEY TAKEAWAY

**The system has 3 parts that talk to each other:**

1. **Python Backend** (engine/ + ai/ + server.py)
   - Understands game rules
   - AI makes decisions
   - Runs as web server

2. **JavaScript Bridge** (ai_support.js)
   - Detects AI turns
   - Sends game state to Python
   - Executes AI actions

3. **Your HTML Game** (injera_game.html)
   - Shows the board
   - Handles human input
   - Calls ai_support.js when needed

**They communicate through HTTP (JSON data):**
HTML ↔ ai_support.js ↔ server.py ↔ AI

That's it! 🎉
