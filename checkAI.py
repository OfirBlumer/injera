"""
Quick diagnostic script to check why AI can't find eating actions
Run this with: python check_ai_problem.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.game_state import GameState
from engine.action_generator import ActionGenerator

# Minimal test game state
test_data = {
    "num_players": 2,
    "current_player_idx": 0,
    "board": [
        {"q": 4, "r": 0, "dish": "Gomen", "hot": False, "hotToken": False, "tahini": 0, "empty": False, "removed": False, "canEatEmpty": False},
        {"q": 3, "r": 1, "dish": "Azifa", "hot": False, "hotToken": False, "tahini": 0, "empty": False, "removed": False, "canEatEmpty": False},
    ],
    "players": [
        {
            "name": "Player 1",
            "position": 0,
            "score": 0,
            "hand": [
                {"type": "Clean Injera", "name": "Clean Injera"},
                {"type": "Rotate", "name": "Rotate Injera"}
            ],
            "handSizeModifier": 0,
            "baseHandSize": 5,
            "superHotCount": 0,
            "superHotValue": 3,
            "eaten": [],
            "dishCounts": {},
            "drinks": []
        }
    ],
    "deck": {
        "cardsRemaining": 50,
        "deckSize": 50,
        "discardSize": 0,
        "composition": {}
    },
    "reachable_by_player": [
        [(4, 0), (3, 1)]  # Player 0 can reach these tiles
    ],
    "final_round_active": False,
    "final_round_start_player": -1,
    "game_over": False
}

print("Converting game state...")
state = GameState.from_dict(test_data)

print(f"\nPlayer 0: {state.players[0].name}")
print(f"Hand: {[c.name for c in state.players[0].hand]}")
print(f"Position: {state.players[0].position}")

print(f"\nBoard has {len(state.board)} tiles")
for tile in state.board:
    print(f"  Tile ({tile.q},{tile.r}): {tile.dish}, hot={tile.hot}, empty={tile.empty}, removed={tile.removed}")

print(f"\nReachable tiles for player 0: {state.get_reachable_tiles(0)}")

print("\nGenerating legal actions...")
actions = ActionGenerator.get_legal_actions(state, 0)

print(f"\nFound {len(actions)} legal actions:")
for action in actions:
    print(f"  - {action.action_type.value}: {action}")

eat_actions = [a for a in actions if a.action_type.value == 'EAT_DISH']
print(f"\nEat actions: {len(eat_actions)}")

if len(eat_actions) == 0:
    print("\n❌ PROBLEM: No eat actions found!")
    print("Expected: At least 2 eat actions (one for each reachable dish)")
else:
    print("\n✓ SUCCESS: Eat actions were found!")