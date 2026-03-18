"""
Behavioral Cloning Trainer
Trains the policy network from recorded human game data.

Usage:
    python -m neural_ai.behavioral_cloning --recordings recordings/
    python -m neural_ai.behavioral_cloning --recordings recordings/ --resume neural_ai/models/checkpoint_latest.pt
"""

import sys
import json
import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import random

# Add parent directory to path
current_dir = Path(__file__).parent
project_root = current_dir.parent
sys.path.insert(0, str(project_root))

from engine.game_state import GameState, Action, ActionType, normalize_card_name
from engine.action_generator import ActionGenerator
from neural_ai.state_encoder import (
    StateEncoder, ACTION_SPACE_SIZE,
    build_coord_to_board_idx, action_to_fixed_index
)
from neural_ai.policy_network import PolicyNetwork


def load_recordings(recordings_dir: Path) -> List[Dict]:
    """Load all recorded games from a directory.

    Supports the HTML recording format:
      {version, num_players, steps: [{state, action}, ...]}
    Files named injera_*.json (downloaded from the game UI).
    """
    recordings = []
    for file_path in sorted(recordings_dir.glob('*.json')):
        with open(file_path, 'r') as f:
            data = json.load(f)
        steps = data.get('steps', [])
        recordings.append({
            'file': file_path.name,
            'steps': steps
        })
        print(f"  Loaded {file_path.name}: {len(steps)} steps")
    return recordings


def match_action_to_fixed_index(recorded_action: Dict, legal_actions: List[Action],
                                 board: List[Dict]) -> Optional[int]:
    """
    Find the fixed action-space index for a recorded action.

    1. Compute fixed index of each legal action.
    2. Find the legal action that matches the recorded action fields.
    3. Return its fixed index (used as training target).

    Returns the fixed index, or None if no match found.
    """
    coord_to_idx = build_coord_to_board_idx(board)

    # Build set of legal fixed indices for validation
    legal_fixed_indices = set()
    for legal in legal_actions:
        fi = action_to_fixed_index(legal, coord_to_idx, board)
        if fi >= 0:
            legal_fixed_indices.add(fi)

    # Compute fixed index from the recorded action dict directly
    # For eat_dish with resource_type='tile', we need the resource tile's properties
    # from the board to determine resource_category. The recorded action has
    # resource_tile_coord which we can look up in the board.
    fi = action_to_fixed_index(recorded_action, coord_to_idx, board)

    if fi >= 0 and fi in legal_fixed_indices:
        return fi

    # Fallback: iterate legal actions and match field-by-field, then return fixed index
    action_type = recorded_action.get('action_type')
    for legal in legal_actions:
        if legal.action_type.value != action_type:
            continue

        matched = False
        if action_type == 'eat_dish':
            if legal.tile_coord != tuple(recorded_action.get('tile_coord', [])):
                continue
            if legal.resource_type != recorded_action.get('resource_type'):
                continue
            if legal.resource_type == 'tile':
                rec_tile = recorded_action.get('resource_tile_coord', [])
                if legal.resource_tile_coord != tuple(rec_tile):
                    continue
            rec_discard = recorded_action.get('discard_card_type')
            if rec_discard and legal.discard_card_type != rec_discard:
                continue
            rec_hot = recorded_action.get('num_drink_tokens_for_hot', 0)
            if legal.num_drink_tokens_for_hot != rec_hot:
                continue
            matched = True

        elif action_type == 'eat_empty_tile':
            if legal.tile_coord != tuple(recorded_action.get('tile_coord', [])):
                continue
            rec_discard = recorded_action.get('discard_card_type')
            if rec_discard and legal.discard_card_type != rec_discard:
                continue
            rec_hot = recorded_action.get('num_drink_tokens_for_hot', 0)
            if legal.num_drink_tokens_for_hot != rec_hot:
                continue
            matched = True

        elif action_type == 'play_drink':
            rec_drink_type = recorded_action.get('drink_card_type')
            if rec_drink_type:
                if legal.drink_card_type == normalize_card_name(rec_drink_type):
                    matched = True
            else:
                matched = True  # old recordings without drink_card_type

        elif action_type == 'drink_token':
            if legal.drink_index == recorded_action.get('drink_index'):
                matched = True

        elif action_type == 'play_rotate':
            if legal.rotation_direction == recorded_action.get('rotation_direction'):
                matched = True

        elif action_type in ('add_tahini', 'add_hot_sauce'):
            if legal.tile_coord == tuple(recorded_action.get('tile_coord', [])):
                orient = recorded_action.get('triangle_orientation')
                if orient is None or legal.triangle_orientation == orient:
                    matched = True

        elif action_type in ('end_turn', 'discard_redraw'):
            matched = True

        elif action_type == 'select_special_cards':
            # Support both old format (kept_card_ids: [str]) and new format (kept_cards: [{id, name}])
            raw = recorded_action.get('kept_card_ids') or [c['id'] for c in recorded_action.get('kept_cards', []) if isinstance(c, dict)]
            kept = [c if isinstance(c, str) else c.get('id', '') for c in raw]
            if legal.kept_card_ids and sorted(legal.kept_card_ids) == sorted(kept):
                matched = True

        if matched:
            fi = action_to_fixed_index(legal, coord_to_idx, board)
            if fi >= 0:
                return fi

    return None


def prepare_training_data(recordings: List[Dict], encoder: StateEncoder) -> List[Tuple]:
    """
    Convert recorded games into (state_vector, action_mask, target_fixed_idx) tuples.
    target_fixed_idx is a fixed action space index (0..ACTION_SPACE_SIZE-1).
    """
    training_data = []
    skipped = 0
    total = 0

    for recording in recordings:
        for step in recording['steps']:
            total += 1
            game_state_data = step['state']
            recorded_action = step['action']
            player_id = recorded_action.get('player_id', game_state_data.get('current_player_idx', 0))

            try:
                # Convert to GameState
                state = GameState.from_dict(game_state_data)

                # Get legal actions
                legal_actions = ActionGenerator.get_legal_actions(state, player_id)
                if len(legal_actions) == 0:
                    skipped += 1
                    continue

                # Extract board data for fixed index computation
                board = game_state_data['board']

                # Find matching fixed action index
                fixed_idx = match_action_to_fixed_index(recorded_action, legal_actions, board)
                if fixed_idx is None:
                    skipped += 1
                    continue

                # Encode state
                state_vector = encoder.encode_state(game_state_data, player_id)

                # Create action mask (now uses fixed action space)
                action_mask = encoder.encode_action_mask(legal_actions, board)

                # Verify the target index is valid in the mask
                if action_mask[fixed_idx] != 1.0:
                    skipped += 1
                    continue

                training_data.append((state_vector, action_mask, fixed_idx))

            except Exception as e:
                skipped += 1
                continue

    print(f"\nPrepared {len(training_data)} training samples ({skipped} skipped out of {total})")
    return training_data


def train_behavioral_cloning(
    recordings_dir: str,
    save_dir: str = "neural_ai/models",
    resume_from: Optional[str] = None,
    epochs: int = 100,
    batch_size: int = 64,
    learning_rate: float = 3e-4,
    validation_split: float = 0.1
):
    """
    Train policy network from recorded human games.

    Args:
        recordings_dir: Directory containing game_*.json recordings
        save_dir: Directory to save trained model
        resume_from: Optional checkpoint to fine-tune from
        epochs: Number of training epochs
        batch_size: Batch size for training
        learning_rate: Learning rate
        validation_split: Fraction of data to use for validation
    """
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Using device: {device}")

    # Load recordings
    print(f"\nLoading recordings from {recordings_dir}...")
    recordings = load_recordings(Path(recordings_dir))
    if len(recordings) == 0:
        print("No recordings found! Play some games with recording enabled first.")
        return

    total_steps = sum(len(r['steps']) for r in recordings)
    print(f"Loaded {len(recordings)} games, {total_steps} total steps")

    # Prepare training data
    encoder = StateEncoder()
    training_data = prepare_training_data(recordings, encoder)
    if len(training_data) == 0:
        print("No valid training data could be prepared!")
        return

    # Split into train/validation
    random.shuffle(training_data)
    val_size = max(1, int(len(training_data) * validation_split))
    val_data = training_data[:val_size]
    train_data = training_data[val_size:]
    print(f"Training: {len(train_data)} samples, Validation: {len(val_data)} samples")

    # Create or load model
    policy_net = PolicyNetwork(
        state_size=encoder.total_state_size,
        action_size=encoder.get_action_space_size()
    ).to(device)

    start_info = "from scratch"
    if resume_from:
        checkpoint = torch.load(resume_from, map_location=device)
        policy_net.load_state_dict(checkpoint['policy_state_dict'])
        start_info = f"fine-tuning from {resume_from}"

    optimizer = optim.Adam(policy_net.parameters(), lr=learning_rate)
    criterion = nn.CrossEntropyLoss()

    print(f"\nTraining {start_info}")
    print(f"  Epochs: {epochs}, Batch size: {batch_size}, LR: {learning_rate}")
    print(f"  State size: {encoder.total_state_size}, Action size: {encoder.get_action_space_size()}")
    print()

    best_val_acc = 0.0

    for epoch in range(epochs):
        # Training
        policy_net.train()
        random.shuffle(train_data)
        total_loss = 0.0
        correct = 0
        total = 0

        for batch_start in range(0, len(train_data), batch_size):
            batch = train_data[batch_start:batch_start + batch_size]

            states = torch.FloatTensor(np.array([d[0] for d in batch])).to(device)
            masks = torch.FloatTensor(np.array([d[1] for d in batch])).to(device)
            targets = torch.LongTensor([d[2] for d in batch]).to(device)

            # Forward pass
            action_probs, logits = policy_net(states, masks)

            # Cross-entropy loss on masked logits
            # Apply mask to logits for loss computation
            masked_logits = logits.clone()
            masked_logits[masks == 0] = -1e9
            loss = criterion(masked_logits, targets)

            # Backward pass
            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(policy_net.parameters(), max_norm=1.0)
            optimizer.step()

            total_loss += loss.item() * len(batch)

            # Accuracy
            predictions = torch.argmax(action_probs, dim=1)
            correct += (predictions == targets).sum().item()
            total += len(batch)

        train_loss = total_loss / total
        train_acc = correct / total

        # Validation
        policy_net.eval()
        val_correct = 0
        val_total = 0
        val_loss = 0.0

        with torch.no_grad():
            for batch_start in range(0, len(val_data), batch_size):
                batch = val_data[batch_start:batch_start + batch_size]

                states = torch.FloatTensor(np.array([d[0] for d in batch])).to(device)
                masks = torch.FloatTensor(np.array([d[1] for d in batch])).to(device)
                targets = torch.LongTensor([d[2] for d in batch]).to(device)

                action_probs, logits = policy_net(states, masks)
                masked_logits = logits.clone()
                masked_logits[masks == 0] = -1e9
                loss = criterion(masked_logits, targets)

                val_loss += loss.item() * len(batch)
                predictions = torch.argmax(action_probs, dim=1)
                val_correct += (predictions == targets).sum().item()
                val_total += len(batch)

        val_loss = val_loss / max(1, val_total)
        val_acc = val_correct / max(1, val_total)

        # Print progress
        if (epoch + 1) % 5 == 0 or epoch == 0:
            print(f"Epoch {epoch+1}/{epochs}  "
                  f"Train Loss: {train_loss:.4f}  Acc: {train_acc:.1%}  |  "
                  f"Val Loss: {val_loss:.4f}  Acc: {val_acc:.1%}")

        # Save best model
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            save_path = Path(save_dir)
            save_path.mkdir(parents=True, exist_ok=True)

            checkpoint = {
                'policy_state_dict': policy_net.state_dict(),
                'episode': 0,
                'training_type': 'behavioral_cloning',
                'train_acc': train_acc,
                'val_acc': val_acc,
                'epochs': epoch + 1,
                'num_recordings': len(recordings),
                'num_samples': len(training_data)
            }
            torch.save(checkpoint, save_path / 'checkpoint_bc_best.pt')

    # Save final model
    save_path = Path(save_dir)
    save_path.mkdir(parents=True, exist_ok=True)

    checkpoint = {
        'policy_state_dict': policy_net.state_dict(),
        'episode': 0,
        'training_type': 'behavioral_cloning',
        'train_acc': train_acc,
        'val_acc': val_acc,
        'epochs': epochs,
        'num_recordings': len(recordings),
        'num_samples': len(training_data)
    }
    torch.save(checkpoint, save_path / 'checkpoint_bc_final.pt')

    print(f"\nTraining complete!")
    print(f"  Best validation accuracy: {best_val_acc:.1%}")
    print(f"  Models saved to {save_dir}/checkpoint_bc_best.pt and checkpoint_bc_final.pt")
    print(f"\nTo use this model:")
    print(f"  1. Copy checkpoint_bc_best.pt to checkpoint_episode_*.pt format")
    print(f"  2. Or pass directly to NeuralAIPlayer")
    print(f"  3. Or fine-tune with self-play: python train_neural_ai.py --resume {save_dir}/checkpoint_bc_best.pt")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Train neural AI from recorded human games")
    parser.add_argument('--recordings', '-r', type=str, default='recordings',
                        help="Directory containing game recordings")
    parser.add_argument('--save-dir', type=str, default='neural_ai/models',
                        help="Directory to save trained model")
    parser.add_argument('--resume', type=str, default=None,
                        help="Checkpoint to fine-tune from (e.g. from self-play)")
    parser.add_argument('--epochs', type=int, default=100,
                        help="Number of training epochs")
    parser.add_argument('--batch-size', type=int, default=64,
                        help="Training batch size")
    parser.add_argument('--lr', type=float, default=3e-4,
                        help="Learning rate")

    args = parser.parse_args()

    train_behavioral_cloning(
        recordings_dir=args.recordings,
        save_dir=args.save_dir,
        resume_from=args.resume,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr
    )
