"""
Neural Player - Integration with game engine
Connects neural network AI with the game engine
"""

import sys
from pathlib import Path
import numpy as np
import torch
import random
from typing import List, Dict, Any, Tuple
import os

# Add parent directory to path to find engine module
current_dir = Path(__file__).parent
project_root = current_dir.parent
sys.path.insert(0, str(project_root))

# Now import from engine
try:
    from engine.game_engine import GameEngine, compute_special_card_scores
    from engine.action_generator import ActionGenerator
    from engine.game_state import GameState, ActionType
except ImportError as e:
    print(f"Error importing engine modules: {e}")
    print(f"Current directory: {os.getcwd()}")
    print(f"Project root: {project_root}")
    print(f"sys.path: {sys.path[:3]}")
    raise

try:
    from neural_ai.state_encoder import (
        StateEncoder, ACTION_SPACE_SIZE,
        build_coord_to_board_idx, action_to_fixed_index
    )
    from neural_ai.trainer import Experience
except ImportError:
    from .state_encoder import (
        StateEncoder, ACTION_SPACE_SIZE,
        build_coord_to_board_idx, action_to_fixed_index
    )
    from .trainer import Experience


def create_game_runner(encoder: StateEncoder, special_cards_per_player: int = 0, sparse_rewards: bool = False, reward_scale: float = 1.0, rotate_bonus: float = 0.5, tahini_bonus: float = 0.5):
    """
    Create a game runner function for self-play (PPO-compatible).

    Args:
        encoder: State encoder instance
        special_cards_per_player: Number of special cards dealt to each player (0=disabled)

    Returns:
        game_runner function
    """

    def game_runner(policy_net, value_net, num_players: int) -> List[List[Experience]]:
        """
        Run one complete game using the policy network.

        Args:
            policy_net: Policy network for action selection
            value_net: Value network for state value estimates (PPO baseline)
            num_players: Number of players

        Returns:
            List of experience lists (one per player)
        """
        # Initialize game
        engine = GameEngine(num_players, special_cards_per_player=special_cards_per_player)
        game_state = engine.initialize_game()

        # Track experiences for each player
        all_experiences = [[] for _ in range(num_players)]

        # Game loop
        max_turns = 500  # Reduced from 1000 - a real game shouldn't need this many
        turn_count = 0

        # Loop detection: track consecutive same-type actions per player
        last_action_type = [None] * num_players
        repeat_count = [0] * num_players
        MAX_REPEATS = 10  # Force end turn after 10 consecutive same-type non-scoring actions

        while not engine.is_game_over(game_state) and turn_count < max_turns:
            current_player_idx = game_state.current_player_idx

            # Generate valid actions
            valid_actions = ActionGenerator.get_legal_actions(game_state, current_player_idx)

            if len(valid_actions) == 0:
                engine.end_turn(game_state)
                turn_count += 1
                continue

            # Encode state
            state_dict = engine.game_state_to_dict(game_state)
            state_vector = encoder.encode_state(state_dict, current_player_idx)

            # Build fixed-index-to-Action map and action mask
            board = state_dict['board']
            coord_to_idx = build_coord_to_board_idx(board)
            fixed_to_action = {}
            for act in valid_actions:
                fi = action_to_fixed_index(act, coord_to_idx, board)
                if fi >= 0:
                    fixed_to_action[fi] = act

            action_mask = encoder.encode_action_mask(valid_actions, board)

            # Select action using policy network
            policy_net.eval()
            with torch.no_grad():
                state_tensor = torch.FloatTensor(state_vector).unsqueeze(0)
                mask_tensor = torch.FloatTensor(action_mask).unsqueeze(0)

                action_probs, _ = policy_net(state_tensor, mask_tensor)

                # Sample from policy (no epsilon-greedy; PPO entropy bonus handles exploration)
                dist = torch.distributions.Categorical(action_probs[0])
                action_idx = dist.sample().item()
                log_prob = dist.log_prob(torch.tensor(action_idx)).item()

                # Get value estimate for this state
                value = value_net(state_tensor).squeeze().item() if value_net else 0.0

            # Map fixed index back to Action object
            if action_idx in fixed_to_action:
                selected_action = fixed_to_action[action_idx]
            else:
                # Fallback: pick first legal action (mask should prevent this)
                selected_action = valid_actions[0]

            # Loop detection: if same action type repeated too many times, force end turn
            at = selected_action.action_type
            if at == last_action_type[current_player_idx]:
                repeat_count[current_player_idx] += 1
            else:
                repeat_count[current_player_idx] = 0
                last_action_type[current_player_idx] = at

            if repeat_count[current_player_idx] >= MAX_REPEATS and at == ActionType.END_TURN:
                # Stuck in END_TURN loop - just force it and move on
                engine.end_turn(game_state)
                turn_count += 1
                continue

            # Store experience
            experience = Experience(
                state=state_vector,
                action_mask=action_mask,
                action=action_idx,
                reward=0.0,
                log_prob=log_prob,
                value=value
            )
            all_experiences[current_player_idx].append(experience)

            # Track score and tahini before action
            score_before = engine.players[current_player_idx].score
            tahini_before = engine.players[current_player_idx].tahini_consumed

            # Execute action
            success = engine.execute_action(game_state, selected_action)

            # Determine shaping scale: sparse_rewards overrides reward_scale to 0
            shaping = 0.0 if sparse_rewards else reward_scale

            if not success:
                experience.reward = -1.0 * shaping
                engine.end_turn(game_state)
            else:
                if shaping > 0:
                    # Score-delta reward
                    score_after = engine.players[current_player_idx].score
                    score_delta = score_after - score_before
                    experience.reward = float(score_delta) * shaping

                    # Small bonus for PLAY_DRINK (delayed value)
                    if selected_action.action_type == ActionType.PLAY_DRINK:
                        experience.reward += 1.5 * shaping

                # Rotate bonus: only if the board improved according to the value network
                if selected_action.action_type == ActionType.PLAY_ROTATE and rotate_bonus > 0 and value_net:
                    new_state_dict = engine.game_state_to_dict(game_state)
                    new_state_vec = encoder.encode_state(new_state_dict, current_player_idx)
                    new_state_tensor = torch.FloatTensor(new_state_vec).unsqueeze(0)
                    with torch.no_grad():
                        v_after = value_net(new_state_tensor).squeeze().item()
                    if v_after > value:
                        experience.reward += rotate_bonus

                # Tahini bonus (independent of reward_scale)
                tahini_eaten = engine.players[current_player_idx].tahini_consumed - tahini_before
                if tahini_eaten > 0 and tahini_bonus > 0:
                    experience.reward += tahini_bonus * tahini_eaten

                # End turn if: explicit END_TURN or Coffee/Beer finished
                if selected_action.action_type == ActionType.END_TURN or engine.force_end_turn:
                    engine.force_end_turn = False
                    engine.end_turn(game_state)

            turn_count += 1

        # If we hit max turns, end the game
        truncated = turn_count >= max_turns
        if truncated:
            engine.game_over = True
            game_state.game_over = True

        # Apply special card bonuses to player scores before ranking
        if special_cards_per_player > 0:
            sc_bonuses = compute_special_card_scores(engine.players, num_players)
            for pi, bonus in enumerate(sc_bonuses):
                engine.players[pi].score += bonus
            # Sync updated scores to game_state
            for pi in range(num_players):
                game_state.players[pi].score = engine.players[pi].score

        # Game over - assign rank-based final rewards
        final_scores = [p.score for p in game_state.players]

        # Compute ranks (1-indexed, ties share the same rank)
        sorted_unique = sorted(set(final_scores), reverse=True)
        score_to_rank = {s: r + 1 for r, s in enumerate(sorted_unique)}

        n = num_players
        for player_idx, experiences in enumerate(all_experiences):
            if len(experiences) == 0:
                continue

            player_score = game_state.players[player_idx].score
            rank = score_to_rank[player_score]

            # Rank-based rewards: 1st = +30, last = -15, linearly interpolated
            if n <= 1:
                final_reward = 30.0
            else:
                final_reward = 30.0 - (rank - 1) * 45.0 / (n - 1)

            if truncated:
                final_reward -= 3.0

            # Add final reward to last experience
            if experiences:
                experiences[-1].reward += final_reward

        return all_experiences

    return game_runner


class NeuralAIPlayer:
    """Neural AI player that can be used in the game"""

    def __init__(self, model_path: str, device: str = 'cpu'):
        """
        Initialize neural AI player

        Args:
            model_path: Path to trained model checkpoint
            device: Device to run on ('cpu' or 'cuda')
        """
        self.device = torch.device(device)
        self.encoder = StateEncoder()

        # Load model
        from .policy_network import PolicyNetwork, ValueNetwork

        self.policy_net = PolicyNetwork(
            state_size=self.encoder.total_state_size,
            action_size=self.encoder.get_action_space_size()
        ).to(self.device)

        self.value_net = ValueNetwork(
            state_size=self.encoder.total_state_size
        ).to(self.device)

        checkpoint = torch.load(model_path, map_location=self.device)
        self.policy_net.load_state_dict(checkpoint['policy_state_dict'])
        self.policy_net.eval()
        if 'value_state_dict' in checkpoint:
            self.value_net.load_state_dict(checkpoint['value_state_dict'])
            self.value_net.eval()
        else:
            self.value_net = None
        self.last_action_probs = []  # Debug: probabilities from last select_action call

        print(f"Loaded neural AI from {model_path}")
        print(f"  Episode: {checkpoint.get('episode', 'unknown')}")

    def select_action(self, game_state: GameState, valid_actions: List[Any], deterministic: bool = False) -> Any:
        """
        Select action given game state and valid actions

        Args:
            game_state: Current game state
            valid_actions: List of valid actions
            deterministic: If True, select best action. If False, sample from distribution

        Returns:
            Selected action
        """
        if len(valid_actions) == 0:
            return None

        # Convert game state to dictionary
        state_dict = game_state.to_dict()

        # Encode state
        current_player_idx = game_state.current_player_idx
        state_vector = self.encoder.encode_state(state_dict, current_player_idx)

        # Build fixed-index-to-Action map
        board = state_dict['board']
        coord_to_idx = build_coord_to_board_idx(board)
        fixed_to_action = {}
        for act in valid_actions:
            fi = action_to_fixed_index(act, coord_to_idx, board)
            if fi >= 0:
                fixed_to_action[fi] = act

        # Create action mask (fixed action space)
        action_mask = self.encoder.encode_action_mask(valid_actions, board)

        # Select action
        with torch.no_grad():
            state_tensor = torch.FloatTensor(state_vector).unsqueeze(0).to(self.device)
            mask_tensor = torch.FloatTensor(action_mask).unsqueeze(0).to(self.device)

            action_probs, _ = self.policy_net(state_tensor, mask_tensor)

            # Store full probability vector and fixed-index map for debug display
            self.last_action_probs_full = action_probs[0].cpu().numpy()
            self.last_fixed_to_action = fixed_to_action

            if deterministic:
                action_idx = torch.argmax(action_probs[0]).item()
            else:
                dist = torch.distributions.Categorical(action_probs[0])
                action_idx = dist.sample().item()

        # Map fixed index back to Action object
        if action_idx in fixed_to_action:
            selected = fixed_to_action[action_idx]

            # If a rotate was chosen, verify it actually improves the board
            if selected.action_type == ActionType.PLAY_ROTATE and self.value_net:
                if not self._rotate_improves_board(game_state, selected, state_vector):
                    # Suppress all rotate actions and re-select
                    rotate_indices = [fi for fi, act in fixed_to_action.items()
                                      if act.action_type == ActionType.PLAY_ROTATE]
                    suppressed_mask = action_mask.copy()
                    for ri in rotate_indices:
                        suppressed_mask[ri] = 0.0
                    if suppressed_mask.sum() > 0:
                        with torch.no_grad():
                            sup_mask_tensor = torch.FloatTensor(suppressed_mask).unsqueeze(0).to(self.device)
                            action_probs2, _ = self.policy_net(state_tensor, sup_mask_tensor)
                            if deterministic:
                                action_idx = torch.argmax(action_probs2[0]).item()
                            else:
                                dist2 = torch.distributions.Categorical(action_probs2[0])
                                action_idx = dist2.sample().item()
                        if action_idx in fixed_to_action:
                            selected = fixed_to_action[action_idx]

            return selected

        # Fallback (mask should prevent this)
        return valid_actions[0]

    def _rotate_improves_board(self, game_state: GameState, rotate_action, state_vector_before) -> bool:
        """Check if executing a rotate improves the board according to the value network."""
        import copy
        from engine.game_engine import GameEngine

        v_before = self.value_net(
            torch.FloatTensor(state_vector_before).unsqueeze(0).to(self.device)
        ).squeeze().item()

        # Deep copy the game state and execute the rotate on the copy
        state_copy = copy.deepcopy(game_state)
        engine = GameEngine(len(game_state.players))
        engine.execute_action(state_copy, rotate_action)

        # Encode and evaluate new state
        state_dict = state_copy.to_dict()
        new_state_vec = self.encoder.encode_state(state_dict, game_state.current_player_idx)
        new_tensor = torch.FloatTensor(new_state_vec).unsqueeze(0).to(self.device)
        with torch.no_grad():
            v_after = self.value_net(new_tensor).squeeze().item()

        return v_after > v_before


# Command-line interface for playing against neural AI
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Play against neural AI")
    parser.add_argument('--model', type=str, required=True, help="Path to model checkpoint")
    parser.add_argument('--deterministic', action='store_true', help="Use deterministic action selection")

    args = parser.parse_args()

    # Load player
    player = NeuralAIPlayer(args.model, device='cpu')

    print("\nNeural AI loaded and ready!")
    print("Use this player in your game by setting ai_level='neural' and providing the model path.")
