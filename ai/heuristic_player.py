"""
Heuristic AI player for Injera.

Plans the entire turn as a sequence using TurnPlanner, then executes it one
action at a time. No training required — scoring rules are in ActionEvaluator.
"""

import random
from typing import Optional

from engine.game_state import GameState, Action, ActionType
from engine.action_generator import ActionGenerator
from ai.evaluator import SPECIAL_CARD_DRAFT_PRIORITY, CARD_SYNERGIES
from ai.turn_planner import TurnPlanner


class HeuristicPlayer:
    """
    Rule-based AI that plans its full turn before acting.

    Usage:
        player = HeuristicPlayer(player_id=0)
        action = player.choose_action(game_state)
        engine.execute_action(game_state, action)
    """

    def __init__(self, player_id: int, randomness: float = 0.0, temperature: float = 0.25):
        """
        player_id   : index of the player this AI controls (0-based)
        randomness  : probability [0, 1) of picking a uniformly random legal action
                      (epsilon-greedy; useful for self-play variety)
        temperature : kept for server.py softmax display; TurnPlanner uses its own
        """
        self.player_id = player_id
        self.randomness = randomness
        self.temperature = temperature

    def choose_action(self, state: GameState) -> Optional[Action]:
        """Plan the full turn and return the first action of the best sequence."""
        legal_actions = ActionGenerator.get_legal_actions(state, self.player_id)

        if not legal_actions:
            return None

        # Draft phase: only SELECT_SPECIAL_CARDS actions exist
        if legal_actions[0].action_type == ActionType.SELECT_SPECIAL_CARDS:
            return self._choose_draft_action(legal_actions)

        # Epsilon-greedy randomness for self-play variety
        if self.randomness > 0 and random.random() < self.randomness:
            return random.choice(legal_actions)

        return TurnPlanner(self.player_id).choose_action(state)

    # ------------------------------------------------------------------
    # Draft phase
    # ------------------------------------------------------------------

    def _choose_draft_action(self, draft_actions) -> Action:
        """Keep the pair of special cards with the highest combined priority + synergy."""
        best_action = draft_actions[0]
        best_score  = float('-inf')

        for action in draft_actions:
            if not action.kept_card_ids:
                continue
            ids = action.kept_card_ids
            base     = sum(SPECIAL_CARD_DRAFT_PRIORITY.get(cid, 0) for cid in ids)
            synergy  = CARD_SYNERGIES.get(frozenset(ids), 0)
            score    = base + synergy
            if score > best_score:
                best_score  = score
                best_action = action

        return best_action

    def __repr__(self) -> str:
        return f"HeuristicPlayer(player_id={self.player_id}, randomness={self.randomness})"
