"""
Self-Play Trainer for Neural AI
PPO (Proximal Policy Optimization) with GAE (Generalized Advantage Estimation)
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple, Any, Optional
import json
from datetime import datetime


from .policy_network import PolicyNetwork, ValueNetwork
from .state_encoder import StateEncoder


class Experience:
    """Single experience tuple (PPO-compatible)"""
    def __init__(self, state: np.ndarray, action_mask: np.ndarray,
                 action: int, reward: float, log_prob: float,
                 value: float = 0.0):
        self.state = state
        self.action_mask = action_mask
        self.action = action
        self.reward = reward
        self.log_prob = log_prob   # log pi_old(a|s) - needed for PPO ratio
        self.value = value         # V(s) estimate at collection time


class SelfPlayTrainer:
    """PPO self-play trainer with GAE advantage estimation"""

    def __init__(self,
                 state_size: int,
                 action_size: int,
                 learning_rate: float = 3e-4,
                 gamma: float = 0.99,
                 gae_lambda: float = 0.95,
                 clip_epsilon: float = 0.2,
                 entropy_coeff: float = 0.01,
                 value_coeff: float = 0.5,
                 ppo_epochs: int = 4,
                 minibatch_size: int = 128,
                 max_grad_norm: float = 0.5,
                 batch_games: int = 8):
        """
        Args:
            state_size: Size of state vector
            action_size: Maximum action space size
            learning_rate: Learning rate for optimizer
            gamma: Discount factor for rewards
            gae_lambda: Lambda for GAE advantage estimation
            clip_epsilon: PPO clipping parameter
            entropy_coeff: Coefficient for entropy bonus
            value_coeff: Coefficient for value loss
            ppo_epochs: Number of optimization epochs per batch
            minibatch_size: Minibatch size for PPO updates
            max_grad_norm: Maximum gradient norm for clipping
            batch_games: Number of games to collect before each PPO update
        """
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        print(f"Using device: {self.device}")

        self.state_size = state_size
        self.action_size = action_size
        self.gamma = gamma
        self.gae_lambda = gae_lambda
        self.clip_epsilon = clip_epsilon
        self.entropy_coeff = entropy_coeff
        self.value_coeff = value_coeff
        self.ppo_epochs = ppo_epochs
        self.minibatch_size = minibatch_size
        self.max_grad_norm = max_grad_norm
        self.batch_games = batch_games

        # Networks
        self.policy_net = PolicyNetwork(state_size, action_size).to(self.device)
        self.value_net = ValueNetwork(state_size).to(self.device)

        # Single optimizer for both networks (common in PPO implementations)
        self.optimizer = optim.Adam([
            {'params': self.policy_net.parameters(), 'lr': learning_rate},
            {'params': self.value_net.parameters(), 'lr': learning_rate}
        ])

        # Training stats
        self.policy_losses = []
        self.value_losses = []
        self.entropies = []
        self.clip_fractions = []
        self.avg_returns = []

    def collect_batch(self, game_runner, player_counts: List[int],
                      episode_offset: int) -> List[List[Experience]]:
        """
        Collect a batch of games for PPO training.

        Args:
            game_runner: Function that runs a game
            player_counts: List of player counts to cycle through
            episode_offset: Current episode number (for cycling)

        Returns:
            List of all player trajectories (flattened across games)
        """
        all_trajectories = []

        for game_idx in range(self.batch_games):
            num_players = player_counts[(episode_offset + game_idx) % len(player_counts)]
            game_experiences = game_runner(self.policy_net, self.value_net, num_players)

            for player_experiences in game_experiences:
                if len(player_experiences) > 0:
                    all_trajectories.append(player_experiences)

        return all_trajectories

    def compute_gae(self, trajectory: List[Experience]) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute GAE advantages and returns for a single trajectory.

        Returns:
            advantages: np.ndarray of shape (T,)
            returns: np.ndarray of shape (T,) - advantage + value = return target
        """
        T = len(trajectory)
        advantages = np.zeros(T, dtype=np.float32)
        returns = np.zeros(T, dtype=np.float32)

        # Bootstrap from last value (0 since game is over)
        last_gae = 0.0
        last_value = 0.0  # Terminal state value = 0

        for t in reversed(range(T)):
            reward = trajectory[t].reward
            value = trajectory[t].value

            # TD error: delta = r + gamma * V(s') - V(s)
            delta = reward + self.gamma * last_value - value

            # GAE: A_t = delta_t + (gamma * lambda) * A_{t+1}
            advantages[t] = last_gae = delta + self.gamma * self.gae_lambda * last_gae

            # Return target = advantage + value
            returns[t] = advantages[t] + value

            last_value = value

        return advantages, returns

    def train_batch(self, trajectories: List[List[Experience]]) -> Dict[str, float]:
        """
        Perform PPO update on a batch of trajectories.

        Args:
            trajectories: List of experience trajectories

        Returns:
            Dictionary of training metrics
        """
        if len(trajectories) == 0:
            return {'policy_loss': 0, 'value_loss': 0, 'entropy': 0,
                    'clip_fraction': 0, 'avg_return': 0, 'num_experiences': 0}

        # Compute GAE for all trajectories
        all_states = []
        all_masks = []
        all_actions = []
        all_old_log_probs = []
        all_advantages = []
        all_returns = []

        total_return = 0.0
        total_traj = 0

        for trajectory in trajectories:
            advantages, returns = self.compute_gae(trajectory)

            for i, exp in enumerate(trajectory):
                all_states.append(exp.state)
                all_masks.append(exp.action_mask)
                all_actions.append(exp.action)
                all_old_log_probs.append(exp.log_prob)
                all_advantages.append(advantages[i])
                all_returns.append(returns[i])

            # Track avg return per trajectory
            total_return += sum(exp.reward for exp in trajectory)
            total_traj += 1

        num_samples = len(all_states)
        if num_samples == 0:
            return {'policy_loss': 0, 'value_loss': 0, 'entropy': 0,
                    'clip_fraction': 0, 'avg_return': 0, 'num_experiences': 0}

        # Convert to tensors
        states_t = torch.FloatTensor(np.array(all_states)).to(self.device)
        masks_t = torch.FloatTensor(np.array(all_masks)).to(self.device)
        actions_t = torch.LongTensor(all_actions).to(self.device)
        old_log_probs_t = torch.FloatTensor(all_old_log_probs).to(self.device)
        advantages_t = torch.FloatTensor(all_advantages).to(self.device)
        returns_t = torch.FloatTensor(all_returns).to(self.device)

        # Normalize advantages (crucial for PPO stability)
        if advantages_t.std() > 1e-6:
            advantages_t = (advantages_t - advantages_t.mean()) / (advantages_t.std() + 1e-8)

        # PPO epochs: reuse the same batch multiple times
        total_policy_loss = 0.0
        total_value_loss = 0.0
        total_entropy = 0.0
        total_clip_fraction = 0.0
        num_updates = 0

        for _ in range(self.ppo_epochs):
            # Shuffle and create minibatches
            indices = np.random.permutation(num_samples)

            for start in range(0, num_samples, self.minibatch_size):
                end = min(start + self.minibatch_size, num_samples)
                mb_indices = indices[start:end]

                mb_states = states_t[mb_indices]
                mb_masks = masks_t[mb_indices]
                mb_actions = actions_t[mb_indices]
                mb_old_log_probs = old_log_probs_t[mb_indices]
                mb_advantages = advantages_t[mb_indices]
                mb_returns = returns_t[mb_indices]

                # Forward pass
                self.policy_net.train()
                self.value_net.train()

                action_probs, _ = self.policy_net(mb_states, mb_masks)
                values = self.value_net(mb_states).squeeze(-1)

                # New log probs
                new_log_probs = torch.log(
                    action_probs.gather(1, mb_actions.unsqueeze(1)).squeeze(1) + 1e-10
                )

                # PPO ratio: r(theta) = pi_new / pi_old
                ratio = torch.exp(new_log_probs - mb_old_log_probs)

                # Clipped surrogate objective
                surr1 = ratio * mb_advantages
                surr2 = torch.clamp(ratio, 1.0 - self.clip_epsilon,
                                    1.0 + self.clip_epsilon) * mb_advantages
                policy_loss = -torch.min(surr1, surr2).mean()

                # Value loss (clipped)
                value_loss = F.mse_loss(values, mb_returns)

                # Entropy bonus
                entropy = -(action_probs * torch.log(action_probs + 1e-10)).sum(dim=1).mean()

                # Combined loss
                loss = policy_loss + self.value_coeff * value_loss - self.entropy_coeff * entropy

                # Backward pass
                self.optimizer.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(self.policy_net.parameters(), self.max_grad_norm)
                nn.utils.clip_grad_norm_(self.value_net.parameters(), self.max_grad_norm)
                self.optimizer.step()

                # Track metrics
                with torch.no_grad():
                    clip_fraction = ((ratio - 1.0).abs() > self.clip_epsilon).float().mean().item()

                total_policy_loss += policy_loss.item()
                total_value_loss += value_loss.item()
                total_entropy += entropy.item()
                total_clip_fraction += clip_fraction
                num_updates += 1

        # Average metrics
        avg_return = total_return / max(1, total_traj)
        metrics = {
            'policy_loss': total_policy_loss / max(1, num_updates),
            'value_loss': total_value_loss / max(1, num_updates),
            'entropy': total_entropy / max(1, num_updates),
            'clip_fraction': total_clip_fraction / max(1, num_updates),
            'avg_return': avg_return,
            'num_experiences': num_samples,
            'num_trajectories': total_traj
        }

        # Record stats
        self.policy_losses.append(metrics['policy_loss'])
        self.value_losses.append(metrics['value_loss'])
        self.entropies.append(metrics['entropy'])
        self.clip_fractions.append(metrics['clip_fraction'])
        self.avg_returns.append(avg_return)

        return metrics

    def save_checkpoint(self, save_dir: Path, episode: int, metadata: Optional[Dict] = None):
        """Save model checkpoint"""
        save_dir = Path(save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)

        checkpoint = {
            'episode': episode,
            'policy_state_dict': self.policy_net.state_dict(),
            'value_state_dict': self.value_net.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'policy_losses': self.policy_losses[-200:],
            'value_losses': self.value_losses[-200:],
            'entropies': self.entropies[-200:],
            'clip_fractions': self.clip_fractions[-200:],
            'avg_returns': self.avg_returns[-200:],
            'timestamp': datetime.now().isoformat(),
            'algorithm': 'ppo'
        }

        if metadata:
            checkpoint['metadata'] = metadata

        # Save checkpoint
        checkpoint_path = save_dir / f"checkpoint_episode_{episode}.pt"
        torch.save(checkpoint, checkpoint_path)

        # Also save as latest
        latest_path = save_dir / "checkpoint_latest.pt"
        torch.save(checkpoint, latest_path)

        # Save training stats as JSON
        stats = {
            'episode': episode,
            'policy_losses': self.policy_losses[-100:],
            'value_losses': self.value_losses[-100:],
            'entropies': self.entropies[-100:],
            'clip_fractions': self.clip_fractions[-100:],
            'avg_returns': self.avg_returns[-100:]
        }
        stats_path = save_dir / f"stats_episode_{episode}.json"
        with open(stats_path, 'w') as f:
            json.dump(stats, f, indent=2)

        print(f"Saved checkpoint to {checkpoint_path}")

    def load_checkpoint(self, checkpoint_path: Path):
        """Load model checkpoint"""
        checkpoint = torch.load(checkpoint_path, map_location=self.device)

        self.policy_net.load_state_dict(checkpoint['policy_state_dict'])

        if 'value_state_dict' in checkpoint:
            self.value_net.load_state_dict(checkpoint['value_state_dict'])

        if 'optimizer_state_dict' in checkpoint:
            self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])

        self.policy_losses = checkpoint.get('policy_losses', [])
        self.value_losses = checkpoint.get('value_losses', [])
        self.entropies = checkpoint.get('entropies', [])
        self.clip_fractions = checkpoint.get('clip_fractions', [])
        self.avg_returns = checkpoint.get('avg_returns', [])

        episode = checkpoint.get('episode', 0)
        algo = checkpoint.get('algorithm', 'unknown')
        print(f"Loaded checkpoint from episode {episode} (algorithm: {algo})")

        return episode


def train_self_play(num_games: int,
                    num_players,
                    save_every: int,
                    save_dir: str = "neural_ai/models",
                    resume_from: Optional[str] = None,
                    learning_rate: float = 3e-4,
                    batch_games: int = 8,
                    special_cards_per_player: int = 0,
                    entropy_coeff: float = 0.01,
                    sparse_rewards: bool = False,
                    reward_scale: float = 1.0,
                    rotate_bonus: float = 0.5,
                    tahini_bonus: float = 0.5):
    """
    Main PPO training loop.

    Args:
        num_games: Total number of games to play
        num_players: int or list of ints - player counts to cycle through
        save_every: Save checkpoint every N games
        save_dir: Directory to save models
        resume_from: Path to checkpoint to resume from
        learning_rate: Learning rate for optimizer
        batch_games: Number of games per PPO update batch
        special_cards_per_player: Number of special cards dealt per player (0=disabled)
    """
    import sys
    from pathlib import Path

    # Ensure we can import from parent directory
    project_root = Path(__file__).parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from neural_ai.neural_player import create_game_runner

    # Normalize num_players to a list
    if isinstance(num_players, int):
        player_counts = [num_players]
    else:
        player_counts = list(num_players)

    # Setup
    encoder = StateEncoder()
    trainer = SelfPlayTrainer(
        state_size=encoder.total_state_size,
        action_size=encoder.get_action_space_size(),
        learning_rate=learning_rate,
        batch_games=batch_games,
        entropy_coeff=entropy_coeff
    )

    start_episode = 0
    if resume_from:
        start_episode = trainer.load_checkpoint(Path(resume_from))

    # Create game runner
    game_runner = create_game_runner(encoder, special_cards_per_player=special_cards_per_player, sparse_rewards=sparse_rewards, reward_scale=reward_scale, rotate_bonus=rotate_bonus, tahini_bonus=tahini_bonus)

    # Training loop
    print(f"\n{'='*60}")
    print(f"PPO Self-Play Training")
    print(f"  Total games: {num_games}")
    print(f"  Player counts: {player_counts} (cycling)")
    print(f"  Batch size: {batch_games} games per PPO update")
    print(f"  PPO epochs: {trainer.ppo_epochs}")
    print(f"  Minibatch size: {trainer.minibatch_size}")
    print(f"  Learning rate: {learning_rate}")
    print(f"  Clip epsilon: {trainer.clip_epsilon}")
    print(f"  Entropy coeff: {trainer.entropy_coeff}")
    print(f"  GAE lambda: {trainer.gae_lambda}")
    print(f"  Save every: {save_every} games")
    print(f"  Save directory: {save_dir}")
    if special_cards_per_player > 0:
        print(f"  Special cards per player: {special_cards_per_player}")
    print(f"{'='*60}\n")

    games_played = 0
    batch_num = 0

    while games_played < num_games:
        batch_num += 1
        current_episode = start_episode + games_played

        # Collect a batch of games
        trajectories = trainer.collect_batch(
            game_runner, player_counts, current_episode
        )

        games_played += trainer.batch_games

        # Train on the batch
        metrics = trainer.train_batch(trajectories)

        # Log progress
        print(f"Batch {batch_num} (games {games_played}/{num_games})")
        print(f"  Policy Loss: {metrics['policy_loss']:.4f}  "
              f"Value Loss: {metrics['value_loss']:.4f}  "
              f"Entropy: {metrics['entropy']:.4f}")
        print(f"  Clip Fraction: {metrics['clip_fraction']:.3f}  "
              f"Avg Return: {metrics['avg_return']:.2f}  "
              f"Experiences: {metrics['num_experiences']}  "
              f"Trajectories: {metrics['num_trajectories']}")

        # Save checkpoint (check if we crossed a save boundary)
        total_episode = start_episode + games_played
        prev_games = games_played - trainer.batch_games
        if games_played // save_every > prev_games // save_every or games_played >= num_games:
            trainer.save_checkpoint(
                Path(save_dir),
                total_episode,
                metadata={
                    'player_counts': player_counts,
                    'total_games': total_episode,
                    'batch_games': trainer.batch_games,
                    'learning_rate': learning_rate
                }
            )

    print(f"\nTraining complete! Played {games_played} games in {batch_num} batches.")
    print(f"Models saved to {save_dir}/")


# Run from command line
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Train neural AI through PPO self-play")
    parser.add_argument('--games', type=int, default=10000, help="Total number of games to play")
    parser.add_argument('--players', type=int, nargs='+', default=[2, 3, 4, 5, 6],
                        help="Player counts to cycle through")
    parser.add_argument('--batch-games', type=int, default=8,
                        help="Number of games per PPO update batch")
    parser.add_argument('--save-every', type=int, default=200,
                        help="Save checkpoint every N games")
    parser.add_argument('--save-dir', type=str, default="neural_ai/models",
                        help="Directory to save models")
    parser.add_argument('--resume', type=str, default=None,
                        help="Path to checkpoint to resume from")
    parser.add_argument('--lr', type=float, default=3e-4, help="Learning rate")

    args = parser.parse_args()
    train_self_play(
        num_games=args.games,
        num_players=args.players,
        save_every=args.save_every,
        save_dir=args.save_dir,
        resume_from=args.resume,
        learning_rate=args.lr,
        batch_games=args.batch_games
    )
