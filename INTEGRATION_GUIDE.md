# Neural AI Integration Guide

## How to Use Neural AI in Your Game

### Step 1: Add Neural AI to Python Server (server.py)

**Add import at top of file (after line 24):**

```python
from ai.beginner_ai_v2 import BeginnerAI
from ai.intermediate_ai_v2 import IntermediateAI
from ai.expert_ai_v2 import ExpertAI

# ADD THIS:
from neural_ai.neural_player import NeuralAIPlayer  # NEW
```

**Update ai_instances dictionary (around line 30-34):**

```python
# Store AI instances
ai_instances = {
    'beginner': BeginnerAI(),
    'intermediate': IntermediateAI(),
    'expert': ExpertAI(),
    'neural': None  # NEW - will be lazy loaded
}

# Neural AI model path (change this to your trained model)
NEURAL_MODEL_PATH = 'neural_ai/models/checkpoint_latest.pt'  # NEW
```

**Update get_ai_move function (around line 73-76):**

```python
# Get appropriate AI
ai = ai_instances.get(ai_level)

# ADD THIS BLOCK:
# Lazy load neural AI (only load once, on first use)
if ai_level == 'neural':
    if ai_instances['neural'] is None:
        print(f"Loading neural AI from {NEURAL_MODEL_PATH}...")
        try:
            ai_instances['neural'] = NeuralAIPlayer(NEURAL_MODEL_PATH)
            print("Neural AI loaded successfully!")
        except Exception as e:
            print(f"Error loading neural AI: {e}")
            return jsonify({'error': f'Failed to load neural AI: {str(e)}'}), 500
    ai = ai_instances['neural']

if not ai:
    return jsonify({'error': f'Unknown AI level: {ai_level}'}), 400
```

**Update action selection (around line 78-79):**

```python
# Get AI's chosen action
# REPLACE THIS:
# action = ai.choose_action(state)

# WITH THIS:
if ai_level == 'neural':
    # Neural AI uses different interface
    from engine.action_generator import ActionGenerator
    valid_actions = ActionGenerator.get_legal_actions(state, state.current_player_idx)
    action = ai.select_action(state, valid_actions, deterministic=False)
else:
    # Rule-based AIs use choose_action
    action = ai.choose_action(state)
```

### Complete server.py changes

Here's the full modified section:

```python
# At top (line ~24)
from ai.beginner_ai_v2 import BeginnerAI
from ai.intermediate_ai_v2 import IntermediateAI
from ai.expert_ai_v2 import ExpertAI
from neural_ai.neural_player import NeuralAIPlayer  # NEW

app = Flask(__name__)
CORS(app)

# Store AI instances
ai_instances = {
    'beginner': BeginnerAI(),
    'intermediate': IntermediateAI(),
    'expert': ExpertAI(),
    'neural': None  # NEW - lazy loaded
}

# Neural AI model path
NEURAL_MODEL_PATH = 'neural_ai/models/checkpoint_latest.pt'  # NEW


@app.route('/ai_move', methods=['POST'])
def get_ai_move():
    try:
        data = request.json
        game_state_data = data.get('game_state')
        ai_level = data.get('ai_level', 'beginner')

        if not game_state_data:
            return jsonify({'error': 'No game state provided'}), 400

        # Convert to GameState object
        state = GameState.from_dict(game_state_data)

        # Get appropriate AI
        ai = ai_instances.get(ai_level)

        # Lazy load neural AI
        if ai_level == 'neural':
            if ai_instances['neural'] is None:
                print(f"Loading neural AI from {NEURAL_MODEL_PATH}...")
                try:
                    ai_instances['neural'] = NeuralAIPlayer(NEURAL_MODEL_PATH)
                    print("Neural AI loaded successfully!")
                except Exception as e:
                    print(f"Error loading neural AI: {e}")
                    return jsonify({'error': f'Failed to load neural AI: {str(e)}'}), 500
            ai = ai_instances['neural']

        if not ai:
            return jsonify({'error': f'Unknown AI level: {ai_level}'}), 400

        # Get AI's chosen action
        if ai_level == 'neural':
            from engine.action_generator import ActionGenerator
            valid_actions = ActionGenerator.get_legal_actions(state, state.current_player_idx)
            action = ai.select_action(state, valid_actions, deterministic=False)
        else:
            action = ai.choose_action(state)

        # ... rest of function unchanged ...
```

---

### Step 2: Add Neural AI Option to Web Interface (injera_game.html)

**Find the player setup section (around line 208) and update AI player creation:**

```javascript
// When creating AI players, add neural as an option
// In your HTML player setup UI:

// Example: Add to AI level dropdown
<select id="aiLevel">
    <option value="beginner">Beginner</option>
    <option value="intermediate">Intermediate</option>
    <option value="advanced">Advanced</option>
    <option value="expert">Expert</option>
    <option value="neural">🤖 Neural AI</option>  <!-- NEW -->
</select>
```

**Or if players are hardcoded in the HTML (around line 208):**

```javascript
// Change any AI player's aiLevel to 'neural':
let playersData = [
    {
        "name": "Player 1",
        "position": 0,
        // ... other fields ...
        "drinks": [],
        "drinksEmptied": 0
    },
    {
        "name": "Neural AI",  // Changed name
        "position": 1,
        // ... other fields ...
        "drinks": [],
        "drinksEmptied": 0,
        "isAI": true,
        "aiLevel": "neural"  // Changed from "beginner" to "neural"
    },
    // ... other players ...
];
```

---

### Step 3: Update ai_support.js (Optional - Better AI Display)

**Add neural AI to AI config (around line 19):**

```javascript
const AI_CONFIG = {
    serverUrl: 'http://localhost:5000',
    enabled: true,
    autoPlay: true,
    thinkingDelay: 800,
    levels: {  // NEW
        'beginner': 'Beginner',
        'intermediate': 'Intermediate',
        'expert': 'Expert',
        'neural': '🤖 Neural AI'  // NEW
    }
};
```

**Update AI display in player panel (around line 540):**

```javascript
// In updatePlayersPanel override:
if (playersData[idx] && playersData[idx].isAI) {
    card.classList.add('ai');
    const h2 = card.querySelector('h2');
    if (h2 && !h2.textContent.includes('[AI]')) {
        const aiLevel = playersData[idx].aiLevel || 'AI';
        const levelDisplay = AI_CONFIG.levels[aiLevel] || aiLevel;  // NEW
        h2.textContent = h2.textContent.replace(playersData[idx].name,
            `[AI] ${playersData[idx].name} (${levelDisplay})`);  // NEW
    }
}
```

---

## Testing Your Integration

### 1. Start the Server

```bash
cd "c:\Users\obfel\injera\fullProject\injera_ai_complete\injera_ai"
python server.py
```

You should see:
```
* Running on http://127.0.0.1:5000
```

### 2. Open Your Game

Open `injera_game.html` in a browser

### 3. Verify Neural AI Loads

When it's the neural AI's turn, check the console (F12) for:
```
Loading neural AI from neural_ai/models/checkpoint_latest.pt...
Loaded neural AI from neural_ai/models/checkpoint_latest.pt
  Episode: 1000
Neural AI loaded successfully!
```

### 4. Play!

The neural AI will now play automatically during its turns!

---

## Changing Models

To use a different trained model:

**In server.py:**
```python
# Change this line to point to your desired model
NEURAL_MODEL_PATH = 'neural_ai/models/checkpoint_episode_5000.pt'
```

**Or use environment variable:**
```python
import os
NEURAL_MODEL_PATH = os.getenv('NEURAL_MODEL_PATH', 'neural_ai/models/checkpoint_latest.pt')
```

Then start server with:
```bash
NEURAL_MODEL_PATH="neural_ai/models/checkpoint_episode_5000.pt" python server.py
```

---

## Troubleshooting

**"Failed to load neural AI: No such file"**
- Make sure you've trained a model first
- Check the path in `NEURAL_MODEL_PATH`
- Verify the file exists: `ls neural_ai/models/`

**"Neural AI taking too long"**
- First inference is slower (model loading)
- Subsequent moves should be fast (<1 second)
- Consider using `deterministic=True` for faster greedy selection

**"Neural AI making bad moves"**
- Early checkpoints (< 1000 games) are weak
- Train for 5000+ games for competitive play
- Use later checkpoints (checkpoint_episode_5000.pt)

**"Out of memory"**
- Neural AI uses more memory than rule-based
- Consider using CPU instead of GPU in server
- Close other programs if needed

---

## Summary

To integrate neural AI:
1. ✅ **server.py**: Add imports, lazy loading, action selection
2. ✅ **injera_game.html**: Set `aiLevel: "neural"` for AI players
3. ⚠️ **ai_support.js**: (Optional) Better AI display

Then just play! The neural AI will act like any other AI opponent but using your trained model.
