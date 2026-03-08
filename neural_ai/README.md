# Neural AI for Injera Board Game

A deep reinforcement learning AI that learns to play Injera through self-play.

## Overview

This neural AI uses:
- **Policy Gradient (REINFORCE)** algorithm for training
- **Self-play** to learn strategies without human data
- **PyTorch** for neural network implementation
- **Masked softmax** to handle variable action spaces

## Features

- ✅ Trains from scratch through self-play
- ✅ Save/load model checkpoints
- ✅ Resume training from any checkpoint
- ✅ Play against any trained model
- ✅ Configurable: games, players, save intervals
- ✅ Full game state encoding (board, players, drinks, deck)

## Installation

Install required dependencies:

```bash
pip install torch numpy
```

## Quick Start

### 1. Train a Model

Train for 1000 games with 4 players, saving every 100 games:

```bash
python train_neural_ai.py --games 1000 --players 4 --save-every 100
```

### 2. Resume Training

Resume from a saved checkpoint:

```bash
python train_neural_ai.py --games 500 --resume neural_ai/models/checkpoint_episode_1000.pt
```

### 3. Play Against Trained Model

The neural AI can be used in your game by loading a checkpoint:

```python
from neural_ai.neural_player import NeuralAIPlayer

# Load trained model
ai_player = NeuralAIPlayer('neural_ai/models/checkpoint_latest.pt')

# Select action
action = ai_player.select_action(game_state, valid_actions, deterministic=False)
```

## Command-Line Options

### Training Script

```bash
python train_neural_ai.py [OPTIONS]
```

**Options:**
- `--games, -g`: Number of games to play (default: 1000)
- `--players, -p`: Number of players per game (2-6, default: 4)
- `--save-every, -s`: Save checkpoint every N games (default: 100)
- `--save-dir, -d`: Directory to save models (default: neural_ai/models)
- `--resume, -r`: Path to checkpoint to resume from (optional)
- `--learning-rate, -lr`: Learning rate for optimizer (default: 1e-4)

### Examples

**Quick test run:**
```bash
python train_neural_ai.py --games 50 --save-every 10
```

**Long training with 6 players:**
```bash
python train_neural_ai.py --games 10000 --players 6 --save-every 500
```

**Resume interrupted training:**
```bash
python train_neural_ai.py --games 5000 --resume neural_ai/models/checkpoint_latest.pt
```

## Neural Network Architecture

### State Encoding

The neural network receives a comprehensive state encoding:

1. **Board State** (61 tiles × 15 features):
   - Dish type (7 types, one-hot)
   - Hot status, hot token, empty, removed
   - Tahini count, canEatEmpty flag
   - Hex coordinates (q, r)

2. **Player State** (6 players × 29 features):
   - Score, hand size, modifiers
   - Super-hot progression
   - Eaten dishes count
   - **Drinks emptied counter** (0-3, turn-ending tracker)
   - Hand composition (only for current player)
   - Active drinks (count and tokens)
   - Dish counts per type

3. **Deck State** (6 card types):
   - Remaining cards of each type (unseen)

4. **Meta Features**:
   - Number of players

**Total state size:** ~1,500 features

### Network Architecture

**Policy Network:**
- Input layer: 1,500 features
- Hidden layers: 512 → 256 → 128 neurons
- Output layer: 500 actions (masked softmax)
- Activation: ReLU
- Dropout: 0.2

**Value Network (baseline):**
- Input layer: 1,500 features
- Hidden layers: 512 → 256 → 128 neurons
- Output layer: 1 value
- Used for variance reduction

### Training Algorithm

**REINFORCE with Baseline:**
1. Play full game using current policy
2. Collect experiences (state, action, reward)
3. Compute discounted returns
4. Compute advantages using value baseline
5. Update policy to maximize expected return
6. Update value network to predict returns

**Reward Structure:**
- Small positive reward (+0.1) for successful actions
- Penalty (-1.0) for failed actions
- Final reward based on game outcome:
  - Winner: +10
  - Others: -5 to 0 (proportional to score)

## Model Checkpoints

Saved checkpoints include:
- Policy network weights
- Value network weights (if using baseline)
- Optimizer states
- Training history (losses, rewards)
- Episode number
- Timestamp

**File naming:**
- `checkpoint_episode_100.pt`: Saved at episode 100
- `checkpoint_latest.pt`: Most recent checkpoint
- `stats_episode_100.json`: Training statistics

## Integration with Game

### As AI Opponent

Use in your game server or HTML interface:

```python
from neural_ai.neural_player import NeuralAIPlayer

# Initialize
neural_ai = NeuralAIPlayer(
    model_path='neural_ai/models/checkpoint_episode_1000.pt',
    device='cpu'  # or 'cuda' if available
)

# In game loop
valid_actions = ActionGenerator.get_legal_actions(game_state, current_player)
selected_action = neural_ai.select_action(
    game_state,
    valid_actions,
    deterministic=False  # False = sample, True = greedy
)

# Execute action
engine.execute_action(game_state, selected_action)
```

### Add to AI Server

Update `server.py` to support neural AI:

```python
# Add neural AI option
if ai_level == 'neural':
    from neural_ai.neural_player import NeuralAIPlayer
    ai_player = NeuralAIPlayer('neural_ai/models/checkpoint_latest.pt')
    action = ai_player.select_action(game_state, valid_actions)
```

## Training Tips

1. **Start small**: Train on 50-100 games first to verify everything works
2. **Monitor progress**: Check loss values and average returns every 10-50 games
3. **Save frequently**: Models can diverge, so keep checkpoints every 50-100 games
4. **Use GPU**: Training is much faster with CUDA-enabled GPU
5. **Adjust learning rate**: If training is unstable, try lower LR (1e-5)
6. **More players**: Training with 4-6 players gives more diverse experiences

## Performance Expectations

**Training time (CPU):**
- 100 games: ~30-60 minutes
- 1000 games: ~5-10 hours
- 10000 games: ~2-3 days

**Training time (GPU):**
- 100 games: ~5-10 minutes
- 1000 games: ~1-2 hours
- 10000 games: ~10-20 hours

**Learning progress:**
- First 500 games: Random exploration, high variance
- 500-2000 games: Basic strategies emerge
- 2000-5000 games: Consistent strategic play
- 5000+ games: Advanced tactics and optimization

## Troubleshooting

**Out of memory:**
- Reduce batch size or hidden layer sizes in `policy_network.py`
- Use smaller games (fewer players)

**Training not improving:**
- Check that rewards are being computed correctly
- Verify valid actions are being generated
- Try adjusting learning rate or discount factor

**Actions failing:**
- Ensure action generator matches game engine
- Check that state encoding matches actual game state

## Future Improvements

- **PPO algorithm**: More stable than REINFORCE
- **Experience replay**: Reuse past experiences
- **Curriculum learning**: Start with simpler scenarios
- **Opponent diversity**: Train against mix of rule-based and neural AIs
- **Hyperparameter tuning**: Optimize network size, learning rate, etc.

## License

Part of the Injera board game project.
