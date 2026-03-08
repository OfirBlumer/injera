# Neural AI Quick Start Guide

## What You Have

A complete deep reinforcement learning system that learns to play Injera through self-play!

**Key files:**
- `train_neural_ai.py` - Main training script
- `test_neural_ai.py` - Verify setup
- `neural_ai/` - Neural AI implementation
  - `state_encoder.py` - Converts game state to neural network input
  - `policy_network.py` - Neural network architecture
  - `trainer.py` - Self-play training algorithm
  - `neural_player.py` - Integration with game engine
  - `models/` - Saved model checkpoints

## Setup (5 minutes)

### 1. Install PyTorch

```bash
pip install torch numpy
```

Or with CUDA for GPU training (much faster):
```bash
pip install torch numpy --index-url https://download.pytorch.org/whl/cu118
```

### 2. Verify Setup

```bash
python test_neural_ai.py
```

You should see all tests pass ✓

## Training (Your First Model)

### Quick Test Run (5-10 minutes)

Train for 50 games to verify everything works:

```bash
python train_neural_ai.py --games 50 --players 4 --save-every 10
```

**What happens:**
- Plays 50 games with 4 neural AI players learning against each other
- Saves model every 10 games
- Models saved to `neural_ai/models/`
- Shows training progress every 10 games

**Expected output:**
```
Episode 10/50
  Policy Loss: 2.5431
  Value Loss: 1.2345
  Avg Return: -2.1
  Experiences: 234

Saved checkpoint to neural_ai/models/checkpoint_episode_10.pt
```

### Real Training (Hours to Days)

For a competitive AI, train for 5000+ games:

```bash
python train_neural_ai.py --games 5000 --players 4 --save-every 100
```

**Training time estimates:**
- **CPU**: ~5-10 hours for 1000 games
- **GPU**: ~1-2 hours for 1000 games

### Resume Training

If training is interrupted or you want to continue:

```bash
python train_neural_ai.py --games 1000 --resume neural_ai/models/checkpoint_latest.pt
```

## Playing Against Neural AI

### Option 1: Test in Python

```python
from neural_ai.neural_player import NeuralAIPlayer
from engine.game_engine import GameEngine
from engine.action_generator import ActionGenerator

# Load trained model
ai_player = NeuralAIPlayer('neural_ai/models/checkpoint_latest.pt')

# In game loop
valid_actions = ActionGenerator.get_legal_actions(game_state, current_player)
selected_action = ai_player.select_action(game_state, valid_actions)
engine.execute_action(game_state, selected_action)
```

### Option 2: Integrate with Web Interface

Update `ai_support.js` to support neural AI:

```javascript
// Add neural AI level
const AI_LEVELS = {
    'beginner': 'Beginner',
    'intermediate': 'Intermediate',
    'advanced': 'Advanced',
    'expert': 'Expert',
    'neural': 'Neural AI'  // NEW
};
```

Update server to handle neural AI requests:

```python
if ai_level == 'neural':
    from neural_ai.neural_player import NeuralAIPlayer
    if not hasattr(app, 'neural_ai_player'):
        app.neural_ai_player = NeuralAIPlayer('neural_ai/models/checkpoint_latest.pt')
    action = app.neural_ai_player.select_action(game_state, valid_actions)
```

## Understanding the AI

### State Encoding

The neural network sees the full game state:

1. **Board (61 tiles)**: Dish types, hot status, tahini, coordinates
2. **All Players**: Scores, hands, drinks, eaten dishes, **drinks_emptied counter**
3. **Current Player Hand**: Exact cards (other players' hands are hidden)
4. **Deck**: Remaining unseen cards
5. **Meta**: Number of players

**Total: ~1,500 input features**

### Network Architecture

```
Input (1,500) → [512 → 256 → 128] → Output (500 actions)
```

- Uses masked softmax to only select valid actions
- Outputs probability distribution over all possible moves
- Trained with REINFORCE + value baseline

### Learning Process

1. **Self-play**: AI plays against itself
2. **Experience collection**: Records (state, action, reward) for each move
3. **Episode end**: Assigns rewards based on final scores
4. **Training**: Updates network to increase probability of good actions
5. **Repeat**: Gets better over thousands of games

### Reward Structure

- **During game**: +0.1 for successful actions, -1.0 for failures
- **Game end**: Winner gets +10, others get -5 to 0 based on relative score

## Training Tips

### Start Small
- Train 50-100 games first to verify everything works
- Check that loss is decreasing and avg return is improving

### Monitor Progress
- Watch for decreasing policy loss (good)
- Watch for increasing avg return (good)
- Save checkpoints frequently (every 50-100 games)

### Training Schedule

**Phase 1: Random (0-500 games)**
- AI explores randomly
- High variance in performance
- Loss very high (~5-10)

**Phase 2: Learning (500-2000 games)**
- Basic strategies emerge
- AI learns to avoid illegal moves
- Loss decreases (~1-3)

**Phase 3: Refinement (2000-5000 games)**
- Consistent strategic play
- AI discovers tactics
- Loss stabilizes (~0.5-1.0)

**Phase 4: Mastery (5000+ games)**
- Advanced strategies
- Optimal play emerges
- Loss very low (~0.1-0.5)

### Common Issues

**"Out of memory"**
- Reduce batch size in trainer
- Use smaller networks in policy_network.py
- Train with fewer players

**"Training not improving"**
- Verify rewards are correct
- Check that valid actions are generated properly
- Try lower learning rate (1e-5 instead of 1e-4)

**"Actions keep failing"**
- Check game engine integration
- Verify state encoding matches game state
- Ensure action indices map correctly

## Next Steps

1. **Run test**: `python test_neural_ai.py` ✓
2. **Quick train**: `python train_neural_ai.py --games 50 --save-every 10` (5-10 min)
3. **Check results**: Look for saved models in `neural_ai/models/`
4. **Real train**: `python train_neural_ai.py --games 5000 --save-every 100` (hours)
5. **Play against it**: Integrate with your game interface

## Command Reference

```bash
# Test setup
python test_neural_ai.py

# Train new model
python train_neural_ai.py --games 1000 --players 4 --save-every 100

# Resume training
python train_neural_ai.py --games 500 --resume neural_ai/models/checkpoint_latest.pt

# Get help
python train_neural_ai.py --help
```

## Files Generated

After training, you'll find:

```
neural_ai/models/
├── checkpoint_episode_100.pt      # Model at episode 100
├── checkpoint_episode_200.pt      # Model at episode 200
├── checkpoint_latest.pt           # Most recent model
├── stats_episode_100.json         # Training statistics
└── stats_episode_200.json
```

Each checkpoint contains:
- Policy network weights
- Value network weights
- Training history
- Episode number
- Timestamp

## Have Fun!

You now have a state-of-the-art neural AI that can learn to play Injera from scratch. Train it, play against it, and see it improve over time!

**Questions?**
Check the full README in `neural_ai/README.md` for detailed documentation.
