"""
Game Engine - Full game simulation for neural AI training
Uses actual game classes from injera_game.py to run real games.
Converts between internal objects and GameState format for ActionGenerator/AI.
"""

import sys
from pathlib import Path
from typing import List, Optional, Tuple, Dict
import random

# Add parent directory to find injera_game module
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from injera_game import (
    Board, HexCoord, HexTile, DishType, CardType, DrinkType,
    Deck, Card, InjeraCard, DrinkCard, TahiniCard, RotateCard, HotSauceCard,
    Player, ActiveDrink
)
from .game_state import (
    GameState, TileState, PlayerState, CardState, DrinkState, DeckState,
    Action, ActionType
)


class GameEngine:
    """Full game engine using real game objects for neural AI training"""

    NUM_SPECIAL_CARDS = 18

    def __init__(self, num_players: int, special_cards_per_player: int = 0):
        self.num_players = num_players
        self.special_cards_per_player = special_cards_per_player
        self.board: Optional[Board] = None
        self.deck: Optional[Deck] = None
        self.players: Optional[List[Player]] = None
        self.current_player_idx: int = 0
        self.final_round_active: bool = False
        self.final_round_start_player: int = -1
        self.game_over: bool = False
        self.force_end_turn: bool = False  # Set when Coffee or Beer finishes (or 2nd Water)
        self.water_refilled_this_turn: List[bool] = [False] * num_players

    def initialize_game(self) -> GameState:
        """Create a full game with real board, deck, and dealt hands"""
        # 1. Create board with dishes
        self.board = Board(radius=5)
        self.board.place_dishes(self.num_players)

        # 2. Create deck
        self.deck = Deck()

        # 3. Create players with correct hand sizes
        if self.num_players <= 4:
            base_hand_size = 4
        else:
            base_hand_size = 3

        self.players = []
        for i in range(self.num_players):
            p = Player(name=f"Player {i+1}", position=i)
            p.base_hand_size = base_hand_size
            self.players.append(p)

        # 4. Deal cards to all players (first player gets one fewer card)
        for i, p in enumerate(self.players):
            deal_count = p.max_hand_size - (1 if i == 0 else 0)
            cards = self.deck.draw_multiple(deal_count)
            for c in cards:
                p.draw_card(c)

        # 5. Deal special cards
        if self.special_cards_per_player > 0:
            card_pool = list(range(self.NUM_SPECIAL_CARDS))
            random.shuffle(card_pool)
            for p in self.players:
                n = min(self.special_cards_per_player, len(card_pool))
                p.special_cards = sorted(card_pool[:n])
                card_pool = card_pool[n:]

        # 6. Reset state
        self.current_player_idx = 0
        self.final_round_active = False
        self.final_round_start_player = -1
        self.game_over = False
        self.force_end_turn = False
        self.water_refilled_this_turn = [False] * self.num_players

        # 6. Build and return GameState
        return self._build_game_state()

    def is_game_over(self, game_state: GameState) -> bool:
        return self.game_over

    def execute_action(self, game_state: GameState, action: Action) -> bool:
        """Execute an action on internal game objects, then sync to GameState"""
        try:
            player = self.players[action.player_id]
            self.force_end_turn = False

            if action.action_type == ActionType.EAT_DISH:
                self._execute_eat_dish(player, action)
            elif action.action_type == ActionType.EAT_EMPTY_TILE:
                self._execute_eat_empty_tile(player, action)
            elif action.action_type == ActionType.PLAY_DRINK:
                self._execute_play_drink(player, action)
            elif action.action_type == ActionType.DRINK_TOKEN:
                self._execute_drink_token(player, action)
            elif action.action_type == ActionType.PLAY_ROTATE:
                self._execute_play_rotate(player, action)
            elif action.action_type == ActionType.ADD_TAHINI:
                self._execute_add_tahini(player, action)
            elif action.action_type == ActionType.ADD_HOT_SAUCE:
                self._execute_add_hot_sauce(player, action)
            elif action.action_type == ActionType.END_TURN:
                pass  # Handled by end_turn()

            # Sync internal state to GameState
            self._sync_game_state(game_state)
            return True

        except Exception as e:
            return False

    def end_turn(self, game_state: GameState):
        """End current player's turn, refill their hand, then move to next player"""
        if not self.game_over:
            # Refill hand for the player who just finished their turn.
            # Beer penalty (if any) reduces the target by 1 this once.
            player = self.players[self.current_player_idx]
            target = player.max_hand_size - player.pending_beer_penalty
            player.pending_beer_penalty = 0
            cards_needed = target - len(player.hand)
            if cards_needed > 0:
                cards = self.deck.draw_multiple(cards_needed)
                for c in cards:
                    player.draw_card(c)

            # Advance to next player
            self.current_player_idx = (self.current_player_idx + 1) % self.num_players
            # Reset water refill flag for the new current player's turn
            self.water_refilled_this_turn[self.current_player_idx] = False

        # Check if final round is complete
        if self.final_round_active and self.current_player_idx == self.final_round_start_player:
            self.game_over = True

        self._sync_game_state(game_state)

    def game_state_to_dict(self, game_state: GameState) -> dict:
        return game_state.to_dict()

    # ==================== Action Handlers ====================

    def _execute_eat_dish(self, player: Player, action: Action):
        """Eat a dish from a tile using the fully-specified action recipe."""
        coord = HexCoord(action.tile_coord[0], action.tile_coord[1])
        tile = self.board.get_tile(coord)
        if not tile or tile.is_empty or tile.is_removed:
            return

        dish_type = tile.dish_type

        # 1. Discard the specified card type
        discard_idx = self._find_card_index_by_type(player, action.discard_card_type)
        if discard_idx is None:
            return
        discarded = player.play_card(discard_idx)
        self.deck.add_to_discard(discarded)

        # 2. Use eating resource + calculate extra points/hot from empty tile
        empty_tile_tahini = 0
        empty_tile_hot = 0
        if action.resource_type == 'card':
            injera_idx = next((i for i, c in enumerate(player.hand)
                               if c.card_type == CardType.INJERA), None)
            if injera_idx is not None:
                injera = player.play_card(injera_idx)
                self.deck.add_to_discard(injera)
        elif action.resource_type == 'tile' and action.resource_tile_coord:
            empty_coord = HexCoord(action.resource_tile_coord[0], action.resource_tile_coord[1])
            empty_tile = self.board.get_tile(empty_coord)
            if empty_tile:
                empty_tile_tahini = empty_tile.tahini_tokens
                raw_hot = 2 if (empty_tile.has_hot_token and self._is_center_tile(empty_coord)) else (1 if empty_tile.has_hot_token else 0)
                empty_tile_hot = max(0, raw_hot + empty_tile.hot_sauce_tokens - empty_tile.tahini_tokens)
                empty_tile.use_injera()  # Remove the empty tile

        # 3. Calculate base value
        if dish_type == DishType.BERBERE_MISIR:
            base_value = 3  # Flat 3 points for Berbere
        elif tile.is_hot:
            base_value = 2
        else:
            base_value = 1

        # 4. Handle hot using the specified recipe
        raw_dish_hot = 2 if dish_type == DishType.BERBERE_MISIR else (1 if tile.is_hot else 0)
        dish_hot = max(0, raw_dish_hot + tile.hot_sauce_tokens - tile.tahini_tokens)
        total_hot = dish_hot + empty_tile_hot
        hot_points = self._handle_hot_by_recipe(
            player, action.num_drink_tokens_for_hot, total_hot, action.player_id
        )

        # 5. Eat the dish (Player.eat_dish adds points to score internally)
        player.eat_dish(dish_type, base_value, tile.tahini_tokens + empty_tile_tahini)
        player.score += hot_points  # Drink points from hot handling

        # 6. Mark tile as eaten (sets dish_type=None, adds hot_token if was hot)
        tile.eat_dish()

        # 7. Check final round (count tiles that still have dishes)
        dishes_remaining = sum(1 for t in self.board.tiles.values() if t.dish_type is not None)
        if dishes_remaining == 0:
            self.final_round_active = True
            self.final_round_start_player = action.player_id

    def _execute_eat_empty_tile(self, player: Player, action: Action):
        """Eat an empty tile for its tahini points using the fully-specified recipe."""
        coord = HexCoord(action.tile_coord[0], action.tile_coord[1])
        tile = self.board.get_tile(coord)
        if not tile or not tile.is_empty or tile.is_removed:
            return

        # 1. Discard the specified card type
        discard_idx = self._find_card_index_by_type(player, action.discard_card_type)
        if discard_idx is None:
            return
        discarded = player.play_card(discard_idx)
        self.deck.add_to_discard(discarded)

        # 2. Handle hot using the specified recipe
        hot_points = 0
        raw_hot_level = 2 if (tile.has_hot_token and self._is_center_tile(coord)) else (1 if tile.has_hot_token else 0)
        hot_level = max(0, raw_hot_level + tile.hot_sauce_tokens - tile.tahini_tokens)
        if hot_level > 0:
            hot_points = self._handle_hot_by_recipe(
                player, action.num_drink_tokens_for_hot, hot_level, action.player_id
            )

        # 3. Score tahini + hot points
        if tile.tahini_tokens > 0:
            player.tahini_consumed += tile.tahini_tokens
        player.score += tile.tahini_tokens + hot_points

        # 4. Remove tile from board
        tile.use_injera()

    def _execute_play_drink(self, player: Player, action: Action):
        """Play a drink card to create an active drink (by type, not index)"""
        if action.drink_card_type is None:
            return

        # Find the first drink card of this type
        card_idx = self._find_card_index_by_type(player, action.drink_card_type)
        if card_idx is None:
            return

        card = player.hand[card_idx]
        if card.card_type != CardType.DRINK or not isinstance(card, DrinkCard):
            return

        # Remove card from hand and activate drink
        player.hand.pop(card_idx)
        player.play_drink_card(card)

    def _execute_drink_token(self, player: Player, action: Action):
        """Consume one token from an active drink"""
        if action.drink_index is None:
            return
        points = self._use_drink_token(player, action.drink_index, action.player_id)
        player.score += points

    def _execute_play_rotate(self, player: Player, action: Action):
        """Play a rotate card to rotate the board 60 degrees"""
        if action.card_index is None or action.card_index >= len(player.hand):
            return
        card = player.play_card(action.card_index)
        self.deck.add_to_discard(card)

        clockwise = action.rotation_direction == 'clockwise'
        self.board.rotate_board(clockwise)

    def _execute_add_tahini(self, player: Player, action: Action):
        """Play a tahini card to add tokens to a triangle of tiles"""
        if action.card_index is None or action.card_index >= len(player.hand):
            return

        card = player.play_card(action.card_index)
        self.deck.add_to_discard(card)

        coord = HexCoord(action.tile_coord[0], action.tile_coord[1])
        orientation = action.triangle_orientation

        # Find the 3 tiles of the triangle
        triangle_coords = self._find_triangle_tiles(coord, orientation)
        for tc in triangle_coords:
            tile = self.board.get_tile(tc)
            if tile and not tile.is_removed:
                tile.tahini_tokens += 1

    def _execute_add_hot_sauce(self, player: Player, action: Action):
        """Play a hot sauce card to add hotness tokens to a triangle of tiles, then draw 1 card"""
        if action.card_index is None or action.card_index >= len(player.hand):
            return

        card = player.play_card(action.card_index)
        self.deck.add_to_discard(card)

        coord = HexCoord(action.tile_coord[0], action.tile_coord[1])
        orientation = action.triangle_orientation

        triangle_coords = self._find_triangle_tiles(coord, orientation)
        for tc in triangle_coords:
            tile = self.board.get_tile(tc)
            if tile and not tile.is_removed:
                tile.hot_sauce_tokens += 1

        # Draw 1 card immediately
        new_cards = self.deck.draw_multiple(1)
        for c in new_cards:
            player.draw_card(c)

    # ==================== Drink Helpers ====================

    def _use_drink_token(self, player: Player, drink_index: int, player_id: int) -> int:
        """
        Use one drink token. Handles finish effects (hand size, water refill).
        Removes finished drink. Coffee/Beer/2nd-Water finishing ends the turn.
        Returns points earned.
        """
        if drink_index >= len(player.active_drinks):
            return 0

        # Remember drink type before consuming (needed after pop)
        drink = player.active_drinks[drink_index]
        drink_type = drink.drink_type

        points, cards_drawn = player.drink_token(drink_index, self.deck)

        # Coffee finishing: refill hand to max_hand_size + 1 immediately
        if cards_drawn > 0:
            to_draw = (player.max_hand_size + 1) - len(player.hand)
            if to_draw > 0:
                new_cards = self.deck.draw_multiple(to_draw)
                for c in new_cards:
                    player.draw_card(c)

        # Check if drink just finished
        if drink_index < len(player.active_drinks) and player.active_drinks[drink_index].is_finished:
            # Remove finished drink so player can order a new one
            player.active_drinks.pop(drink_index)

            # Coffee and Beer always end the turn when finished
            if drink_type in (DrinkType.COFFEE, DrinkType.BEER):
                self.force_end_turn = True
            elif drink_type == DrinkType.WATER:
                if not self.water_refilled_this_turn[player_id]:
                    # First Water this turn: refill hand
                    cards_needed = player.max_hand_size - len(player.hand)
                    if cards_needed > 0:
                        new_cards = self.deck.draw_multiple(cards_needed)
                        for card in new_cards:
                            player.draw_card(card)
                    self.water_refilled_this_turn[player_id] = True
                else:
                    # Second+ Water this turn: end turn (no refill)
                    self.force_end_turn = True

        return points

    def _handle_hot_by_recipe(self, player: Player, num_drink_tokens: int,
                              total_hot: int, player_id: int) -> int:
        """
        Handle hot using the exact recipe specified by the action.
        Uses num_drink_tokens drink tokens first, then injera for the rest.
        Returns total points earned from drink tokens.
        """
        points = 0

        # 1. Use the specified number of drink tokens
        for _ in range(num_drink_tokens):
            active_idx = next((i for i, d in enumerate(player.active_drinks)
                               if not d.is_finished), None)
            if active_idx is not None:
                pts = self._use_drink_token(player, active_idx, player_id)
                points += pts

        # 2. Use injera cards for the rest
        injera_for_hot = total_hot - num_drink_tokens
        for _ in range(injera_for_hot):
            injera_idx = next((i for i, c in enumerate(player.hand)
                               if c.card_type == CardType.INJERA), None)
            if injera_idx is not None:
                card = player.play_card(injera_idx)
                self.deck.add_to_discard(card)

        return points

    # ==================== Other Helpers ====================

    def _find_card_index_by_type(self, player: Player, discard_type: str) -> Optional[int]:
        """
        Find the index of a card in hand matching the given discard type.
        discard_type: 'Clean Injera', 'Rotate', 'Tahini', 'Coffee', 'Beer', or 'Water'
        """
        if not discard_type:
            return None

        for i, c in enumerate(player.hand):
            if discard_type == 'Clean Injera' and c.card_type == CardType.INJERA:
                return i
            elif discard_type == 'Rotate' and c.card_type == CardType.ROTATE:
                return i
            elif discard_type == 'Tahini' and c.card_type == CardType.TAHINI:
                return i
            elif discard_type in ('Coffee', 'Beer', 'Water'):
                if c.card_type == CardType.DRINK and isinstance(c, DrinkCard):
                    if c.drink_type.value == discard_type:
                        return i

        return None

    def _find_triangle_tiles(self, top_coord: HexCoord, orientation: str) -> List[HexCoord]:
        """Find the 3 tile coordinates forming a triangle with given top and orientation"""
        neighbors = top_coord.neighbors()

        # Check all pairs of adjacent neighbors
        for i in range(6):
            n1 = neighbors[i]
            n2 = neighbors[(i + 1) % 6]

            # Both must exist on board and not be removed
            if n1 not in self.board.tiles or n2 not in self.board.tiles:
                continue
            if self.board.tiles[n1].is_removed or self.board.tiles[n2].is_removed:
                continue

            # Determine if top_coord is actually the top (smallest r)
            tiles = [(top_coord.q, top_coord.r), (n1.q, n1.r), (n2.q, n2.r)]
            sorted_tiles = sorted(tiles, key=lambda t: (t[1], t[0]))

            if sorted_tiles[0] != (top_coord.q, top_coord.r):
                continue

            # Check orientation
            bottom1, bottom2 = sorted_tiles[1], sorted_tiles[2]
            avg_q = (bottom1[0] + bottom2[0]) / 2

            if orientation == 'left' and avg_q < top_coord.q:
                return [top_coord, n1, n2]
            elif orientation == 'right' and avg_q > top_coord.q:
                return [top_coord, n1, n2]

        # Fallback: just the top tile
        return [top_coord]

    def _is_center_tile(self, coord: HexCoord) -> bool:
        """Check if coordinate is in center cluster (Berbere hot token territory)"""
        return abs(coord.q) <= 1 and abs(coord.r) <= 1 and abs(coord.q + coord.r) <= 1

    def _card_to_composition_key(self, card: Card) -> str:
        """Convert a Card object to the composition key used in DeckState"""
        if card.card_type == CardType.INJERA:
            return 'Clean Injera'
        elif card.card_type == CardType.ROTATE:
            return 'Rotate Injera'
        elif card.card_type == CardType.TAHINI:
            return 'Tahini'
        elif card.card_type == CardType.HOT_SAUCE:
            return 'Add Hot Sauce'
        elif card.card_type == CardType.DRINK:
            if isinstance(card, DrinkCard):
                return f'Order {card.drink_type.value}'
            return card.name
        return card.name

    # ==================== State Conversion ====================

    def _build_game_state(self) -> GameState:
        """Build a GameState from internal Board/Deck/Player objects"""
        # Convert tiles
        board_tiles = []
        for coord, tile in self.board.tiles.items():
            is_empty = tile.dish_type is None and not tile.is_removed
            tile_state = TileState(
                q=coord.q,
                r=coord.r,
                dish=tile.dish_type.value if tile.dish_type else None,
                hot=tile.is_hot,
                hot_token=tile.has_hot_token,
                tahini=tile.tahini_tokens,
                hot_sauce=tile.hot_sauce_tokens,
                empty=is_empty,
                removed=tile.is_removed,
                can_eat_empty=(self.board.can_eat_empty_tile(coord) if is_empty else False)
            )
            board_tiles.append(tile_state)

        # Convert players
        players = []
        for i, p in enumerate(self.players):
            hand = []
            for c in p.hand:
                if c.card_type == CardType.DRINK and isinstance(c, DrinkCard):
                    hand.append(CardState(card_type='Drink', name=c.drink_type.value))
                elif c.card_type == CardType.INJERA:
                    hand.append(CardState(card_type='Clean Injera', name='Clean Injera'))
                elif c.card_type == CardType.TAHINI:
                    hand.append(CardState(card_type='Tahini', name='Tahini'))
                elif c.card_type == CardType.ROTATE:
                    hand.append(CardState(card_type='Rotate', name='Rotate Injera'))

            drinks = []
            for d in p.active_drinks:
                if not d.is_finished:
                    drinks.append(DrinkState(drink_type=d.drink_type.value, tokens=d.tokens_remaining))

            dish_counts = {}
            for dish in DishType:
                count = p.count_dish_type(dish)
                if count > 0:
                    dish_counts[dish.value] = count

            ps = PlayerState(
                player_id=i,
                name=p.name,
                position=p.position,
                score=p.score,
                hand=hand,
                hand_size_modifier=p.hand_size_modifier,
                base_hand_size=p.base_hand_size,
                super_hot_count=p.super_hot_eaten_count,
                super_hot_value=p.get_super_hot_value(),
                eaten=[d.value for d in p.eaten_dishes],
                dish_counts=dish_counts,
                drinks=drinks,
                water_refilled_this_turn=self.water_refilled_this_turn[i],
                is_ai=True,
                ai_level='neural',
                special_cards=p.special_cards,
                tahini_consumed=p.tahini_consumed,
                hot_dishes_eaten=p.hot_dishes_eaten,
                total_hot_eaten=p.total_hot_eaten
            )
            players.append(ps)

        # Deck composition (cards remaining in deck, not including discard)
        composition = {}
        for card in self.deck.cards:
            key = self._card_to_composition_key(card)
            composition[key] = composition.get(key, 0) + 1

        deck_state = DeckState(
            cards_remaining=len(self.deck.cards),
            deck_size=len(self.deck.cards),
            discard_size=len(self.deck.discard),
            composition=composition
        )

        # Reachable tiles per player
        reachable = []
        for i in range(self.num_players):
            coords = self.board.get_reachable_tiles(i, self.num_players)
            reachable.append([(c.q, c.r) for c in coords])

        return GameState(
            num_players=self.num_players,
            current_player_idx=self.current_player_idx,
            board=board_tiles,
            players=players,
            deck=deck_state,
            reachable_by_player=reachable,
            final_round_active=self.final_round_active,
            final_round_start_player=self.final_round_start_player,
            game_over=self.game_over
        )

    def _sync_game_state(self, game_state: GameState):
        """Sync internal state to existing GameState object (in-place update)"""
        new = self._build_game_state()
        game_state.num_players = new.num_players
        game_state.current_player_idx = new.current_player_idx
        game_state.board = new.board
        game_state.players = new.players
        game_state.deck = new.deck
        game_state.reachable_by_player = new.reachable_by_player
        game_state.final_round_active = new.final_round_active
        game_state.final_round_start_player = new.final_round_start_player
        game_state.game_over = new.game_over


def compute_special_card_scores(players: List[Player], num_players: int) -> List[int]:
    """
    Compute end-of-game special card bonus scores for each player.
    Returns a list of bonus scores (one per player).

    Card indices (0-18) map to:
    0: four_by_four, 1: tahini_freak, 2: sesame_intolerance, 3: tahini_queen,
    4: tasting_menu, 5: picky_eater, 6: some_like_it_hot, 7: hot_monster,
    8: berbere_freak, 9: no_hot_for_you, 10: peas_please, 11: peas_prince,
    12: lentils_party, 13: lentils_princess, 14: savage_cabbage, 15: cabbage_king,
    16: healthy_appetite, 17: consolation_prize, 18: delicate_palate
    """
    bonuses = [0] * len(players)

    # Precompute per-player stats
    stats = []
    for p in players:
        dish_counts = {}
        for d in p.eaten_dishes:
            dish_counts[d] = dish_counts.get(d, 0) + 1
        num_types = len(set(p.eaten_dishes))
        peas = dish_counts.get(DishType.SHIRO, 0) + dish_counts.get(DishType.KIK_ALICHA, 0)
        lentils = dish_counts.get(DishType.MISIR_WOT, 0) + dish_counts.get(DishType.AZIFA, 0)
        cabbage = dish_counts.get(DishType.GOMEN, 0) + dish_counts.get(DishType.TIKEL_GOMEN, 0)
        stats.append({
            'dish_counts': dish_counts,
            'num_types': num_types,
            'total_eaten': len(p.eaten_dishes),
            'peas': peas,
            'lentils': lentils,
            'cabbage': cabbage,
            'tahini': p.tahini_consumed,
            'hot': p.hot_dishes_eaten,
            'total_hot': p.total_hot_eaten,
            'berbere': p.super_hot_eaten_count,
        })

    n = num_players

    for pi, p in enumerate(players):
        s = stats[pi]
        others = [stats[j] for j in range(len(players)) if j != pi]

        for card_id in p.special_cards:
            pts = 0

            if card_id == 0:  # four_by_four
                for count in s['dish_counts'].values():
                    if count == 4:
                        pts += 4
                if s['num_types'] == 4:
                    pts += 4

            elif card_id == 1:  # tahini_freak
                pts = s['tahini'] // 2

            elif card_id == 2:  # sesame_intolerance
                if s['tahini'] == 0:
                    pts = 8

            elif card_id == 3:  # tahini_queen
                if s['tahini'] > 0 and all(s['tahini'] > o['tahini'] for o in others):
                    pts = 2 * (n - 1)

            elif card_id == 4:  # tasting_menu
                if s['num_types'] == 5: pts = 5
                elif s['num_types'] == 6: pts = 6
                elif s['num_types'] == 7: pts = 7

            elif card_id == 5:  # picky_eater
                if s['num_types'] == 3:
                    pts = 21

            elif card_id == 6:  # some_like_it_hot
                pts = s['total_hot'] // 2

            elif card_id == 7:  # hot_monster
                if s['total_hot'] > 0 and all(s['total_hot'] > o['total_hot'] for o in others):
                    pts = 3 * (n - 1)

            elif card_id == 8:  # berbere_freak
                pts = 2 * s['berbere']

            elif card_id == 9:  # no_hot_for_you
                if all(s['total_hot'] < o['total_hot'] for o in others):
                    pts = 4 * (n - 1)

            elif card_id == 10:  # peas_please
                pts = s['peas']

            elif card_id == 11:  # peas_prince
                if s['peas'] > 0 and all(s['peas'] > o['peas'] for o in others):
                    pts = 2 * (n - 1)

            elif card_id == 12:  # lentils_party
                pts = s['lentils']

            elif card_id == 13:  # lentils_princess
                if s['lentils'] > 0 and all(s['lentils'] > o['lentils'] for o in others):
                    pts = 2 * (n - 1)

            elif card_id == 14:  # savage_cabbage
                pts = s['cabbage']

            elif card_id == 15:  # cabbage_king
                if s['cabbage'] > 0 and all(s['cabbage'] > o['cabbage'] for o in others):
                    pts = 2 * (n - 1)

            elif card_id == 16:  # healthy_appetite
                if s['total_eaten'] > 0 and all(s['total_eaten'] > o['total_eaten'] for o in others):
                    pts = 2 * (n - 1)

            elif card_id == 17:  # consolation_prize
                if all(s['total_eaten'] < o['total_eaten'] for o in others):
                    pts = 4 * (n - 1)

            elif card_id == 18:  # delicate_palate
                pts = (s['total_eaten'] - s['total_hot']) // 2

            bonuses[pi] += pts

    return bonuses
