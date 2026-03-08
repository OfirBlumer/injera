#!/usr/bin/env python3
"""
Command-line script to train neural AI through PPO self-play
"""

import argparse
import sys
from pathlib import Path

# Add neural_ai to path
sys.path.append(str(Path(__file__).parent))

from neural_ai.trainer import train_self_play


def main():
    parser = argparse.ArgumentParser(
        description="Train neural AI through PPO self-play",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        '--games', '-g',
        type=int,
        default=10000,
        help="Total number of games to play"
    )

    parser.add_argument(
        '--players', '-p',
        type=int,
        nargs='+',
        default=[2, 3, 4, 5, 6],
        help="Player counts to cycle through (e.g. -p 2 3 4 5 6)"
    )

    parser.add_argument(
        '--batch-games', '-b',
        type=int,
        default=8,
        help="Number of games per PPO update batch"
    )

    parser.add_argument(
        '--save-every', '-s',
        type=int,
        default=200,
        help="Save checkpoint every N games"
    )

    parser.add_argument(
        '--save-dir', '-d',
        type=str,
        default="neural_ai/models",
        help="Directory to save models"
    )

    parser.add_argument(
        '--resume', '-r',
        type=str,
        default=None,
        help="Path to checkpoint to resume training from"
    )

    parser.add_argument(
        '--learning-rate', '-lr',
        type=float,
        default=3e-4,
        help="Learning rate for optimizer"
    )

    parser.add_argument(
        '--special-cards', '-sc',
        type=int,
        default=0,
        help="Number of special cards dealt to each player (0=disabled)"
    )

    parser.add_argument(
        '--entropy-coeff', '-ec',
        type=float,
        default=0.01,
        help="Entropy coefficient for PPO (higher = more exploration)"
    )

    parser.add_argument(
        '--sparse-rewards',
        action='store_true',
        default=False,
        help="Only use end-of-game rank-based rewards (no per-action shaping)"
    )

    parser.add_argument(
        '--reward-scale', '-rs',
        type=float,
        default=1.0,
        help="Scale factor for per-action shaped rewards (0.0=sparse, 1.0=full, 0.1=hybrid)"
    )

    parser.add_argument(
        '--rotate-bonus',
        type=float,
        default=0.5,
        help="Fixed reward bonus per rotate card played (independent of --reward-scale)"
    )

    parser.add_argument(
        '--tahini-bonus',
        type=float,
        default=0.5,
        help="Fixed reward bonus per tahini token consumed (independent of --reward-scale)"
    )

    args = parser.parse_args()

    # Validate arguments
    if args.games <= 0:
        print("Error: Number of games must be positive")
        sys.exit(1)

    if args.save_every <= 0:
        print("Error: Save interval must be positive")
        sys.exit(1)

    # Print configuration
    print("\n" + "="*60)
    print("PPO NEURAL AI TRAINING")
    print("="*60)
    print(f"Total games: {args.games}")
    print(f"Player counts: {args.players} (cycling)")
    print(f"Batch size: {args.batch_games} games per PPO update")
    print(f"Save every: {args.save_every} games")
    print(f"Save directory: {args.save_dir}")
    print(f"Learning rate: {args.learning_rate}")
    print(f"Entropy coefficient: {args.entropy_coeff}")
    if args.sparse_rewards:
        print(f"Reward mode: sparse (rank only)")
    elif args.reward_scale != 1.0:
        print(f"Reward mode: hybrid (shaped x{args.reward_scale} + rank)")
    else:
        print(f"Reward mode: shaped (score-delta + rank)")
    print(f"Rotate bonus: {args.rotate_bonus}  Tahini bonus: {args.tahini_bonus}")
    if args.special_cards > 0:
        print(f"Special cards per player: {args.special_cards}")
    if args.resume:
        print(f"Resuming from: {args.resume}")
    print("="*60 + "\n")

    # Confirm before starting
    try:
        response = input("Start training? (y/n): ")
        if response.lower() != 'y':
            print("Training cancelled.")
            sys.exit(0)
    except KeyboardInterrupt:
        print("\nTraining cancelled.")
        sys.exit(0)

    # Start training
    try:
        train_self_play(
            num_games=args.games,
            num_players=args.players,
            save_every=args.save_every,
            save_dir=args.save_dir,
            resume_from=args.resume,
            learning_rate=args.learning_rate,
            batch_games=args.batch_games,
            special_cards_per_player=args.special_cards,
            entropy_coeff=args.entropy_coeff,
            sparse_rewards=args.sparse_rewards,
            reward_scale=args.reward_scale,
            rotate_bonus=args.rotate_bonus,
            tahini_bonus=args.tahini_bonus
        )
    except KeyboardInterrupt:
        print("\n\nTraining interrupted by user. Progress has been saved.")
        sys.exit(0)
    except Exception as e:
        print(f"\n\nError during training: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
