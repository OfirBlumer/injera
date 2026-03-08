#!/usr/bin/env python3
"""
Run benchmark games with neural AI players and collect statistics.

Usage:
  # All players use the same checkpoint
  python benchmark_ai.py --games 100 --players 3 --checkpoints model.pt

  # Each player uses a different checkpoint (compare progress)
  python benchmark_ai.py --games 100 --players 3 --checkpoints ck_50k.pt ck_100k.pt ck_200k.pt

  # Deterministic play, save to custom file
  python benchmark_ai.py --games 50 --players 2 --checkpoints model.pt --deterministic --output results.json
"""

import argparse
import json
import sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime

sys.path.append(str(Path(__file__).parent))

SPECIAL_CARD_NAMES = {
    0: 'four_by_four',
    1: 'tahini_freak',
    2: 'sesame_intolerance',
    3: 'tahini_queen',
    4: 'tasting_menu',
    5: 'picky_eater',
    6: 'some_like_it_hot',
    7: 'hot_monster',
    8: 'berbere_freak',
    9: 'no_hot_for_you',
    10: 'peas_please',
    11: 'peas_prince',
    12: 'lentils_party',
    13: 'lentils_princess',
    14: 'savage_cabbage',
    15: 'cabbage_king',
    16: 'healthy_appetite',
    17: 'consolation_prize',
    18: 'delicate_palate',
}


def _drink_token_snapshot(player):
    """Return current token counts per drink type for a player."""
    counts = defaultdict(int)
    for d in player.active_drinks:
        counts[d.drink_type.value] += d.tokens_remaining
    return counts


def run_games(num_games, num_players, checkpoints, deterministic, special_cards):
    from engine.game_engine import GameEngine, compute_special_card_scores
    from engine.game_state import ActionType
    from engine.action_generator import ActionGenerator
    from neural_ai.neural_player import NeuralAIPlayer
    from injera_game import DishType

    NON_HOT_DISHES = {d.value for d in DishType.get_non_hot()}

    # Load neural players (one per unique checkpoint, cached)
    print("Loading checkpoints...")
    ai_cache = {}
    ai_players = []
    for ck in checkpoints:
        if ck not in ai_cache:
            ai_cache[ck] = NeuralAIPlayer(ck)
        ai_players.append(ai_cache[ck])

    all_game_stats = []

    for game_idx in range(num_games):
        engine = GameEngine(num_players, special_cards_per_player=special_cards)
        game_state = engine.initialize_game()


        per_player = []
        for pi in range(num_players):
            sc_names = [SPECIAL_CARD_NAMES[cid] for cid in engine.players[pi].special_cards]
            per_player.append({
                'player_idx': pi,
                'checkpoint': checkpoints[pi],
                'special_cards_received': sc_names,
                'cards_dealt': defaultdict(int),   # all card types received (played + in hand at end)
                'drink_cards_played': 0,
                'rotate_cards_played': 0,
                'tahini_cards_played': 0,
                'drink_tokens_consumed': defaultdict(int),  # {'Coffee': N, 'Beer': M, 'Water': K}
                'tahini_consumed': 0,
                'dishes_eaten': defaultdict(int),
                'completion_bonuses': [],           # dish names where player ate all 7 tiles (+15 each)
                'variety_bonus': 0,
                'final_score': 0,
                'special_card_bonus': 0,
                'rank': 0,
            })

        max_turns = 600
        turn_count = 0
        last_action_type = [None] * num_players
        repeat_count = [0] * num_players
        turns_since_eat = 0  # Force game over if no dish eaten for too long

        while not engine.is_game_over(game_state) and turn_count < max_turns:
            pi = game_state.current_player_idx
            ai = ai_players[pi]

            # No-progress safeguard: end game if no dish eaten in 50 consecutive turns
            if turns_since_eat >= 50:
                break

            # Snapshot total dishes eaten across all players before this turn
            total_eaten_before = sum(len(engine.players[p].eaten_dishes) for p in range(num_players))

            valid_actions = ActionGenerator.get_legal_actions(game_state, pi)
            if not valid_actions:
                engine.end_turn(game_state)
                turn_count += 1
                turns_since_eat += 1
                continue

            action = ai.select_action(game_state, valid_actions, deterministic=deterministic)
            if action is None:
                engine.end_turn(game_state)
                turn_count += 1
                turns_since_eat += 1
                continue

            at = action.action_type

            # Loop detection: force end turn if any action type repeats too many times
            if at == last_action_type[pi]:
                repeat_count[pi] += 1
            else:
                repeat_count[pi] = 0
                last_action_type[pi] = at
            if repeat_count[pi] >= 10:
                repeat_count[pi] = 0  # Reset so next turn they can try again
                engine.end_turn(game_state)
                turn_count += 1
                turns_since_eat += 1
                continue

            eaten_before = len(engine.players[pi].eaten_dishes)

            # Snapshot drink tokens BEFORE action (catches all consumption, including hot dish eating)
            drink_snapshot_before = _drink_token_snapshot(engine.players[pi])

            success = engine.execute_action(game_state, action)

            if success:
                if at == ActionType.PLAY_DRINK:
                    per_player[pi]['drink_cards_played'] += 1
                    if action.drink_card_type:
                        per_player[pi]['cards_dealt'][action.drink_card_type] += 1
                elif at == ActionType.PLAY_ROTATE:
                    per_player[pi]['rotate_cards_played'] += 1
                    per_player[pi]['cards_dealt']['Rotate'] += 1
                elif at == ActionType.ADD_TAHINI:
                    per_player[pi]['tahini_cards_played'] += 1
                    per_player[pi]['cards_dealt']['Tahini'] += 1
                elif at in (ActionType.EAT_DISH, ActionType.EAT_EMPTY_TILE):
                    if action.discard_card_type:
                        per_player[pi]['cards_dealt'][action.discard_card_type] += 1

                # Track drink tokens consumed (works for standalone DRINK_TOKEN and hot dish eating)
                drink_snapshot_after = _drink_token_snapshot(engine.players[pi])
                for dtype, before_count in drink_snapshot_before.items():
                    after_count = drink_snapshot_after.get(dtype, 0)
                    consumed = before_count - after_count
                    if consumed > 0:
                        per_player[pi]['drink_tokens_consumed'][dtype] += consumed

                # Track newly eaten dishes
                for dish in engine.players[pi].eaten_dishes[eaten_before:]:
                    per_player[pi]['dishes_eaten'][dish.value] += 1

                if at == ActionType.END_TURN or engine.force_end_turn:
                    engine.force_end_turn = False
                    engine.end_turn(game_state)
            else:
                engine.end_turn(game_state)

            # Update no-progress counter based on whether any dish was eaten this turn
            total_eaten_after = sum(len(engine.players[p].eaten_dishes) for p in range(num_players))
            if total_eaten_after > total_eaten_before:
                turns_since_eat = 0
            else:
                turns_since_eat += 1

            turn_count += 1

        # Collect final stats
        sc_bonuses = [0] * num_players
        if special_cards > 0:
            sc_bonuses = compute_special_card_scores(engine.players, num_players)
            for pi, bonus in enumerate(sc_bonuses):
                engine.players[pi].score += bonus

        final_scores = [engine.players[pi].score for pi in range(num_players)]
        sorted_unique = sorted(set(final_scores), reverse=True)
        score_to_rank = {s: r + 1 for r, s in enumerate(sorted_unique)}

        for pi in range(num_players):
            p = engine.players[pi]

            # Cards remaining in hand at game end count toward cards_dealt
            for card in p.hand:
                per_player[pi]['cards_dealt'][card.card_type.name] += 1

            # Completion bonuses: +15 for eating all 7 tiles of a non-hot dish
            for dish in NON_HOT_DISHES:
                dish_type = next(d for d in DishType if d.value == dish)
                if p.count_dish_type(dish_type) >= 7:
                    per_player[pi]['completion_bonuses'].append(dish)

            per_player[pi]['variety_bonus'] = p.get_variety_bonus()
            per_player[pi]['tahini_consumed'] = p.tahini_consumed
            per_player[pi]['final_score'] = p.score
            per_player[pi]['special_card_bonus'] = sc_bonuses[pi]
            per_player[pi]['rank'] = score_to_rank[p.score]
            per_player[pi]['cards_dealt'] = dict(per_player[pi]['cards_dealt'])
            per_player[pi]['drink_tokens_consumed'] = dict(per_player[pi]['drink_tokens_consumed'])
            per_player[pi]['dishes_eaten'] = dict(per_player[pi]['dishes_eaten'])

        scores_str = ', '.join(f"P{i}:{final_scores[i]}" for i in range(num_players))
        print(f"Game {game_idx + 1}/{num_games}: {scores_str}  turns={turn_count}")

        all_game_stats.append({
            'game': game_idx + 1,
            'turns': turn_count,
            'truncated': turn_count >= max_turns,
            'players': per_player,
        })

    return all_game_stats


def compute_summary(all_game_stats, checkpoints):
    by_checkpoint = {}
    for ck in set(checkpoints):
        by_checkpoint[ck] = {
            'appearances': 0,
            'wins': 0,
            'total_score': 0,
            'total_rank': 0,
            'cards_dealt': defaultdict(int),
            'drink_cards_played': 0,
            'rotate_cards_played': 0,
            'tahini_cards_played': 0,
            'drink_tokens_consumed': defaultdict(int),
            'tahini_consumed': 0,
            'dishes': defaultdict(int),
            'completion_bonuses': defaultdict(int),
            'variety_bonus': 0,
        }

    for game in all_game_stats:
        for ps in game['players']:
            ck = ps['checkpoint']
            s = by_checkpoint[ck]
            s['appearances'] += 1
            s['total_score'] += ps['final_score']
            s['total_rank'] += ps['rank']
            if ps['rank'] == 1:
                s['wins'] += 1
            for card, cnt in ps['cards_dealt'].items():
                s['cards_dealt'][card] += cnt
            s['drink_cards_played'] += ps['drink_cards_played']
            s['rotate_cards_played'] += ps['rotate_cards_played']
            s['tahini_cards_played'] += ps['tahini_cards_played']
            for dtype, cnt in ps['drink_tokens_consumed'].items():
                s['drink_tokens_consumed'][dtype] += cnt
            s['tahini_consumed'] += ps['tahini_consumed']
            for dish, count in ps['dishes_eaten'].items():
                s['dishes'][dish] += count
            for dish in ps['completion_bonuses']:
                s['completion_bonuses'][dish] += 1
            s['variety_bonus'] += ps['variety_bonus']

    summary = {}
    for ck, s in by_checkpoint.items():
        n = s['appearances']
        summary[ck] = {
            'appearances': n,
            'win_rate': round(s['wins'] / n, 3),
            'avg_score': round(s['total_score'] / n, 2),
            'avg_rank': round(s['total_rank'] / n, 2),
            'avg_cards_dealt': {k: round(v / n, 2) for k, v in sorted(s['cards_dealt'].items())},
            'avg_drink_cards_played': round(s['drink_cards_played'] / n, 2),
            'avg_rotate_cards_played': round(s['rotate_cards_played'] / n, 2),
            'avg_tahini_cards_played': round(s['tahini_cards_played'] / n, 2),
            'avg_drink_tokens_consumed': {k: round(v / n, 2) for k, v in sorted(s['drink_tokens_consumed'].items())},
            'avg_tahini_consumed': round(s['tahini_consumed'] / n, 2),
            'avg_dishes': {d: round(c / n, 2) for d, c in sorted(s['dishes'].items(), key=lambda x: -x[1])},
            'completion_bonus_rate': {d: round(c / n, 3) for d, c in sorted(s['completion_bonuses'].items(), key=lambda x: -x[1])},
            'avg_variety_bonus': round(s['variety_bonus'] / n, 2),
        }

    return summary


def print_summary(summary):
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for ck, s in summary.items():
        name = Path(ck).name
        print(f"\n{name}  ({s['appearances']} appearances)")
        print(f"  Win rate: {s['win_rate']:.1%}   Avg rank: {s['avg_rank']:.2f}   Avg score: {s['avg_score']:.1f}")
        print(f"  Cards dealt (avg): {s['avg_cards_dealt']}")
        print(f"  Drink cards played: {s['avg_drink_cards_played']:.1f}   "
              f"Rotates: {s['avg_rotate_cards_played']:.1f}   "
              f"Tahini cards: {s['avg_tahini_cards_played']:.1f}")
        print(f"  Drink tokens consumed: {s['avg_drink_tokens_consumed']}")
        print(f"  Tahini consumed: {s['avg_tahini_consumed']:.1f}")
        print(f"  Variety bonus (avg): {s['avg_variety_bonus']:.1f}")
        if s['completion_bonus_rate']:
            print(f"  Completion bonuses (rate per game):")
            for dish, rate in s['completion_bonus_rate'].items():
                print(f"    {dish:<30} {rate:.3f}")
        print(f"  Dishes eaten (avg per game):")
        for dish, avg in s['avg_dishes'].items():
            print(f"    {dish:<30} {avg:.2f}")


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark neural AI players",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('--games', '-g', type=int, default=100,
                        help="Number of games to play")
    parser.add_argument('--players', '-p', type=int, default=2,
                        help="Number of players per game")
    parser.add_argument('--checkpoints', '-c', nargs='+', required=True,
                        help="Checkpoint path(s): one for all players, or one per player")
    parser.add_argument('--deterministic', action='store_true', default=False,
                        help="Use deterministic (argmax) action selection")
    parser.add_argument('--special-cards', '-sc', type=int, default=1,
                        help="Special cards dealt per player (0=disabled, default=1)")
    parser.add_argument('--output', '-o', type=str, default=None,
                        help="Output JSON file path (default: auto-generated with timestamp)")

    args = parser.parse_args()

    checkpoints = args.checkpoints
    if len(checkpoints) == 1:
        checkpoints = checkpoints * args.players
    elif len(checkpoints) != args.players:
        print(f"Error: provide 1 checkpoint (shared by all) or exactly {args.players} (one per player)")
        sys.exit(1)

    # Auto-generate output filename if not specified
    if args.output is None:
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        ck_name = Path(checkpoints[0]).stem  # e.g. "checkpoint_episode_150000"
        mode = 'd' if args.deterministic else 's'
        args.output = f"benchmark_{args.players}p_{args.games}g_{ck_name}_{ts}_{mode}.json"

    print(f"\nBenchmark: {args.games} games, {args.players} players, "
          f"{'deterministic' if args.deterministic else 'stochastic'}")
    for i, ck in enumerate(checkpoints):
        print(f"  Player {i}: {ck}")
    print()

    all_game_stats = run_games(
        num_games=args.games,
        num_players=args.players,
        checkpoints=checkpoints,
        deterministic=args.deterministic,
        special_cards=args.special_cards,
    )

    summary = compute_summary(all_game_stats, checkpoints)

    output = {
        'config': {
            'games': args.games,
            'players': args.players,
            'checkpoints': checkpoints,
            'deterministic': args.deterministic,
            'special_cards': args.special_cards,
        },
        'summary': summary,
        'games': all_game_stats,
    }

    with open(args.output, 'w') as f:
        json.dump(output, f, indent=2)

    print_summary(summary)
    print(f"\nFull results saved to {args.output}")


if __name__ == "__main__":
    main()
