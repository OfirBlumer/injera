"""
TurnPlanner — builds a complete action sequence for an entire turn.

plan_sequence(state) returns the ordered list of all actions the AI intends
to take this turn.  The server commits to this sequence and pops one action
per request, regenerating only when the list is exhausted — which happens
naturally at every hand-refill boundary:

  Terminal conditions (sequence ends here):
    • END_TURN
    • DISCARD_REDRAW        — hand replaced with unknown cards
    • Coffee / Beer empties — engine sets force_end_turn
    • 2nd Water empties     — engine sets force_end_turn
    • 1st Water empties     — hand refilled with real cards; stop here, server replans

Pruning: only actions whose softmax probability (temperature 0.5) ≥ 5% are
expanded.  With temperature 0.5 the distribution is moderately peaked, giving
a typical branching factor of 2–3 and keeping tree size manageable.
"""

import copy
import math
import random
from typing import List, Optional, Tuple

from engine.game_state import GameState, Action, ActionType
from engine.action_generator import ActionGenerator
from engine.game_engine import GameEngine
from ai.evaluator import ActionEvaluator

TEMPERATURE     = 0.8   # Pruning temperature: broad DFS exploration
SEQ_TEMPERATURE = 0.2   # Sampling temperature: tight selection of best full sequence
PROB_THRESHOLD  = 0.05
MAX_DEPTH       = 14


# ------------------------------------------------------------------
# Semantic action matching (ignores card_index, which shifts as cards are used)
# ------------------------------------------------------------------

def actions_match(planned: Action, actual: Action) -> bool:
    """
    Return True if `planned` and `actual` represent the same logical action.

    card_index is deliberately excluded: it points into the player's hand and
    shifts every time a card is played, so a plan generated at turn-start would
    have wrong indices by the third or fourth action.
    """
    if planned.action_type != actual.action_type:
        return False
    t = planned.action_type
    if t == ActionType.EAT_DISH:
        return (planned.tile_coord            == actual.tile_coord
                and planned.resource_type         == actual.resource_type
                and planned.resource_tile_coord   == actual.resource_tile_coord
                and planned.discard_card_type     == actual.discard_card_type
                and planned.num_drink_tokens_for_hot == actual.num_drink_tokens_for_hot)
    if t == ActionType.EAT_EMPTY_TILE:
        return (planned.tile_coord        == actual.tile_coord
                and planned.discard_card_type == actual.discard_card_type)
    if t == ActionType.PLAY_DRINK:
        return planned.drink_card_type == actual.drink_card_type
    if t == ActionType.DRINK_TOKEN:
        return planned.drink_index == actual.drink_index
    if t == ActionType.ADD_TAHINI:
        return (planned.tile_coord            == actual.tile_coord
                and planned.triangle_orientation  == actual.triangle_orientation)
    if t == ActionType.ADD_AWAZE:
        return planned.tile_coord == actual.tile_coord
    if t == ActionType.PLAY_ROTATE:
        return planned.rotation_direction == actual.rotation_direction
    if t in (ActionType.END_TURN, ActionType.DISCARD_REDRAW):
        return True
    return planned == actual


# ------------------------------------------------------------------
# Planner
# ------------------------------------------------------------------

class TurnPlanner:
    """
    Plans a complete turn as a single committed sequence of actions.

    For each candidate first action (those above the softmax probability
    threshold), the DFS finds the best continuation; the full sequence score
    is the sum of all individual action scores along that path.  A first
    action is then sampled using softmax over those sequence totals, and
    the complete sequence [first_action, ...continuation] is returned.
    """

    def __init__(self, player_id: int):
        self.player_id = player_id

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def plan_sequence(self, state: GameState) -> List[Action]:
        """Return the complete ordered action sequence for this turn."""
        legal = ActionGenerator.get_legal_actions(state, self.player_id)
        if not legal:
            return []

        evaluator  = ActionEvaluator(state, self.player_id)
        candidates = self._pruned_candidates(legal, evaluator)
        if not candidates:
            return [legal[0]]

        sequence_scores: List[float]       = []
        sequences:       List[List[Action]] = []

        for first_score, first_action in candidates:
            total, seq = self._dfs(state, first_action, first_score, depth=0)
            sequence_scores.append(total)
            sequences.append(seq)

        # Softmax over full-sequence scores → sample one sequence
        max_s   = max(sequence_scores)
        weights = [math.exp((s - max_s) / SEQ_TEMPERATURE) for s in sequence_scores]
        total_w = sum(weights)
        r       = random.random() * total_w
        cumulative = 0.0
        for seq, w in zip(sequences, weights):
            cumulative += w
            if r <= cumulative:
                return seq
        return sequences[-1]

    def choose_action(self, state: GameState) -> Optional[Action]:
        """Return the first action of the planned sequence (single-step use)."""
        seq = self.plan_sequence(state)
        return seq[0] if seq else None

    # ------------------------------------------------------------------
    # Core DFS
    # ------------------------------------------------------------------

    def _dfs(
        self,
        state:       GameState,
        action:      Action,
        accumulated: float,
        depth:       int,
    ) -> Tuple[float, List[Action]]:
        """
        Find the best continuation after `action` from `state`.

        Returns (total_score, [action, ...subsequent_actions]).
        The first element of the returned list is always `action` itself.
        """
        if action.action_type in (ActionType.END_TURN, ActionType.DISCARD_REDRAW):
            return accumulated, [action]

        if depth >= MAX_DEPTH:
            return accumulated, [action]

        sim_state, turn_ended = _simulate(state, action)
        if turn_ended:
            return accumulated, [action]

        # First Water refill: hand changed with real cards we can't predict — stop here,
        # server will regenerate a fresh plan from the new state.
        pid = self.player_id
        if (not state.players[pid].water_refilled_this_turn
                and sim_state.players[pid].water_refilled_this_turn):
            return accumulated, [action]

        legal = ActionGenerator.get_legal_actions(sim_state, self.player_id)
        if not legal:
            return accumulated, [action]

        evaluator       = ActionEvaluator(sim_state, self.player_id)
        next_candidates = self._pruned_candidates(legal, evaluator)
        if not next_candidates:
            return accumulated, [action]

        best_total = float('-inf')
        best_seq   = [action]

        for next_score, next_action in next_candidates:
            total, future_seq = self._dfs(
                sim_state, next_action, accumulated + next_score, depth + 1
            )
            if total > best_total:
                best_total = total
                best_seq   = [action] + future_seq

        if best_total == float('-inf'):
            return accumulated, [action]
        return best_total, best_seq

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _pruned_candidates(
        legal:     List[Action],
        evaluator: ActionEvaluator,
    ) -> List[Tuple[float, Action]]:
        """Score all legal actions; keep those with softmax prob ≥ PROB_THRESHOLD."""
        scored  = [(evaluator.score_action(a), a) for a in legal]
        max_s   = max(s for s, _ in scored)
        weights = [math.exp((s - max_s) / TEMPERATURE) for s, _ in scored]
        total_w = sum(weights)
        result  = [
            (s, a) for (s, a), w in zip(scored, weights)
            if w / total_w >= PROB_THRESHOLD
        ]
        return result or [max(scored, key=lambda x: x[0])]



# ------------------------------------------------------------------
# State simulation
# ------------------------------------------------------------------

def _simulate(state: GameState, action: Action) -> Tuple[GameState, bool]:
    """
    Deep-copy `state`, execute `action` through a fresh GameEngine,
    return (updated_state, turn_ended).

    turn_ended is True when the engine sets force_end_turn (Coffee/Beer/2nd-Water
    glass emptied).  END_TURN and DISCARD_REDRAW are intercepted by the planner
    before this function is reached.
    """
    sim    = copy.deepcopy(state)
    engine = GameEngine(num_players=sim.num_players)
    engine.initialize_from_game_state(sim)
    engine.execute_action(sim, action)
    return sim, engine.force_end_turn
