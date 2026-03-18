"""
Game State - Represents the complete state of an Injera game
This is a lightweight version that can be serialized to/from JSON for the web interface
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Tuple
from enum import Enum


class ActionType(Enum):
    """All possible action types in the game"""
    EAT_DISH = "eat_dish"
    EAT_EMPTY_TILE = "eat_empty_tile"
    PLAY_DRINK = "play_drink"
    DRINK_TOKEN = "drink_token"
    PLAY_ROTATE = "play_rotate"
    ADD_TAHINI = "add_tahini"
    ADD_HOT_SAUCE = "add_hot_sauce"
    END_TURN = "end_turn"
    DISCARD_REDRAW = "discard_redraw"
    SELECT_SPECIAL_CARDS = "select_special_cards"


def normalize_card_name(name: str) -> str:
    """Normalize card names between JS ('Order Coffee') and Python ('Coffee') formats"""
    if not name:
        return name
    if name.startswith('Order '):
        return name[6:]  # 'Order Coffee' -> 'Coffee'
    return name


@dataclass
class Action:
    """Represents a single action a player can take.

    Actions use TYPE-BASED fields (not index-based) to avoid degeneracy
    where identical cards at different indices would create duplicate actions.
    """
    action_type: ActionType
    player_id: int

    # Tile targeting (eat_dish, eat_empty_tile, add_tahini)
    tile_coord: Optional[Tuple[int, int]] = None  # (q, r) for hex coordinate

    # Eat action specifics (eat_dish, eat_empty_tile)
    resource_type: Optional[str] = None  # 'card' or 'tile'
    resource_tile_coord: Optional[Tuple[int, int]] = None  # Adjacent empty tile coord
    discard_card_type: Optional[str] = None  # Card TYPE to discard (e.g. 'Coffee', 'Clean Injera')
    num_drink_tokens_for_hot: int = 0  # Drink tokens consumed for hot handling
    # (remaining hot handled by injera cards = total_hot - num_drink_tokens_for_hot)

    # Play drink specifics
    drink_card_type: Optional[str] = None  # 'Coffee', 'Beer', or 'Water'

    # Drink token specifics
    drink_index: Optional[int] = None  # Which active drink to consume

    # Rotate specifics
    rotation_direction: Optional[str] = None  # 'clockwise' or 'counterclockwise'

    # Tahini specifics
    triangle_orientation: Optional[str] = None  # 'left' or 'right'

    # Legacy: card_index still used by play_rotate and add_tahini
    # (all rotate cards are identical, so first index is fine)
    card_index: Optional[int] = None

    # Draft action (select_special_cards)
    dealt_card_ids: Optional[List[str]] = None   # All cards shown to the player
    kept_card_ids: Optional[List[str]] = None    # Cards the player chose to keep

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'action_type': self.action_type.value,
            'player_id': self.player_id,
            'tile_coord': self.tile_coord,
            'resource_type': self.resource_type,
            'resource_tile_coord': self.resource_tile_coord,
            'discard_card_type': self.discard_card_type,
            'num_drink_tokens_for_hot': self.num_drink_tokens_for_hot,
            'drink_card_type': self.drink_card_type,
            'drink_index': self.drink_index,
            'rotation_direction': self.rotation_direction,
            'triangle_orientation': self.triangle_orientation,
            'card_index': self.card_index,
            'dealt_card_ids': self.dealt_card_ids,
            'kept_card_ids': self.kept_card_ids,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Action':
        """Create Action from dictionary"""
        return cls(
            action_type=ActionType(data['action_type']),
            player_id=data['player_id'],
            tile_coord=tuple(data['tile_coord']) if data.get('tile_coord') else None,
            resource_type=data.get('resource_type'),
            resource_tile_coord=tuple(data['resource_tile_coord']) if data.get('resource_tile_coord') else None,
            discard_card_type=data.get('discard_card_type'),
            num_drink_tokens_for_hot=data.get('num_drink_tokens_for_hot', 0),
            drink_card_type=data.get('drink_card_type'),
            drink_index=data.get('drink_index'),
            rotation_direction=data.get('rotation_direction'),
            triangle_orientation=data.get('triangle_orientation'),
            card_index=data.get('card_index'),
            dealt_card_ids=data.get('dealt_card_ids'),
            kept_card_ids=data.get('kept_card_ids'),
        )


@dataclass
class TileState:
    """State of a single hex tile"""
    q: int
    r: int
    dish: Optional[str] = None
    hot: bool = False
    hot_token: bool = False
    tahini: int = 0
    hot_sauce: int = 0
    empty: bool = False
    removed: bool = False
    can_eat_empty: bool = False
    
    @property
    def coord(self) -> Tuple[int, int]:
        return (self.q, self.r)


@dataclass
class CardState:
    """State of a card"""
    card_type: str  # 'Clean Injera', 'Drink', 'Tahini', 'Rotate'
    name: str  # Full name like 'Order Coffee'


@dataclass
class DrinkState:
    """State of an active drink"""
    drink_type: str  # 'Coffee', 'Beer', 'Water'
    tokens: int


@dataclass
class PlayerState:
    """State of a single player"""
    player_id: int
    name: str
    position: int  # Seat position (0-5)
    score: int = 0
    hand: List[CardState] = field(default_factory=list)
    hand_size_modifier: int = 0
    base_hand_size: int = 5
    super_hot_count: int = 0
    super_hot_value: int = 3
    eaten: List[str] = field(default_factory=list)
    dish_counts: Dict[str, int] = field(default_factory=dict)
    drinks: List[DrinkState] = field(default_factory=list)
    water_refilled_this_turn: bool = False
    is_ai: bool = False
    ai_level: Optional[str] = None  # 'beginner', 'intermediate', 'advanced', 'expert'
    special_cards: List[int] = field(default_factory=list)  # Card indices (0-17) held
    tahini_consumed: int = 0
    hot_dishes_eaten: int = 0
    total_hot_eaten: int = 0
    @property
    def max_hand_size(self) -> int:
        return self.base_hand_size + self.hand_size_modifier

    @property
    def hand_counts(self) -> Dict[str, int]:
        """Count of each card type in hand (e.g. {'Clean Injera': 2, 'Drink': 1})"""
        counts: Dict[str, int] = {}
        for card in self.hand:
            counts[card.card_type] = counts.get(card.card_type, 0) + 1
        return counts

    @property
    def drink_card_types(self) -> Set[str]:
        """Set of distinct drink card names in hand (e.g. {'Coffee', 'Beer'})"""
        return {normalize_card_name(c.name) for c in self.hand if c.card_type == 'Drink'}

    @property
    def discard_card_types(self) -> Set[str]:
        """Set of distinct card types that can be discarded when eating"""
        types: Set[str] = set()
        for c in self.hand:
            if c.card_type == 'Drink':
                types.add(normalize_card_name(c.name))  # 'Coffee', 'Beer', 'Water'
            else:
                types.add(c.card_type)  # 'Clean Injera', 'Rotate', 'Tahini'
        return types


@dataclass
class DeckState:
    """State of the deck"""
    cards_remaining: int
    deck_size: int
    discard_size: int
    composition: Dict[str, int] = field(default_factory=dict)


@dataclass 
class GameState:
    """Complete state of the game"""
    num_players: int
    current_player_idx: int
    board: List[TileState]
    players: List[PlayerState]
    deck: DeckState
    reachable_by_player: List[List[Tuple[int, int]]]  # List of reachable coords for each player
    final_round_active: bool = False
    final_round_start_player: int = -1
    game_over: bool = False
    winner_id: Optional[int] = None
    # Cards dealt to current player during the draft phase (empty outside draft)
    draft_dealt_cards: List[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'num_players': self.num_players,
            'current_player_idx': self.current_player_idx,
            'board': [vars(tile) for tile in self.board],
            'players': [{
                'player_id': p.player_id,
                'name': p.name,
                'position': p.position,
                'score': p.score,
                'hand': [{'type': c.card_type, 'name': c.name} for c in p.hand],
                'hand_size_modifier': p.hand_size_modifier,
                'base_hand_size': p.base_hand_size,
                'max_hand_size': p.max_hand_size,
                'super_hot_count': p.super_hot_count,
                'super_hot_value': p.super_hot_value,
                'eaten': p.eaten,
                'dish_counts': p.dish_counts,
                'drinks': [{'type': d.drink_type, 'tokens': d.tokens} for d in p.drinks],
                'water_refilled_this_turn': p.water_refilled_this_turn,
                'is_ai': p.is_ai,
                'ai_level': p.ai_level,
                'special_cards': p.special_cards,
                'tahini_consumed': p.tahini_consumed,
                'hot_dishes_eaten': p.hot_dishes_eaten,
                'total_hot_eaten': p.total_hot_eaten
            } for p in self.players],
            'deck': {
                'cards_remaining': self.deck.cards_remaining,
                'deck_size': self.deck.deck_size,
                'discard_size': self.deck.discard_size,
                'composition': self.deck.composition
            },
            'reachable_by_player': self.reachable_by_player,
            'final_round_active': self.final_round_active,
            'final_round_start_player': self.final_round_start_player,
            'game_over': self.game_over,
            'winner_id': self.winner_id,
            'draft_dealt_cards': self.draft_dealt_cards,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'GameState':
        """Create GameState from dictionary"""
        # Convert tile data from camelCase (JavaScript) to snake_case (Python)
        board = []
        for tile_data in data['board']:
            tile_dict = {
                'q': tile_data['q'],
                'r': tile_data['r'],
                'dish': tile_data.get('dish'),
                'hot': tile_data.get('hot', False),
                'hot_token': tile_data.get('hotToken', False),  # camelCase -> snake_case
                'tahini': tile_data.get('tahini', 0),
                'hot_sauce': tile_data.get('hotSauce', 0),
                'empty': tile_data.get('empty', False),
                'removed': tile_data.get('removed', False),
                'can_eat_empty': tile_data.get('canEatEmpty', False)  # camelCase -> snake_case
            }
            board.append(TileState(**tile_dict))
        
        players = []
        for idx, p_data in enumerate(data['players']):
            # Convert camelCase to snake_case
            player = PlayerState(
                player_id=idx,  # Use array index as player_id
                name=p_data['name'],
                position=p_data['position'],
                score=p_data['score'],
                hand=[CardState(card_type=c['type'], name=c['name']) for c in p_data['hand']],
                hand_size_modifier=p_data.get('handSizeModifier', p_data.get('hand_size_modifier', 0)),
                base_hand_size=p_data.get('baseHandSize', p_data.get('base_hand_size', 5)),
                super_hot_count=p_data.get('superHotCount', p_data.get('super_hot_count', 0)),
                super_hot_value=p_data.get('superHotValue', p_data.get('super_hot_value', 3)),
                eaten=p_data.get('eaten', []),
                dish_counts=p_data.get('dishCounts', p_data.get('dish_counts', {})),
                drinks=[DrinkState(drink_type=d['type'], tokens=d['tokens']) for d in p_data.get('drinks', [])],
                water_refilled_this_turn=p_data.get('waterRefilledThisTurn', p_data.get('water_refilled_this_turn', False)),
                is_ai=p_data.get('isAI', p_data.get('is_ai', False)),
                ai_level=p_data.get('aiLevel', p_data.get('ai_level')),
                special_cards=p_data.get('specialCards', p_data.get('special_cards', [])),
                tahini_consumed=p_data.get('tahiniConsumed', p_data.get('tahini_consumed', 0)),
                hot_dishes_eaten=p_data.get('hotDishesEaten', p_data.get('hot_dishes_eaten', 0)),
                total_hot_eaten=p_data.get('totalHotEaten', p_data.get('total_hot_eaten', 0))
            )
            players.append(player)
        
        # Convert deck data from camelCase (JavaScript) to snake_case (Python)
        deck_data = data['deck']
        deck = DeckState(
            cards_remaining=deck_data.get('cardsRemaining', deck_data.get('cards_remaining', 0)),
            deck_size=deck_data.get('deckSize', deck_data.get('deck_size', 0)),
            discard_size=deck_data.get('discardSize', deck_data.get('discard_size', 0)),
            composition=deck_data.get('composition', {})
        )
        
        # Convert reachable coordinates from objects to tuples
        reachable_by_player = []
        for player_reachable in data['reachable_by_player']:
            coord_tuples = [(coord['q'], coord['r']) if isinstance(coord, dict) else coord 
                           for coord in player_reachable]
            reachable_by_player.append(coord_tuples)
        
        return cls(
            num_players=data['num_players'],
            current_player_idx=data['current_player_idx'],
            board=board,
            players=players,
            deck=deck,
            reachable_by_player=reachable_by_player,
            final_round_active=data['final_round_active'],
            final_round_start_player=data['final_round_start_player'],
            game_over=data.get('game_over', False),
            winner_id=data.get('winner_id'),
            draft_dealt_cards=data.get('draft_dealt_cards', []),
        )
    
    def get_current_player(self) -> PlayerState:
        """Get the current player"""
        return self.players[self.current_player_idx]
    
    def get_tile(self, q: int, r: int) -> Optional[TileState]:
        """Get tile at coordinate"""
        for tile in self.board:
            if tile.q == q and tile.r == r:
                return tile
        return None
    
    def get_reachable_tiles(self, player_id: int) -> List[Tuple[int, int]]:
        """Get reachable tile coordinates for a player"""
        player_position = self.players[player_id].position
        return self.reachable_by_player[player_position]
    
    def is_tile_reachable(self, player_id: int, q: int, r: int) -> bool:
        """Check if a tile is reachable by a player"""
        reachable = self.get_reachable_tiles(player_id)
        return (q, r) in reachable