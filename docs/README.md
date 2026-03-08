# Injera Board Game - AI Players

Play against computer opponents with different skill levels!

## Quick Start

### 1. Install Dependencies

```bash
cd injera_ai
pip install -r requirements.txt
```

### 2. Start the AI Server

```bash
python server.py
```

You should see:
```
🤖 INJERA AI SERVER STARTING
Server will run on: http://localhost:5000
...
```

Keep this terminal window open!

### 3. Open the Game in Your Browser

In a new terminal, navigate to where your `injera_game.html` file is located, then open it in your browser.

**Note:** You'll need to modify `injera_game.html` to add AI player support (see below).

## How It Works

The system has three parts:

1. **Game Engine** (`engine/`) - Core game logic that understands rules and generates legal moves
2. **AI Players** (`ai/`) - Different difficulty levels of computer opponents
3. **Flask Server** (`server.py`) - Web API that the HTML interface calls to get AI moves

When it's an AI player's turn:
- JavaScript sends the current game state to `http://localhost:5000/ai_move`
- Python AI chooses an action
- JavaScript executes that action in the game

## AI Levels

Currently available:

- **Beginner AI** - Makes random legal moves (weighted toward eating dishes)

Coming soon:
- **Intermediate AI** - Uses heuristics to make smarter choices
- **Advanced AI** - Plans ahead multiple turns
- **Expert AI** - Full strategic analysis

## API Endpoints

### `POST /ai_move`

Get an AI's chosen action.

**Request:**
```json
{
  "game_state": { ... },
  "ai_level": "beginner"
}
```

**Response:**
```json
{
  "action": {
    "action_type": "eat_dish",
    "player_id": 1,
    "tile_coord": [2, 3],
    "resource_type": "card"
  },
  "message": "Beginner AI is eating Gomen using Injera card",
  "ai_level": "beginner"
}
```

### `POST /legal_actions`

Get all legal actions for debugging.

**Request:**
```json
{
  "game_state": { ... },
  "player_id": 0
}
```

**Response:**
```json
{
  "actions": [ ... ],
  "count": 15
}
```

### `GET /health`

Check if server is running.

## Next Steps

To integrate AI into your HTML game, you'll need to modify `injera_game.html`:

1. Add player type selection (Human vs AI)
2. Detect when it's an AI player's turn
3. Call the `/ai_move` endpoint
4. Execute the returned action
5. Auto-advance to next turn

I can help you with these modifications! Just let me know when you're ready.

## File Structure

```
injera_ai/
├── engine/
│   ├── __init__.py
│   ├── game_state.py        # Game state representation
│   └── action_generator.py  # Finds legal moves
├── ai/
│   ├── __init__.py
│   └── beginner_ai.py       # Random AI player
├── server.py                # Flask API server
├── requirements.txt         # Python dependencies
└── README.md               # This file
```

## Testing

Test that the server works:

```bash
# In one terminal
python server.py

# In another terminal
curl http://localhost:5000/health
```

You should see: `{"message":"AI server is running","status":"ok"}`

## Troubleshooting

**Problem:** `ModuleNotFoundError: No module named 'flask'`
**Solution:** Run `pip install -r requirements.txt`

**Problem:** Port 5000 already in use
**Solution:** Edit `server.py` and change the port number (e.g., 5001)

**Problem:** CORS errors in browser
**Solution:** Make sure `flask-cors` is installed

## Development

To add a new AI level:

1. Create a new file in `ai/` (e.g., `intermediate_ai.py`)
2. Implement the `choose_action(state)` method
3. Add it to `server.py` in the `ai_instances` dictionary
4. Update the HTML interface to offer it as an option
