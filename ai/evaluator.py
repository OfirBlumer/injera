"""
Action evaluator for the heuristic AI.

Scores each legal action by its expected point impact, encoding the same
reasoning a human player applies: chase completion and variety bonus thresholds,
align with special card objectives, and manage resources sensibly.
"""

from engine.game_state import GameState, Action, ActionType
from engine.action_generator import ActionGenerator

# Dish type values (from DishType enum in injera_game.py)
NON_HOT_DISHES    = {'Azifa', 'Gomen', 'Shiro'}
MEDIUM_HOT_DISHES = {'Kik Alicha', 'Misir Wot', 'Tikel Gomen'}
SUPER_HOT_DISH    = 'Key Sir'
PEAS_DISHES       = {'Shiro', 'Kik Alicha'}
LENTIL_DISHES     = {'Azifa', 'Misir Wot'}
CABBAGE_DISHES    = {'Gomen', 'Tikel Gomen'}
ALL_DISH_TYPES    = NON_HOT_DISHES | MEDIUM_HOT_DISHES | {SUPER_HOT_DISH}

# Special card name -> priority weight used during the draft phase.
# Higher = prefer to keep this card.
# Pair adjustments applied on top of individual priorities during draft selection.
# Positive = synergy (cards reinforce the same strategy).
# Negative = conflict (cards pull the player in opposite directions).
CARD_SYNERGIES: dict = {
    # Same-category food bonuses stack directly
    frozenset({'lentils_freak',  'lentils_princess'}):  +2,
    frozenset({'peas_please',    'peas_prince'}):        +2,
    frozenset({'cabbage_savage', 'cabbage_king'}):       +2,

    # Both reward hot dishes — doubled bonus per hot tile
    frozenset({'some_like_it_hot',  'too_hot_to_handle'}): +2,
    frozenset({'some_like_it_hot',  'beetroot_boss'}):     +1,
    frozenset({'too_hot_to_handle', 'beetroot_boss'}):     +1,

    # Both reward tahini collection
    frozenset({'tahini_party', 'tahini_queen'}): +2,

    # Variety + quantity bonuses complement each other
    frozenset({'tasting_menu', 'healthy_appetite'}): +1,

    # ── Conflicts ──────────────────────────────────────────────────────────
    # healthy_appetite rewards eating the MOST; consolation_prize rewards eating the FEWEST — mutually exclusive
    frozenset({'healthy_appetite', 'consolation_prize'}): -3,
    # Sesame intolerance penalises tahini; tahini cards reward it
    frozenset({'sesame_intolerance', 'tahini_queen'}): -3,
    frozenset({'sesame_intolerance', 'tahini_party'}): -3,

    # no_hot_for_you penalises hot dishes; these cards reward them
    frozenset({'no_hot_for_you', 'some_like_it_hot'}):  -3,
    frozenset({'no_hot_for_you', 'too_hot_to_handle'}): -3,
    frozenset({'no_hot_for_you', 'beetroot_boss'}):     -3,

    # picky_eater wants exactly 3 unique dish types; tasting_menu rewards 5-7
    frozenset({'picky_eater', 'tasting_menu'}): -3,

    # delicate_palate prefers cold dishes; hot-focused cards pull the other way
    frozenset({'delicate_palate', 'some_like_it_hot'}):  -1,
    frozenset({'delicate_palate', 'too_hot_to_handle'}): -1,
    frozenset({'delicate_palate', 'beetroot_boss'}):     -2,
}

SPECIAL_CARD_DRAFT_PRIORITY = {
    'healthy_appetite': 3,
    'tasting_menu':     3,
    'peas_please':      2,
    'lentils_freak':    2,
    'cabbage_savage':   2,
    'tahini_party':     2,
    'delicate_palate':  2,
    'some_like_it_hot': 2,
    'beetroot_boss':    2,
    '4x4':              1,
    'sesame_intolerance': 1,
    'tahini_queen':     1,
    'picky_eater':      1,
    'too_hot_to_handle': 1,
    'no_hot_for_you':   1,
    'peas_prince':      1,
    'lentils_princess': 1,
    'cabbage_king':     1,
    'consolation_prize': 1,
}


class ActionEvaluator:
    """
    Computes the expected point value of a legal action.

    Positive values mean the action is good; higher is better.
    END_TURN returns 0.0 and acts as the baseline.
    """

    def __init__(self, state: GameState, player_id: int):
        self.state = state
        self.player_id = player_id
        self.player = state.players[player_id]
        self.num_players = state.num_players
        self.reachable = set(map(tuple, state.get_reachable_tiles(player_id)))
        self.opponent_reachable = set()
        for pid in range(state.num_players):
            if pid != player_id:
                self.opponent_reachable.update(map(tuple, state.get_reachable_tiles(pid)))

    def score_action(self, action: Action) -> float:
        if action.action_type == ActionType.EAT_DISH:
            return self._score_eat_dish(action)
        elif action.action_type == ActionType.EAT_EMPTY_TILE:
            return self._score_eat_empty_tile(action)
        elif action.action_type == ActionType.PLAY_DRINK:
            return self._score_play_drink(action)
        elif action.action_type == ActionType.DRINK_TOKEN:
            return self._score_drink_token(action)
        elif action.action_type == ActionType.PLAY_ROTATE:
            return self._score_rotate(action)
        elif action.action_type == ActionType.ADD_TAHINI:
            return self._score_add_tahini(action)
        elif action.action_type == ActionType.ADD_AWAZE:
            return self._score_add_awaze(action)
        elif action.action_type == ActionType.DISCARD_REDRAW:
            return self._score_discard_redraw()
        elif action.action_type == ActionType.END_TURN:
            # Never end the turn while Coffee or Beer tokens are still available —
            # final round especially: this is the last chance to spend them.
            active_coffee_beer = sum(
                d.tokens for d in self.player.drinks
                if d.drink_type in ('Coffee', 'Beer') and d.tokens > 0
            )
            return -5.0 if active_coffee_beer > 0 else -0.5
        return 0.0

    # ------------------------------------------------------------------
    # EAT_DISH
    # ------------------------------------------------------------------

    def _score_eat_dish(self, action: Action) -> float:
        tile = self.state.get_tile(action.tile_coord[0], action.tile_coord[1])
        if not tile or not tile.dish:
            return 0.0

        dish = tile.dish
        player = self.player
        is_hot = tile.hot or dish == SUPER_HOT_DISH or getattr(tile, 'awaze', 0) > 0
        tile_coord = tuple(action.tile_coord)
        injera_count = sum(1 for c in player.hand if c.card_type == 'Clean Injera')

        # 1. Base dish value — awaze raises eating *cost*, not intrinsic point value
        if dish == SUPER_HOT_DISH:
            base_value = 3.0
        elif tile.hot:
            base_value = 2.0
        else:
            base_value = 1.0

        # 2. Tahini on the dish tile itself
        tahini_bonus = float(tile.tahini)

        # 3. Extra tahini from the empty tile when eating with resource_type='tile'
        #    (the engine awards those tokens to the player too)
        empty_tile_tahini = 0.0
        if action.resource_type == 'tile' and action.resource_tile_coord:
            empty_tile = self.state.get_tile(
                action.resource_tile_coord[0], action.resource_tile_coord[1]
            )
            if empty_tile:
                empty_tile_tahini = float(empty_tile.tahini)

        # 4. Completion bonus — applies to ALL dish types, +5 at 5th / 6th / 7th tile
        completion_bonus = 0.0
        current_count = player.dish_counts.get(dish, 0)
        if (current_count + 1) in (5, 6, 7):
            completion_bonus = 5.0

        # 5. Variety bonus — +5/7/9 for the 5th/6th/7th unique dish type
        variety_bonus = 0.0
        unique_types = len(set(player.eaten))
        if dish not in player.eaten:
            new_unique = unique_types + 1
            if new_unique == 5:
                variety_bonus = 5.0
            elif new_unique == 6:
                variety_bonus = 7.0
            elif new_unique == 7:
                variety_bonus = 9.0

        # 6. Forward-looking value: proximity to the next bonus threshold
        forward_value = 0.0
        for threshold in (5, 6, 7):
            if current_count == threshold - 1:
                forward_value += 2.0   # One tile away from triggering +5
                break
            elif current_count == threshold - 2:
                forward_value += 0.5   # Two tiles away
                break
        if dish not in player.eaten:
            if unique_types == 4:
                forward_value += 2.0   # Next unique type triggers +5
            elif unique_types == 5:
                forward_value += 2.5   # Next unique type triggers +7
            elif unique_types == 6:
                forward_value += 3.0   # Next unique type triggers +9

        # 7. Special card alignment
        special_value = self._special_card_alignment(dish, is_hot)

        # 8. Resource preference: eating with an empty tile saves an injera card.
        #    But if that empty tile is adjacent to OTHER reachable dishes, using it
        #    here forecloses eating those dishes this turn — penalise proportionally.
        #    Exception: if the tile has tahini, always prefer it as the resource —
        #    leaving a tahini'd tile unused gifts those points to opponents.
        if action.resource_type == 'card':
            resource_modifier = -2.5
        else:
            resource_modifier = 0.2
            if action.resource_tile_coord:
                res_coord = tuple(action.resource_tile_coord)
                target_coord = tuple(action.tile_coord)
                res_tile = self.state.get_tile(
                    action.resource_tile_coord[0], action.resource_tile_coord[1]
                )
                tahini_on_res = float(res_tile.tahini) if res_tile else 0.0
                if tahini_on_res == 0:
                    alt_uses = sum(
                        1 for t in self.state.board
                        if not t.removed and not t.empty and t.dish
                        and tuple(t.coord) in self.reachable
                        and tuple(t.coord) != target_coord
                        and self._hex_adjacent(res_coord, t.coord)
                    )
                    # Prefer exclusive tiles over shared ones, but tiles always
                    # beat cards by a wide margin: floor at 0.0.
                    resource_modifier = max(0.0, 0.2 - 0.1 * alt_uses)
                # tahini_on_res > 0: no alt_uses penalty — eat with it now

        # 9. Discard card cost: prefer discarding low-value cards
        discard_cost = self._discard_card_penalty(action.discard_card_type)

        # 10. Drink token cost (each token spent is a point foregone or resource used)
        drink_cost = -0.1 * (action.num_drink_tokens_for_hot or 0)

        # 11. True cost of handling hotness with injera cards.
        #     Each injera spent on hotness has opportunity cost ~1 pt (another dish).
        #     Stronger penalty when non-hot dishes are available as alternatives;
        #     lighter when everything reachable is hot (no choice).
        #     Also penalise wasting drink tokens that are already available.
        num_tokens_used = action.num_drink_tokens_for_hot or 0
        active_drink_tokens = sum(d.tokens for d in player.drinks if d.tokens > 0)
        hot_handling_cost = 0.0

        # Dish hotness
        dish_raw_hot = 0
        if is_hot:
            base_hot = 2 if dish == SUPER_HOT_DISH else (1 if tile.hot else 0)
            dish_raw_hot = max(0, base_hot
                               + getattr(tile, 'awaze', 0)
                               - getattr(tile, 'tahini', 0))
        # Empty tile resource hotness (its hot token adds to the total to handle)
        empty_res_raw_hot = 0
        _excess_tile_tahini = 0
        if action.resource_type == 'tile' and action.resource_tile_coord:
            _res = self.state.get_tile(
                action.resource_tile_coord[0], action.resource_tile_coord[1]
            )
            if _res and _res.hot_token:
                _berbere = (abs(_res.q) <= 1 and abs(_res.r) <= 1
                            and abs(_res.q + _res.r) <= 1)
                _raw_tile_heat = 2 if _berbere else 1
                _res_tahini = getattr(_res, 'tahini', 0)
                _tile_full_heat = _raw_tile_heat + getattr(_res, 'awaze', 0)
                empty_res_raw_hot = max(0, _tile_full_heat - _res_tahini)
                _excess_tile_tahini = max(0, _res_tahini - _tile_full_heat)
        # Cross-reduction: excess tahini from one tile cools the other's remaining heat
        _dish_full_heat = (2 if dish == SUPER_HOT_DISH else (1 if tile.hot else 0)) + getattr(tile, 'awaze', 0)
        _excess_dish_tahini = max(0, getattr(tile, 'tahini', 0) - _dish_full_heat)
        raw_hot = max(0, dish_raw_hot - _excess_tile_tahini) + max(0, empty_res_raw_hot - _excess_dish_tahini)

        if raw_hot > 0:
            injera_for_hot = max(0, raw_hot - num_tokens_used)
            wasted_tokens  = max(0, min(active_drink_tokens, raw_hot) - num_tokens_used)

            non_hot_reachable = sum(
                1 for t in self.state.board
                if not t.removed and not t.empty and t.dish
                and not t.hot and t.dish != SUPER_HOT_DISH
                and not getattr(t, 'awaze', 0)
                and t.coord in self.reachable
            )

            if injera_for_hot > 0:
                if non_hot_reachable > 0:
                    per_injera = -3.2 if dish == SUPER_HOT_DISH else -1.2
                else:
                    per_injera = -0.75 if dish == SUPER_HOT_DISH else -0.5
                hot_handling_cost += per_injera * injera_for_hot

            hot_handling_cost -= 0.4 * wasted_tokens

            # Penalty for eating a hot dish with injera when tahini in hand could reduce
            # that cost. Tahini placed afterward is useless (dish tile is gone).
            if injera_for_hot > 0:
                tahini_in_hand = sum(1 for c in player.hand if c.card_type == 'Tahini')
                remaining_room = max(0, (2 if dish == SUPER_HOT_DISH else 1) - tile.tahini)
                if tahini_in_hand > 0 and remaining_room > 0:
                    hot_handling_cost -= 0.8 * min(injera_for_hot, min(tahini_in_hand, remaining_room))

            # Key Sir with a card resource when cold dishes are available is
            # almost always wrong — save the card for easier dishes, use a
            # tile for Key Sir or wait.
            if dish == SUPER_HOT_DISH and action.resource_type == 'card' and non_hot_reachable > 0:
                hot_handling_cost -= 1.5

        # 12. Premature turn-end penalty: Coffee/Beer end the turn when their last token
        #     is used. If that happens while there are cards + resources left this turn,
        #     those potential eats are wasted. ANY card counts as a discard for eating,
        #     so wasted_eats = min(hand_cards_remaining, eating_resources_remaining).
        premature_end_penalty = 0.0
        if num_tokens_used > 0:
            active_drink = next((d for d in player.drinks if d.tokens > 0), None)
            if (active_drink
                    and active_drink.drink_type in ('Coffee', 'Beer')
                    and active_drink.tokens <= num_tokens_used):
                _injera_for_hot_here = max(0, raw_hot - num_tokens_used)
                # Total cards removed from hand by this action
                _cards_consumed = (1                                        # discard (any type)
                                   + (1 if action.resource_type == 'card' else 0)
                                   + _injera_for_hot_here)
                _hand_after = max(0, len(player.hand) - _cards_consumed)

                # Eating resources still available after this action
                _injera_after = max(0, injera_count
                                    - (1 if action.resource_type == 'card' else 0)
                                    - _injera_for_hot_here)
                _empty_after  = max(0, sum(
                    1 for t in self.state.board
                    if not t.removed and t.empty and t.can_eat_empty
                    and tuple(t.coord) in self.reachable
                ) - (1 if action.resource_type == 'tile' else 0))
                _resources_after = _injera_after + _empty_after

                _wasted_eats = min(_hand_after, _resources_after)
                if _wasted_eats > 0:
                    premature_end_penalty = -1.0 * _wasted_eats

        # 13. Contest bonus: prefer eating dishes that opponents can also reach.
        #     Exclusive dishes can wait; contested ones should be eaten first.
        contest_bonus = 0.4 if tile_coord in self.opponent_reachable else 0.0

        # 14. Reveal bonus: the dish tile becomes an empty tile after eating.
        #     More adjacent reachable dishes → more future use from the revealed tile.
        #     In 2-player games the tile is ours alone; in 5-6 player games opponents
        #     are more likely to claim it first, so the bonus shrinks (or turns negative).
        adj_reachable = sum(
            1 for t in self.state.board
            if not t.removed and not t.empty and t.dish
            and tuple(t.coord) in self.reachable
            and tuple(t.coord) != tile_coord
            and self._hex_adjacent(tile_coord, t.coord)
        )
        player_factor = (5 - self.num_players) / 4.0  # 2p→0.75, 4p→0.25, 5p→0.0, 6p→-0.25
        if adj_reachable >= 2:
            reveal_bonus = 0.5 * player_factor
        elif adj_reachable == 1:
            reveal_bonus = 0.15 * player_factor
        else:
            reveal_bonus = 0.0

        # 15. New-resource bonus: the eaten dish tile will become a playable eating
        #     resource (can_eat_empty: ≥2 external neighbors — off-board or removed).
        #     When using a tile resource it is removed after eating, counting as one
        #     extra external neighbor for the new empty tile.
        #     This distinguishes non-defensive eating (creates resource) from defensive
        #     eating (dish buried in opponent territory, no new resource formed).
        #     The bonus is scaled up strongly when a first-glass water refill is pending,
        #     because the incoming cards make the new resource much more exploitable.
        new_resource_bonus = 0.0
        _board_map = {tuple(t.coord): t for t in self.state.board}
        _res_coord = (tuple(action.resource_tile_coord)
                      if action.resource_type == 'tile' and action.resource_tile_coord
                      else None)
        _ext = 0
        for _dq, _dr in ((1,0),(-1,0),(0,1),(0,-1),(1,-1),(-1,1)):
            _nc = (tile_coord[0]+_dq, tile_coord[1]+_dr)
            if _nc == _res_coord:
                _ext += 1  # resource tile will be removed after eating
            elif _nc not in _board_map or _board_map[_nc].removed:
                _ext += 1
        if _ext >= 2:
            _water_pending = (
                any(d.drink_type == 'Water' and d.tokens > 0 for d in player.drinks)
                and not player.water_refilled_this_turn
            )
            if _water_pending:
                new_resource_bonus = 0.6
            else:
                # Base penalty scales with player count (more opponents = worse to gift a tile).
                # Hand-size lift: more cards in hand means more eating left this turn,
                # so the new tile is more likely to be used by you before opponents get it.
                # Neutral point is 3p; 4p+ are all defensive to varying degrees.
                # 6p, hand=3: -0.75 + 0.12 = -0.63  → very defensive
                # 5p, hand=3: -0.50 + 0.12 = -0.38  → defensive
                # 4p, hand=3: -0.25 + 0.12 = -0.13  → mildly defensive
                # 3p, hand=3: +0.00 + 0.12 = +0.12  → neutral
                # 2p, hand=3: +0.25 + 0.12 = +0.37  → non-defensive preferred
                _nr_factor = (3 - self.num_players) / 4.0
                new_resource_bonus = 1.0 * _nr_factor + 0.04 * len(player.hand)

        score = (base_value + tahini_bonus + empty_tile_tahini
                 + completion_bonus + variety_bonus + forward_value
                 + resource_modifier + discard_cost
                 + drink_cost + hot_handling_cost + premature_end_penalty
                 + contest_bonus + reveal_bonus + new_resource_bonus)
        # The floor keeps eating above END_TURN (0.0) even with heavy penalties.
        # Negative special effects (picky_eater −5, no_hot_for_you −2) push toward it.
        # Positive special effects (lentils_princess +0.7, healthy_appetite +0.4) must
        # survive above the floor so they can differentiate between dish choices.
        return max(score + min(0.0, special_value), 0.05) + max(0.0, special_value)

    def _discard_card_penalty(self, discard_type: str) -> float:
        """Opportunity cost of losing this card type from hand when eating.

        Preferred discard order (least painful → most painful):
          Awaze ≈ free  >  Rotate (when not urgent)  >  Clean Injera
          >  Water (cold board)  >  Tahini  >  Water (hot board)
          >  Rotate (urgently needed)  >  Coffee / Beer
        """
        if not discard_type:
            return 0.0

        player = self.player

        if discard_type in ('Awaze', 'Add Awaze'):
            # Almost always the right card to throw away — no useful future action
            return 0.0

        elif discard_type == 'Rotate':
            # Early game: rotation is nearly useless, so discard freely
            total_eaten = sum(len(p.eaten) for p in self.state.players)
            if total_eaten < self.num_players * 3:
                return -0.1
            # Later: only cheap to discard when there are still plenty of non-hot tiles
            non_hot_reachable = sum(
                1 for t in self.state.board
                if not t.removed and not t.empty
                and t.dish in NON_HOT_DISHES
                and t.coord in self.reachable
            )
            return -0.4 if non_hot_reachable < 3 else -0.1

        elif discard_type == 'Clean Injera':
            injera_count = sum(1 for c in player.hand if c.card_type == 'Clean Injera')
            return -0.05 * max(1, 5 - injera_count)

        elif discard_type == 'Tahini':
            return -0.4

        elif discard_type in ('Coffee', 'Beer'):
            return -0.5

        elif discard_type == 'Water':
            hot_reachable = sum(
                1 for t in self.state.board
                if not t.removed and not t.empty
                and (t.hot or t.dish == SUPER_HOT_DISH or getattr(t, 'awaze', 0) > 0)
                and t.coord in self.reachable
            )
            return -0.4 if hot_reachable > 0 else -0.1

        return -0.2

    def _special_card_alignment(self, dish: str, is_hot: bool) -> float:
        bonus = 0.0
        player = self.player

        for card_id in player.special_cards:
            if card_id == 0:   # 4x4
                count = player.dish_counts.get(dish, 0)
                if count == 3:    # Eating brings it to 4 — the sweet spot
                    bonus += 3.0
                # No penalty for eating the 5th: the completion bonus (+5) exceeds
                # what the 4x4 card rewards for exactly 4, so eating on is correct.

            elif card_id == 4:   # tasting_menu: bonus stacks on variety bonus
                unique = len(set(player.eaten))
                if dish not in player.eaten and unique in (4, 5, 6):
                    bonus += 1.5

            elif card_id == 5:   # picky_eater: +15 for exactly 3 unique dish types
                unique = len(set(player.eaten))
                if dish not in player.eaten and unique >= 3:
                    bonus -= 5.0  # Gaining a 4th type destroys this card

            elif card_id == 6:   # some_like_it_hot
                if is_hot:
                    bonus += 0.5

            elif card_id == 7:   # too_hot_to_handle
                if is_hot:
                    bonus += 0.5

            elif card_id == 8:   # beetroot_boss: +2 per Key Sir
                if dish == SUPER_HOT_DISH:
                    bonus += 2.0

            elif card_id == 9:   # no_hot_for_you
                if is_hot:
                    bonus -= 2.0

            elif card_id == 10:  # peas_please
                if dish in PEAS_DISHES:
                    bonus += 1.0

            elif card_id == 11:  # peas_prince
                if dish in PEAS_DISHES:
                    bonus += 0.7

            elif card_id == 12:  # lentils_freak
                if dish in LENTIL_DISHES:
                    bonus += 1.0

            elif card_id == 13:  # lentils_princess
                if dish in LENTIL_DISHES:
                    bonus += 0.7

            elif card_id == 14:  # cabbage_savage
                if dish in CABBAGE_DISHES:
                    bonus += 1.0

            elif card_id == 15:  # cabbage_king
                if dish in CABBAGE_DISHES:
                    bonus += 0.7

            elif card_id == 16:  # healthy_appetite
                bonus += 0.4

            elif card_id == 17:  # consolation_prize
                bonus -= 0.3

            elif card_id == 18:  # delicate_palate
                if not is_hot:
                    bonus += 0.5

        return bonus

    # ------------------------------------------------------------------
    # EAT_EMPTY_TILE
    # ------------------------------------------------------------------

    def _score_eat_empty_tile(self, action: Action) -> float:
        tile = self.state.get_tile(action.tile_coord[0], action.tile_coord[1])
        if not tile:
            return 0.0
        discard_cost = self._discard_card_penalty(action.discard_card_type)
        tahini = float(tile.tahini)

        if tahini > 0:
            return tahini + discard_cost

        # 0-tahini tile: only worth eating in two specific situations.
        tile_coord = tuple(tile.coord)

        # Situation 1: eating this tile creates a free vertex that enables an adjacent
        # tahini-bearing empty tile (currently can_eat_empty=False) to become a valid
        # eating resource. Unlocking a tahini tile is worth a card + discard.
        enables_tahini = any(
            not t.removed and t.empty and float(t.tahini) > 0
            and not t.can_eat_empty
            and self._hex_adjacent(tile_coord, tuple(t.coord))
            for t in self.state.board
        )
        if enables_tahini:
            return 0.5 + discard_cost

        # Situation 2: defensive denial — this tile is adjacent to dishes outside the
        # player's reachable set (opponent territory). The player has no resource for
        # those dishes anyway, so eating the tile denies opponents a free eating resource.
        best_opponent_dish = 0.0
        for t in self.state.board:
            if (not t.removed and not t.empty and t.dish
                    and tuple(t.coord) not in self.reachable
                    and self._hex_adjacent(tile_coord, tuple(t.coord))):
                if t.dish == SUPER_HOT_DISH:
                    dv = 3.0
                elif t.hot or t.dish in MEDIUM_HOT_DISHES or getattr(t, 'awaze', 0) > 0:
                    dv = 2.0
                else:
                    dv = 1.0
                best_opponent_dish = max(best_opponent_dish, dv)

        if best_opponent_dish > 0:
            # If the player has water tokens on the first glass (finishing it refills hand),
            # skip defensive play — the incoming refill will provide better eating options.
            # Must be strictly worse than the "no strategic reason" fallback (-0.3).
            has_water_tokens = any(
                d.drink_type == 'Water' and d.tokens > 0
                for d in self.player.drinks
            )
            if has_water_tokens and not self.player.water_refilled_this_turn:
                return -0.3 + discard_cost

            # Small defensive value, proportional to what the opponent stands to gain.
            # Scale down when the player has cards in hand — each card is better spent
            # on actual eating than blocking, so defensiveness only makes sense when
            # the hand is nearly empty.
            # Cards consumed: 1 discard + any injera spent on hot handling.
            tile = self.state.get_tile(action.tile_coord[0], action.tile_coord[1])
            if tile:
                raw_hot = 0
                if tile.hot_token:
                    is_berbere = (abs(tile.q) <= 1 and abs(tile.r) <= 1
                                  and abs(tile.q + tile.r) <= 1)
                    raw_hot = 2 if is_berbere else 1
                hot_level = max(0, raw_hot + getattr(tile, 'awaze', 0) - getattr(tile, 'tahini', 0))
                injera_for_hot = max(0, hot_level - (action.num_drink_tokens_for_hot or 0))
            else:
                injera_for_hot = 0
            hand_after = max(0, len(self.player.hand) - 1 - injera_for_hot)
            base_defensive = 0.15 * best_opponent_dish - 0.1
            defensive_value = base_defensive - 0.1 * hand_after
            return defensive_value + discard_cost

        # No strategic reason — eat only as absolute last resort.
        return -0.3 + discard_cost

    # ------------------------------------------------------------------
    # PLAY_DRINK
    # ------------------------------------------------------------------

    def _score_play_drink(self, action: Action) -> float:
        hot_reachable = sum(
            1 for t in self.state.board
            if not t.removed and not t.empty
            and (t.hot or t.dish == SUPER_HOT_DISH or getattr(t, 'awaze', 0) > 0)
            and t.coord in self.reachable
        )
        hot_factor = min(hot_reachable, 5) / 5.0  # 0.0 – 1.0

        total_eaten = sum(len(p.eaten) for p in self.state.players)
        game_progress = min(1.0, total_eaten / (self.num_players * 8))

        active_tokens = sum(d.tokens for d in self.player.drinks if d.tokens > 0)
        token_scarcity = max(0.0, 1.0 - active_tokens / 4.0)

        # Forward value from hot dishes near completion/variety thresholds.
        # Ordering any drink enables cheaper hotness handling, making bonuses easier to reach.
        unique_eaten = set(self.player.eaten)
        n_unique     = len(unique_eaten)
        hot_bonus_forward = 0.0
        for t in self.state.board:
            if t.removed or t.empty or not t.dish:
                continue
            if not (t.hot or t.dish == SUPER_HOT_DISH or getattr(t, 'awaze', 0) > 0):
                continue
            if t.coord not in self.reachable:
                continue
            dish  = t.dish
            count = self.player.dish_counts.get(dish, 0)
            for threshold in (5, 6, 7):
                if count == threshold - 1:
                    hot_bonus_forward += 3.0   # one eat from completion bonus
                    break
                elif count == threshold - 2:
                    hot_bonus_forward += 0.8
                    break
            if dish not in unique_eaten:
                if   n_unique == 4: hot_bonus_forward += 2.0
                elif n_unique == 5: hot_bonus_forward += 3.0
                elif n_unique == 6: hot_bonus_forward += 4.0
        # Scale by token scarcity — no forward value if tokens already available
        hot_bonus_forward = min(hot_bonus_forward, 6.0) * token_scarcity

        # Hot injera saving: tokens prevent burning injera cards on hot handling.
        # For each reachable hot dish, any hot level not yet covered by existing tokens
        # would cost an injera card without this drink (~0.8 eating value per card).
        # This captures value even when no dish is near a threshold.
        hot_injera_saving = 0.0
        if token_scarcity > 0:
            for _t in self.state.board:
                if _t.removed or _t.empty or not _t.dish:
                    continue
                if not (_t.hot or _t.dish == SUPER_HOT_DISH or getattr(_t, 'awaze', 0) > 0):
                    continue
                if tuple(_t.coord) not in self.reachable:
                    continue
                _raw = 2 if _t.dish == SUPER_HOT_DISH else 1
                _raw = max(0, _raw + getattr(_t, 'awaze', 0) - getattr(_t, 'tahini', 0))
                if _raw > 0:
                    hot_injera_saving += max(0, _raw - active_tokens) * 0.8
            hot_injera_saving = min(hot_injera_saving, 2.5)

        if action.drink_card_type == 'Water':
            if self.player.water_refilled_this_turn:
                # Second glass: still gives tokens for hotness, finishing it ends the turn.
                # Prefer coffee/beer if available, but still a solid play.
                return 4.0 + hot_bonus_forward * 0.6 + hot_injera_saving * 0.5
            return 6.0 + hot_bonus_forward + hot_injera_saving

        final_round = self.state.final_round_active

        if action.drink_card_type == 'Coffee':
            if final_round:
                # +3 pts finish; extra card is irrelevant — solid but beer beats it.
                return 5.0 + hot_bonus_forward * 0.8 + hot_injera_saving * 0.6
            base = 4.5 + 0.5 * hot_factor * token_scarcity
            return base + hot_bonus_forward + hot_injera_saving * 0.6

        elif action.drink_card_type == 'Beer':
            if final_round:
                # +6 pts finish; no next-refill penalty — best drink to order and drain.
                return 6.5 + hot_bonus_forward + hot_injera_saving * 0.6
            beer_base = 2.5 + 1.5 * game_progress  # 2.5 early → 4.0 late
            base = beer_base + 0.5 * hot_factor
            return base + hot_bonus_forward * 0.8 + hot_injera_saving * 0.6

        return 0.0

    # ------------------------------------------------------------------
    # DRINK_TOKEN
    # ------------------------------------------------------------------

    def _score_drink_token(self, action: Action) -> float:
        idx = action.drink_index
        if idx is None or idx >= len(self.player.drinks):
            return 0.0
        drink = self.player.drinks[idx]
        dt = drink.drink_type

        is_last = drink.tokens == 1

        # If the player holds a drink card they'll want to play next turn, drinking
        # tokens now has forward value (progress toward finish bonus + makes room).
        has_drink_card = any(c.card_type == 'Drink' for c in self.player.hand)
        final_round    = self.state.final_round_active

        if dt == 'Beer':
            if is_last:
                if final_round:
                    # Final round: +6 pts, no next refill to penalise — best drink to finish.
                    return 2.5
                # Mid-game: +6 pts but costs 1 card next refill (pendingBeerPenalty).
                # Card loss outweighs point gain vs coffee — score below coffee-last.
                return 0.3
            # Non-last: penalty to defer until after eating, relaxed when a drink
            # card is in hand (making progress toward the bonus has forward value).
            return 0.1 if has_drink_card else -0.3

        elif dt == 'Coffee':
            if is_last:
                if final_round:
                    # Final round: +3 pts, extra card bonus irrelevant — less than beer.
                    return 1.2
                # Mid-game: +3 pts AND refills hand to maxHandSize+1 (extra card).
                # Extra card enables more eating next turn — better than beer mid-game.
                return 0.6
            return 0.05 if has_drink_card else -0.2
        elif dt == 'Water':
            # Use only the per-turn flag — NOT the drinks-list index, which would
            # falsely flag glasses carried over from previous turns.
            if self.player.water_refilled_this_turn:
                # Second glass: voluntarily spending any token is always wrong.
                # Tokens are only worth spending when needed for hot handling (not here).
                # Last token also ends the turn. Both cases: heavy penalty.
                return -2.0
            else:
                # Working on first glass. Last token refills hand and turn continues —
                # genuinely valuable; reward it slightly above a normal token spend.
                return 0.5 if is_last else 0.25
        return -0.2

    # ------------------------------------------------------------------
    # PLAY_ROTATE
    # ------------------------------------------------------------------

    def _score_rotate(self, action: Action) -> float:
        # Early game: board is near-symmetric, rotation gives almost no benefit
        # and wastes a card. Gate it until each player has eaten ~3 dishes on average.
        total_eaten = sum(len(p.eaten) for p in self.state.players)
        if total_eaten < self.num_players * 3:
            return -0.8  # Below END_TURN: essentially never rotate early

        player = self.player
        unique_eaten = set(player.eaten)
        is_cw = action.rotation_direction == 'clockwise'

        gained = 0.0
        lost   = 0.0

        for t in self.state.board:
            if t.removed or t.empty or not t.dish:
                continue
            q, r = t.coord[0], t.coord[1]
            new_coord = (-r, q + r) if is_cw else (q + r, -q)

            was_reachable  = tuple(t.coord) in self.reachable
            will_reachable = new_coord in self.reachable

            if not was_reachable and will_reachable:
                gained += self._tile_access_value(t, player, unique_eaten)
            elif was_reachable and not will_reachable:
                lost += self._tile_access_value(t, player, unique_eaten)

        net = gained - lost
        # ~35% utilization (you won't eat every newly reachable tile) minus card cost
        return net * 0.35 - 0.6

    # ------------------------------------------------------------------
    # ADD_TAHINI
    # ------------------------------------------------------------------

    def _get_triangle_tiles(self, tile_coord, orientation):
        """Return the list of TileState objects forming the triangle (1–3 tiles)."""
        top_q, top_r = tile_coord
        neighbors = ActionGenerator._get_neighbors(top_q, top_r)
        for i, n1_coord in enumerate(neighbors):
            n1 = self.state.get_tile(n1_coord[0], n1_coord[1])
            if not n1 or n1.removed:
                continue
            for n2_coord in neighbors[i + 1:]:
                n2 = self.state.get_tile(n2_coord[0], n2_coord[1])
                if not n2 or n2.removed:
                    continue
                if n2_coord not in ActionGenerator._get_neighbors(n1_coord[0], n1_coord[1]):
                    continue
                all_coords = sorted(
                    [(top_q, top_r), n1_coord, n2_coord], key=lambda t: (t[1], t[0])
                )
                if all_coords[0] != (top_q, top_r):
                    continue
                b1, b2 = all_coords[1], all_coords[2]
                tri_orient = 'left' if (b1[0] + b2[0]) / 2 < top_q else 'right'
                if tri_orient == orientation:
                    top_tile = self.state.get_tile(top_q, top_r)
                    return [t for t in [top_tile, n1, n2] if t]
        top_tile = self.state.get_tile(top_q, top_r)
        return [top_tile] if top_tile else []

    def _score_add_tahini(self, action: Action) -> float:
        tile = self.state.get_tile(action.tile_coord[0], action.tile_coord[1])
        if not tile or tile.removed:
            return 0.0

        player = self.player
        injera_count = sum(1 for c in player.hand if c.card_type == 'Clean Injera')
        empty_tile_resources = sum(
            1 for t in self.state.board
            if not t.removed and t.empty and t.can_eat_empty
            and t.coord in self.reachable
        )
        effective_resources = injera_count + empty_tile_resources
        # Placing tahini costs 1 tahini card; each subsequent eat requires ≥1 card to
        # discard.  If the player's remaining hand (after this action) can't support any
        # eating action, effective_resources must be 0 regardless of empty-tile count.
        effective_resources = min(effective_resources, max(0, len(player.hand) - 1))
        tile_coord = tuple(tile.coord)

        total_eaten = sum(len(p.eaten) for p in self.state.players)
        game_progress = min(1.0, total_eaten / (self.num_players * 8))

        if effective_resources == 0:
            if tile_coord not in self.opponent_reachable:
                return 0.8
            return -1.0

        # Score all 3 triangle tiles individually, then sum.
        triangle = self._get_triangle_tiles(
            (action.tile_coord[0], action.tile_coord[1]), action.triangle_orientation
        )

        active_drink_tokens = sum(d.tokens for d in player.drinks if d.tokens > 0)
        has_drink = active_drink_tokens > 0

        total = 0.0
        for t in triangle:
            tc = tuple(t.coord)
            reachable_by_us  = tc in self.reachable
            reachable_by_opp = tc in self.opponent_reachable

            if t.empty and t.can_eat_empty and reachable_by_us:
                # Guaranteed tahini point: we'll consume this tile as a resource this turn.
                total += 1.2

            elif not t.dish or t.empty:
                # No dish and not a usable empty tile — tahini is wasted here.
                total += 0.0

            elif reachable_by_us:
                is_hot   = t.hot or t.dish == SUPER_HOT_DISH or getattr(t, 'awaze', 0) > 0
                is_super = t.dish == SUPER_HOT_DISH
                # Check if an adjacent empty tile exists that we could eat this dish with
                has_adj_empty = any(
                    not adj.removed and adj.empty and adj.can_eat_empty
                    and tuple(adj.coord) in self.reachable
                    and self._hex_adjacent(tc, tuple(adj.coord))
                    for adj in self.state.board
                )
                if not is_hot:
                    tile_score = 1.5 if has_adj_empty else 0.9
                elif not is_super:
                    # Tahini eliminates medium-hot cost entirely — big forward value.
                    tile_score = 2.2 if has_adj_empty else 1.8
                    # Second tahini on a hot dish can cool an adjacent hot empty tile too.
                    # The extra token covers the empty tile's heat, saving a drink card.
                    if t.tahini >= 1:
                        has_hot_adj_empty = any(
                            not adj.removed and adj.empty and adj.hot_token
                            and tuple(adj.coord) in self.reachable
                            and self._hex_adjacent(tc, tuple(adj.coord))
                            for adj in self.state.board
                        )
                        if has_hot_adj_empty:
                            tile_score += 0.8
                else:
                    # Key Sir: tahini reduces to 1 — still expensive.
                    if has_adj_empty and has_drink:
                        tile_score = 1.1
                    elif has_adj_empty:
                        tile_score = 0.6
                    elif has_drink:
                        tile_score = 0.4
                    else:
                        tile_score = 0.1

                # Forward value when this dish is near a completion/variety bonus.
                # Placing tahini now enables cheaper eating for the bonus-triggering eat,
                # so the placement has more value than just hotness reduction.
                if is_hot and t.tahini < (2 if is_super else 1):
                    t_count = player.dish_counts.get(t.dish, 0)
                    for threshold in (5, 6, 7):
                        if t_count == threshold - 1:
                            tile_score += 3.0
                            break
                        elif t_count == threshold - 2:
                            tile_score += 0.8
                            break
                    unique_eaten = set(player.eaten)
                    if t.dish not in unique_eaten:
                        n_uniq = len(unique_eaten)
                        if   n_uniq == 4: tile_score += 1.5
                        elif n_uniq == 5: tile_score += 2.0
                        elif n_uniq == 6: tile_score += 2.5

                # Gift penalty if opponents can also reach this tile.
                # Each extra opponent gets a full turn before the player returns,
                # so the theft risk scales with opponent count.
                if reachable_by_opp:
                    tile_score -= 0.2 * (self.num_players - 1)
                total += tile_score

            else:
                # We can't reach this tile — it's a pure gift to opponents.
                total += -0.3 * (self.num_players - 1) if reachable_by_opp else 0.0

        tahini_cards = sum(1 for c in player.hand if c.card_type == 'Tahini')
        excess = tahini_cards - effective_resources
        if excess > 0:
            is_exclusive = tile_coord not in self.opponent_reachable
            if is_exclusive:
                # Safe to place for next turn — small reward for securing territory.
                existing = min(float(tile.tahini), 2)
                total += 0.3 + 0.1 * existing
            else:
                # Contested tile we can't eat this turn: opponents eat it and collect
                # our tahini bonus. Scale with game progress and opponent count.
                progress_multiplier = 1.0 + 0.5 * game_progress  # 1.0 early → 1.5 late
                total -= 1.5 * progress_multiplier * (self.num_players - 1)
                contested_triangle = sum(
                    1 for t in triangle
                    if tuple(t.coord) in self.opponent_reachable
                    and tuple(t.coord) not in self.reachable
                )
                if contested_triangle >= 2:
                    total -= 1.0 * (self.num_players - 1)

        # Single-card multi-player risk: if this is the player's only tahini card,
        # the tile is contested, and the player has no resources to eat it THIS turn
        # (excess >= 0 means the card would sit until next turn at best), the expected
        # value is low — N-1 opponents each get a shot at it before the player returns.
        if (tahini_cards == 1
                and tile_coord in self.opponent_reachable
                and effective_resources == 0):
            total -= 0.4 * (self.num_players - 1)

        return total

    # ------------------------------------------------------------------
    # ADD_AWAZE
    # ------------------------------------------------------------------

    def _score_add_awaze(self, action: Action) -> float:
        tile = self.state.get_tile(action.tile_coord[0], action.tile_coord[1])
        if not tile or tile.removed:
            return -0.5

        # Awaze on an empty tile is wasted — it only affects eat cost for dish tiles
        if tile.empty or not tile.dish:
            return -1.0

        tile_coord = tuple(tile.coord)
        in_self     = tile_coord in self.reachable
        in_opponent = tile_coord in self.opponent_reachable

        if in_self:
            # Adding awaze to a dish we can reach makes it more expensive for us
            return -1.5

        if in_opponent:
            # Pure opponent territory: forces them to spend an extra injera (or drink token).
            # More disruptive on cold dishes (jumped from free to costly) than already-hot ones.
            if tile.hot or tile.dish == SUPER_HOT_DISH:
                return 0.4   # Already hot — adds one more burden
            else:
                return 0.6   # Cold dish turned hot — most impactful harassment

        # Tile is reachable by nobody: playing a card here is wasted.
        return -0.8

    # ------------------------------------------------------------------
    # DISCARD_REDRAW
    # ------------------------------------------------------------------

    def _score_discard_redraw(self) -> float:
        player = self.player
        hand_size = len(player.hand)
        injera_count = sum(1 for c in player.hand if c.card_type == 'Clean Injera')
        active_drink_tokens = sum(d.tokens for d in player.drinks if d.tokens > 0)
        drink_cards_in_hand = sum(1 for c in player.hand if c.card_type == 'Drink')

        # Final round: no dishes remain — injera cards and empty tiles are useless
        # for eating. Only drink tokens, drink cards, and tahini still score.
        dishes_remain = any(
            not t.removed and not t.empty and t.dish
            for t in self.state.board
        )
        if not dishes_remain:
            tahini_cards = sum(1 for c in player.hand if c.card_type == 'Tahini')
            reachable_empty = sum(
                1 for t in self.state.board
                if not t.removed and t.empty and t.can_eat_empty
                and tuple(t.coord) in self.reachable
            )
            can_place_tahini = tahini_cards > 0 and reachable_empty > 0
            # Eating a tahini-bearing empty tile scores points — counts as useful
            tahini_on_reachable_empty = any(
                not t.removed and t.empty and t.can_eat_empty
                and float(t.tahini) > 0
                and tuple(t.coord) in self.reachable
                for t in self.state.board
            )
            has_useful_action = (active_drink_tokens > 0 or drink_cards_in_hand > 0
                                 or can_place_tahini or tahini_on_reachable_empty)
            if not has_useful_action:
                # d&r is the only path to scoring (draw Coffee/Beer).
                # With 1 card: d&r and end_turn both give a full hand next turn — neutral.
                # With 2+ cards: d&r replaces N useless cards; strictly better than end_turn.
                if hand_size > 1:
                    return 3.0
                return 0.0
            return -0.6      # Still have useful actions; don't waste the hand

        hot_reachable = sum(
            1 for t in self.state.board
            if not t.removed and not t.empty
            and (t.hot or t.dish == SUPER_HOT_DISH or getattr(t, 'awaze', 0) > 0)
            and t.coord in self.reachable
        )

        # Penalty for discarding drink cards needed for nearby hot dishes.
        drink_penalty = -0.5 if (drink_cards_in_hand > 0 and hot_reachable > 0) else 0.0

        # Empty tiles are valid eating resources — count them alongside injera.
        empty_tile_resources = sum(
            1 for t in self.state.board
            if not t.removed and t.empty and t.can_eat_empty
            and t.coord in self.reachable
        )
        effective_resources = injera_count + empty_tile_resources

        total_eaten = sum(len(p.eaten) for p in self.state.players)
        game_progress = min(1.0, total_eaten / (self.num_players * 8))

        # Check whether any reachable dish can actually be eaten with the current hand.
        # A player may have resources (injera, empty tiles) but still be unable to eat if
        # all reachable dishes are hot and the combined eating + hotness cost exceeds
        # what's available (e.g. 1 injera + 2 rotates, all dishes hot level 1).
        actually_eatable = False
        for _t in self.state.board:
            if _t.removed or _t.empty or not _t.dish or tuple(_t.coord) not in self.reachable:
                continue
            _base_hot = 2 if _t.dish == SUPER_HOT_DISH else 1 if _t.hot else 0
            _dish_hot = max(0, _base_hot + getattr(_t, 'awaze', 0) - getattr(_t, 'tahini', 0))
            _hot_need = max(0, _dish_hot - active_drink_tokens)
            # Eating with injera card: 1 injera (eat) + _hot_need injera (hot)
            if injera_count >= 1 + _hot_need:
                actually_eatable = True
                break
            # Eating with adjacent empty tile: tile must be adjacent to this dish
            if empty_tile_resources > 0 and injera_count >= _hot_need:
                _t_coord = tuple(_t.coord)
                if any(
                    not adj.removed and adj.empty and adj.can_eat_empty
                    and tuple(adj.coord) in self.reachable
                    and self._hex_adjacent(tuple(adj.coord), _t_coord)
                    for adj in self.state.board
                ):
                    actually_eatable = True
                    break

        can_eat_at_all = (effective_resources > 0 or active_drink_tokens > 0) and actually_eatable
        # EAT_EMPTY_TILE on a tahini tile scores real points; any card suffices as discard.
        # Without this, d&r gets an inflated "stuck" bonus that incorrectly beats eating.
        if not can_eat_at_all and player.hand:
            can_eat_at_all = any(
                not t.removed and t.empty and t.can_eat_empty
                and float(t.tahini) > 0
                and tuple(t.coord) in self.reachable
                for t in self.state.board
            )
        if not can_eat_at_all:
            # Scale down the "stuck" bonus when cards remain in hand: each card is a
            # resource that could have been used with a smarter eating order this turn.
            score = max(0.5, 2.0 - 0.4 * hand_size) + drink_penalty
        elif effective_resources == 0:
            score = 1.0 + drink_penalty   # Only drink tokens, no tile/injera resource
        elif effective_resources == 1:
            score = 0.1 + drink_penalty   # Down to last resource — worth refreshing
        else:
            # 2+ eating resources: hand is functional, redrawing wastes good cards.
            score = -0.6 + drink_penalty

        # General defensiveness penalty: only applies when eating was actually possible —
        # holding cards isn't "squandering opportunities" if there are none to take.
        if actually_eatable:
            score -= 0.25 * hand_size

        # Late game: cards that can't be played this turn are increasingly costly to hold.
        # Boost D&R when the hand contains near-useless cards (Rotate, Awaze) or
        # simply more cards than eating opportunities.
        if game_progress >= 0.65 and hand_size >= 2:
            useful_cards = injera_count + drink_cards_in_hand
            excess_cards = max(0, hand_size - useful_cards - active_drink_tokens)
            # Rotate and Awaze are almost worthless at late game — treat each as an
            # extra excess card regardless of the overall excess count.
            dead_cards = sum(
                1 for c in player.hand
                if c.card_type in ('Rotate', 'Add Awaze', 'Awaze')
            )
            effective_excess = excess_cards + dead_cards
            if effective_excess >= 1:
                # Higher per-card coefficient when specifically holding dead cards.
                boost_coeff = 1.0 if dead_cards > 0 else 0.5
                late_boost = min(2.0, boost_coeff * effective_excess) * ((game_progress - 0.65) / 0.35)
                score += late_boost

        # D&R with 0 or 1 card draws 0 new cards — strictly no better than END_TURN.
        if hand_size <= 1:
            return min(score, -0.5)

        return score

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _tile_access_value(tile, player, unique_eaten: set) -> float:
        """How much is it worth to gain (or lose) access to this tile?"""
        dish  = tile.dish
        count = player.dish_counts.get(dish, 0)
        is_hot = tile.hot or dish == SUPER_HOT_DISH or getattr(tile, 'awaze', 0) > 0

        # Hot tiles are harder to eat so less valuable to merely reach
        base = 0.2 if is_hot else 0.6

        # Completion bonus proximity (+5 at 5th tile of a type)
        if count >= 4:
            base += 3.0
        elif count == 3:
            base += 1.5
        elif count == 2:
            base += 0.5

        # Variety bonus proximity
        if dish not in unique_eaten:
            n = len(unique_eaten)
            if n >= 6:
                base += 3.0
            elif n >= 5:
                base += 2.0
            elif n >= 4:
                base += 1.5
            else:
                base += 0.3

        # Tahini already on tile
        base += float(tile.tahini) * 0.5

        return base

    # ------------------------------------------------------------------
    # Geometry
    # ------------------------------------------------------------------

    @staticmethod
    def _hex_adjacent(c1, c2) -> bool:
        q1, r1 = c1[0], c1[1]
        q2, r2 = c2[0], c2[1]
        return max(abs(q2-q1), abs(r2-r1), abs((q2+r2)-(q1+r1))) == 1
