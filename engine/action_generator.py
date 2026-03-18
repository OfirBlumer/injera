"""
Action Generator - Finds all legal actions for a player in a given game state
"""

from typing import List, Tuple, Set
from engine.game_state import GameState, Action, ActionType, TileState, PlayerState, normalize_card_name


class ActionGenerator:
    """Generates all legal actions for a player"""

    @staticmethod
    def get_legal_actions(state: GameState, player_id: int) -> List[Action]:
        """
        Get all legal actions for a player.
        Each action is a fully-specified "recipe" with no ambiguity:
        - eat actions specify discard_card_type and num_drink_tokens_for_hot
        - play_drink specifies drink_card_type (not card index)
        """
        if state.game_over:
            return []

        if state.current_player_idx != player_id:
            return []  # Not this player's turn

        player = state.players[player_id]
        actions = []

        # 1. Eat dish actions (fully enumerated sub-choices)
        actions.extend(ActionGenerator._get_eat_dish_actions(state, player))

        # 2. Eat empty tile actions (fully enumerated sub-choices)
        actions.extend(ActionGenerator._get_eat_empty_tile_actions(state, player))

        # 3. Play drink card actions (one per drink TYPE)
        actions.extend(ActionGenerator._get_play_drink_actions(state, player))

        # 4. Drink token actions
        actions.extend(ActionGenerator._get_drink_token_actions(state, player))

        # 5. Play rotate card actions
        actions.extend(ActionGenerator._get_play_rotate_actions(state, player))

        # 6. Add tahini actions (unrestricted — any tile on the board)
        actions.extend(ActionGenerator._get_add_tahini_actions(state, player))

        # 7. Add hot sauce actions (unrestricted — any tile on the board)
        actions.extend(ActionGenerator._get_add_hot_sauce_actions(state, player))

        # 8. Discard all & redraw N-1
        actions.extend(ActionGenerator._get_discard_redraw_actions(state, player))

        # 9. Special card draft (only during the draft phase)
        draft_actions = ActionGenerator._get_select_special_cards_actions(state, player)
        if draft_actions:
            return draft_actions  # Draft is the only legal action during this step

        # 10. End turn (always available)
        actions.append(Action(
            action_type=ActionType.END_TURN,
            player_id=player_id
        ))

        return actions

    @staticmethod
    def _get_neighbors(q: int, r: int) -> List[Tuple[int, int]]:
        """Get all 6 neighbor coordinates"""
        return [
            (q + 1, r),
            (q + 1, r - 1),
            (q, r - 1),
            (q - 1, r),
            (q - 1, r + 1),
            (q, r + 1)
        ]

    @staticmethod
    def _get_adjacent_eatable_empty_tiles(state: GameState, player: PlayerState, q: int, r: int) -> List[TileState]:
        """Find adjacent empty tiles that can be eaten"""
        neighbors = ActionGenerator._get_neighbors(q, r)
        eatable_empty = []
        reachable_coords = state.get_reachable_tiles(player.player_id)

        for nq, nr in neighbors:
            tile = state.get_tile(nq, nr)
            if tile and tile.empty and not tile.removed and tile.can_eat_empty:
                # Check if reachable
                if (nq, nr) in reachable_coords:
                    eatable_empty.append(tile)

        return eatable_empty

    @staticmethod
    def _get_available_discard_types(player: PlayerState, injera_committed: int) -> List[str]:
        """Get card types available for discarding after committing injera cards.

        Returns list of unique discard type strings. Drink cards are split by
        drink name ('Coffee', 'Beer', 'Water'), other cards by card_type.
        """
        # Count cards by discard-type
        counts = {}
        for c in player.hand:
            if c.card_type == 'Drink':
                key = normalize_card_name(c.name)  # 'Coffee', 'Beer', 'Water'
            else:
                key = c.card_type  # 'Clean Injera', 'Rotate', 'Tahini'
            counts[key] = counts.get(key, 0) + 1

        # Subtract committed injera
        injera_available = counts.get('Clean Injera', 0) - injera_committed
        if injera_available > 0:
            counts['Clean Injera'] = injera_available
        else:
            counts.pop('Clean Injera', None)

        return [t for t, cnt in counts.items() if cnt > 0]

    @staticmethod
    def _enumerate_eat_sub_choices(player: PlayerState, tile: TileState,
                                    resource_type: str, resource_tile_coord,
                                    total_hot: int, injera_count: int,
                                    active_drink_tokens: int,
                                    injera_committed_base: int) -> List[Action]:
        """Enumerate all (discard_card_type, num_drink_tokens_for_hot) combinations for an eat action.

        Args:
            player: Current player
            tile: Target dish tile
            resource_type: 'card' (injera) or 'tile' (empty tile)
            resource_tile_coord: Coord of adjacent empty tile (if resource_type='tile')
            total_hot: Total hot level to handle (dish hot + empty tile hot token)
            injera_count: Number of injera cards in hand
            active_drink_tokens: Total drink tokens available
            injera_committed_base: Injera already committed for the eating resource
                                   (1 if using injera card, 0 if using empty tile)
        """
        actions = []

        # For each valid num_drink_tokens_for_hot (0 to min(total_hot, active_drink_tokens))
        max_drink_tokens = min(total_hot, active_drink_tokens)

        for num_drink in range(0, max_drink_tokens + 1):
            injera_for_hot = total_hot - num_drink
            total_injera_committed = injera_committed_base + injera_for_hot

            if injera_count < total_injera_committed:
                continue  # Not enough injera

            # Get available discard types after committing injera
            available_discards = ActionGenerator._get_available_discard_types(
                player, total_injera_committed
            )

            if not available_discards:
                continue  # No card left to discard

            for discard_type in available_discards:
                actions.append(Action(
                    action_type=ActionType.EAT_DISH,
                    player_id=player.player_id,
                    tile_coord=tile.coord,
                    resource_type=resource_type,
                    resource_tile_coord=resource_tile_coord,
                    discard_card_type=discard_type,
                    num_drink_tokens_for_hot=num_drink
                ))

        return actions

    @staticmethod
    def _get_eat_dish_actions(state: GameState, player: PlayerState) -> List[Action]:
        """Get all possible eat dish actions with fully enumerated sub-choices.

        Each action specifies:
        - tile_coord: which dish to eat
        - resource_type: 'card' (injera) or 'tile' (adjacent empty tile)
        - resource_tile_coord: which empty tile (if resource_type='tile')
        - discard_card_type: which card TYPE to discard
        - num_drink_tokens_for_hot: how many drink tokens for hot handling
        """
        actions = []

        if len(player.hand) == 0:
            return actions  # Need at least 1 card to discard

        reachable_coords = state.get_reachable_tiles(player.player_id)
        injera_count = sum(1 for c in player.hand if c.card_type == 'Clean Injera')
        active_drink_tokens = sum(d.tokens for d in player.drinks if d.tokens > 0)

        for tile in state.board:
            if tile.removed or tile.empty or not tile.dish:
                continue

            # Check if reachable
            if tile.coord not in reachable_coords:
                continue

            # Hot level from the dish itself
            is_berbere = tile.dish == 'Key Sir'
            hot_dish_level = 2 if is_berbere else 1 if tile.hot else 0

            adjacent_empty = ActionGenerator._get_adjacent_eatable_empty_tiles(state, player, tile.q, tile.r)

            if injera_count == 0 and len(adjacent_empty) == 0:
                continue  # Can't eat this dish

            # Option A: Eat with injera card (resource_type='card')
            # Costs: 1 injera (for eating) + injera for hot + 1 discard card
            if injera_count > 0:
                actions.extend(ActionGenerator._enumerate_eat_sub_choices(
                    player, tile, 'card', None, hot_dish_level,
                    injera_count, active_drink_tokens, injera_committed_base=1
                ))

            # Option B: Eat with each adjacent empty tile (resource_type='tile')
            # Costs: 0 injera for eating + injera for hot + 1 discard card
            for empty_tile in adjacent_empty:
                empty_tile_hot = 0
                if empty_tile.hot_token:
                    is_berbere_token = (abs(empty_tile.q) <= 1 and abs(empty_tile.r) <= 1 and
                                      abs(empty_tile.q + empty_tile.r) <= 1)
                    empty_tile_hot = 2 if is_berbere_token else 1

                total_hot = hot_dish_level + empty_tile_hot
                actions.extend(ActionGenerator._enumerate_eat_sub_choices(
                    player, tile, 'tile', empty_tile.coord, total_hot,
                    injera_count, active_drink_tokens, injera_committed_base=0
                ))

        return actions

    @staticmethod
    def _get_eat_empty_tile_actions(state: GameState, player: PlayerState) -> List[Action]:
        """Get all possible eat empty tile actions with fully enumerated sub-choices.

        Each action specifies:
        - tile_coord: which empty tile to eat
        - discard_card_type: which card TYPE to discard
        - num_drink_tokens_for_hot: how many drink tokens for hot handling
        """
        actions = []

        if len(player.hand) == 0:
            return actions  # Need at least 1 card to discard

        reachable_coords = state.get_reachable_tiles(player.player_id)
        injera_count = sum(1 for c in player.hand if c.card_type == 'Clean Injera')
        active_drink_tokens = sum(d.tokens for d in player.drinks if d.tokens > 0)

        for tile in state.board:
            if tile.removed or not tile.empty or not tile.can_eat_empty:
                continue

            # Check if reachable
            if tile.coord not in reachable_coords:
                continue

            # Hot level from hot token on the empty tile
            hot_level = 0
            if tile.hot_token:
                is_berbere_token = (abs(tile.q) <= 1 and abs(tile.r) <= 1 and
                                  abs(tile.q + tile.r) <= 1)
                hot_level = 2 if is_berbere_token else 1

            # Enumerate (discard_card_type, num_drink_tokens_for_hot) combinations
            max_drink_tokens = min(hot_level, active_drink_tokens)

            for num_drink in range(0, max_drink_tokens + 1):
                injera_for_hot = hot_level - num_drink

                if injera_count < injera_for_hot:
                    continue  # Not enough injera for hot handling

                # Get available discard types after committing injera for hot
                available_discards = ActionGenerator._get_available_discard_types(
                    player, injera_for_hot
                )

                if not available_discards:
                    continue  # No card left to discard

                for discard_type in available_discards:
                    actions.append(Action(
                        action_type=ActionType.EAT_EMPTY_TILE,
                        player_id=player.player_id,
                        tile_coord=tile.coord,
                        discard_card_type=discard_type,
                        num_drink_tokens_for_hot=num_drink
                    ))

        return actions

    @staticmethod
    def _get_play_drink_actions(state: GameState, player: PlayerState) -> List[Action]:
        """Get all possible play drink card actions.

        One action per distinct drink TYPE (not per card index) to avoid degeneracy.
        """
        actions = []

        # Can only have one active drink at a time
        if len(player.drinks) > 0:
            return actions

        # One action per distinct drink type
        seen_types = set()
        for c in player.hand:
            if c.card_type == 'Drink':
                drink_type = normalize_card_name(c.name)
                if drink_type not in seen_types:
                    seen_types.add(drink_type)
                    actions.append(Action(
                        action_type=ActionType.PLAY_DRINK,
                        player_id=player.player_id,
                        drink_card_type=drink_type
                    ))

        return actions

    @staticmethod
    def _get_drink_token_actions(state: GameState, player: PlayerState) -> List[Action]:
        """Get all possible drink token actions"""
        actions = []

        active_drinks = [i for i, d in enumerate(player.drinks) if d.tokens > 0]

        for drink_idx in active_drinks:
            actions.append(Action(
                action_type=ActionType.DRINK_TOKEN,
                player_id=player.player_id,
                drink_index=drink_idx
            ))

        return actions

    @staticmethod
    def _get_play_rotate_actions(state: GameState, player: PlayerState) -> List[Action]:
        """Get all possible play rotate card actions"""
        actions = []

        rotate_cards = [i for i, c in enumerate(player.hand) if c.name == 'Rotate Injera']

        if len(rotate_cards) > 0:
            # Add both rotation directions (all rotate cards identical, use first index)
            actions.append(Action(
                action_type=ActionType.PLAY_ROTATE,
                player_id=player.player_id,
                card_index=rotate_cards[0],
                rotation_direction='clockwise'
            ))
            actions.append(Action(
                action_type=ActionType.PLAY_ROTATE,
                player_id=player.player_id,
                card_index=rotate_cards[0],
                rotation_direction='counterclockwise'
            ))

        return actions

    @staticmethod
    def _get_add_tahini_actions(state: GameState, player: PlayerState) -> List[Action]:
        """Get all possible add tahini actions (unrestricted — any tile on the board)"""
        actions = []
        tahini_cards = [i for i, c in enumerate(player.hand) if c.name == 'Tahini']
        if len(tahini_cards) == 0:
            return actions
        for tile in state.board:
            if tile.removed:
                continue
            for orientation in ActionGenerator._find_triangles_with_top(state, tile):
                actions.append(Action(
                    action_type=ActionType.ADD_TAHINI,
                    player_id=player.player_id,
                    card_index=tahini_cards[0],
                    tile_coord=tile.coord,
                    triangle_orientation=orientation
                ))
        return actions

    @staticmethod
    def _get_add_hot_sauce_actions(state: GameState, player: PlayerState) -> List[Action]:
        """Get all possible add hot sauce actions (unrestricted — any tile on the board)"""
        actions = []
        sauce_cards = [i for i, c in enumerate(player.hand) if c.name == 'Add Hot Sauce']
        if len(sauce_cards) == 0:
            return actions
        for tile in state.board:
            if tile.removed:
                continue
            for orientation in ActionGenerator._find_triangles_with_top(state, tile):
                actions.append(Action(
                    action_type=ActionType.ADD_HOT_SAUCE,
                    player_id=player.player_id,
                    card_index=sauce_cards[0],
                    tile_coord=tile.coord,
                    triangle_orientation=orientation
                ))
        return actions

    @staticmethod
    def _get_discard_redraw_actions(state: GameState, player: PlayerState) -> List[Action]:
        """Get discard-all-and-draw-N-1 action (available whenever hand is non-empty)"""
        if len(player.hand) == 0:
            return []
        return [Action(action_type=ActionType.DISCARD_REDRAW, player_id=player.player_id)]

    @staticmethod
    def _get_select_special_cards_actions(state: GameState, player: PlayerState) -> List[Action]:
        """Generate all legal keep-2-from-3 draft choices.

        Only active when state.draft_dealt_cards is non-empty (i.e. during a draft step).
        Generates C(N, 2) actions where N = len(state.draft_dealt_cards).
        If N <= 2 there is only one legal action (keep all dealt cards).
        """
        dealt = state.draft_dealt_cards
        if not dealt:
            return []

        from itertools import combinations
        actions = []
        for kept in combinations(dealt, min(2, len(dealt))):
            actions.append(Action(
                action_type=ActionType.SELECT_SPECIAL_CARDS,
                player_id=player.player_id,
                dealt_card_ids=list(dealt),
                kept_card_ids=list(kept),
            ))
        return actions

    @staticmethod
    def _find_triangles_with_top(state: GameState, top_tile: TileState) -> List[str]:
        """Find valid triangle orientations with this tile as the top"""
        orientations = []
        neighbors = ActionGenerator._get_neighbors(top_tile.q, top_tile.r)

        for i in range(len(neighbors)):
            for j in range(i + 1, len(neighbors)):
                n1_coord = neighbors[i]
                n2_coord = neighbors[j]

                n1 = state.get_tile(n1_coord[0], n1_coord[1])
                n2 = state.get_tile(n2_coord[0], n2_coord[1])

                if not n1 or not n2 or n1.removed or n2.removed:
                    continue

                # Check if n1 and n2 are adjacent to each other
                if n2_coord not in ActionGenerator._get_neighbors(n1_coord[0], n1_coord[1]):
                    continue

                # Sort tiles to find the topmost (smallest r)
                tiles = [(top_tile.q, top_tile.r), n1_coord, n2_coord]
                sorted_tiles = sorted(tiles, key=lambda t: (t[1], t[0]))

                if sorted_tiles[0] != (top_tile.q, top_tile.r):
                    continue  # This tile is not the top

                bottom1, bottom2 = sorted_tiles[1], sorted_tiles[2]
                avg_q = (bottom1[0] + bottom2[0]) / 2

                if avg_q < top_tile.q:
                    if 'left' not in orientations:
                        orientations.append('left')
                elif avg_q > top_tile.q:
                    if 'right' not in orientations:
                        orientations.append('right')

        return orientations
