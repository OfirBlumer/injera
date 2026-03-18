"""
State Encoder for Neural Network AI
Converts game state into tensor representation
"""

import numpy as np
from typing import Dict, List, Tuple, Any, Optional
from enum import Enum

# Game constants
DISH_TYPES = ['Gomen', 'Azifa', 'Shiro', 'Kik Alicha', 'Misir Wot', 'Tikel Gomen', 'Key Sir']
CARD_TYPES = ['Injera', 'Rotate', 'Beer', 'Water', 'Coffee', 'Tahini', 'HotSauce']
DRINK_TYPES = ['Beer', 'Water', 'Coffee']

# Board has 61 hexagonal tiles
BOARD_SIZE = 61
MAX_PLAYERS = 6
MAX_HAND_SIZE = 12  # Conservative estimate
NUM_SPECIAL_CARDS = 19
SPECIAL_CARD_NAME_TO_IDX = {
    '4x4': 0, 'tahini_party': 1, 'sesame_intolerance': 2, 'tahini_queen': 3,
    'tasting_menu': 4, 'picky_eater': 5, 'some_like_it_hot': 6, 'too_hot_to_handle': 7,
    'beetroot_boss': 8, 'no_hot_for_you': 9, 'peas_please': 10, 'peas_prince': 11,
    'lentils_freak': 12, 'lentils_princess': 13, 'cabbage_savage': 14, 'cabbage_king': 15,
    'healthy_appetite': 16, 'consolation_prize': 17, 'delicate_palate': 18,
    # Legacy aliases for backward compatibility with old recordings
    'four_by_four': 0, 'tahini_freak': 1, 'hot_monster': 7,
    'berbere_freak': 8, 'lentils_party': 12, 'savage_cabbage': 14,
}
# Reverse mapping: index → card id
SPECIAL_CARD_IDX_TO_NAME: Dict[int, str] = {v: k for k, v in SPECIAL_CARD_NAME_TO_IDX.items()}

# ==================== FIXED ACTION SPACE ====================
# Each action type occupies a fixed region. Same semantic action = same index always.

# Drink types for play_drink (3)
DRINK_TYPES_ORDER = ['Coffee', 'Beer', 'Water']

# Discard card types (6)
DISCARD_TYPES_ORDER = ['Clean Injera', 'Rotate', 'Coffee', 'Beer', 'Water', 'Tahini']
NUM_DISCARD_TYPES = len(DISCARD_TYPES_ORDER)

# Hot handling levels (0-4 drink tokens for hot)
NUM_HOT_LEVELS = 5

# Resource categories for eat_dish (7)
# 0: card (use injera card)
# 1: plain tile (no hot token, no tahini)
# 2: hot tile (hot level 1 / outer, no tahini)
# 3: extra hot tile (hot level 2 / center, no tahini)
# 4: tahini tile (has tahini, no hot)
# 5: hot+tahini tile (hot level 1 + tahini)
# 6: extra hot+tahini tile (hot level 2 + tahini)
NUM_RESOURCE_CATS = 7

# Rotation directions
ROTATION_ORDER = ['clockwise', 'counterclockwise']

# Triangle orientations
ORIENTATION_ORDER = ['left', 'right']

# Sub-index strides
EAT_DISH_STRIDE_PER_TILE = NUM_RESOURCE_CATS * NUM_DISCARD_TYPES * NUM_HOT_LEVELS  # 7*6*5 = 210
EAT_EMPTY_STRIDE_PER_TILE = NUM_DISCARD_TYPES * NUM_HOT_LEVELS  # 6*5 = 30

# Action space layout
BASE_PLAY_DRINK = 0                                          # 3 slots
BASE_DRINK_TOKEN = BASE_PLAY_DRINK + 3                       # 3 slots
BASE_PLAY_ROTATE = BASE_DRINK_TOKEN + 3                      # 2 slots
BASE_ADD_TAHINI = BASE_PLAY_ROTATE + 2                       # 122 slots (61*2)
BASE_ADD_HOT_SAUCE = BASE_ADD_TAHINI + BOARD_SIZE * 2        # 122 slots (61*2)
BASE_EAT_DISH = BASE_ADD_HOT_SAUCE + BOARD_SIZE * 2          # 12810 slots (61*210)
BASE_EAT_EMPTY_TILE = BASE_EAT_DISH + BOARD_SIZE * EAT_DISH_STRIDE_PER_TILE  # 1830 slots (61*30)
INDEX_END_TURN = BASE_EAT_EMPTY_TILE + BOARD_SIZE * EAT_EMPTY_STRIDE_PER_TILE
INDEX_DISCARD_REDRAW = INDEX_END_TURN + 1

# Draft action: choose which pair of special cards to keep
# C(19, 2) = 171 possible pairs; only legal pair indices are unmasked during the draft
NUM_DRAFT_PAIRS = NUM_SPECIAL_CARDS * (NUM_SPECIAL_CARDS - 1) // 2  # 171
BASE_SELECT_DRAFT = INDEX_DISCARD_REDRAW + 1
ACTION_SPACE_SIZE = BASE_SELECT_DRAFT + NUM_DRAFT_PAIRS  # 15065

# Precomputed pair <-> index mappings (sorted card indices i < j)
DRAFT_PAIR_TO_IDX: Dict[Tuple[int, int], int] = {}
DRAFT_IDX_TO_PAIR: Dict[int, Tuple[int, int]] = {}
_draft_idx = 0
for _i in range(NUM_SPECIAL_CARDS):
    for _j in range(_i + 1, NUM_SPECIAL_CARDS):
        DRAFT_PAIR_TO_IDX[(_i, _j)] = _draft_idx
        DRAFT_IDX_TO_PAIR[_draft_idx] = (_i, _j)
        _draft_idx += 1
del _draft_idx, _i, _j


def build_coord_to_board_idx(board: List[Dict]) -> Dict[Tuple[int, int], int]:
    """Build dynamic (q,r) -> board list index mapping from current board data.

    This must be rebuilt per game state because board rotation changes
    tile coordinates while preserving list order.
    """
    return {(tile['q'], tile['r']): i for i, tile in enumerate(board)}


def _is_center_tile(q: int, r: int) -> bool:
    """Check if a tile is in the center area (hot level 2 / extra hot)."""
    return abs(q) <= 1 and abs(r) <= 1 and abs(q + r) <= 1


def get_resource_category(action, board: List[Dict], coord_to_idx: Dict) -> int:
    """Determine the resource category (0-6) for an eat_dish action.

    Args:
        action: Action object or dict with resource_type, resource_tile_coord
        resource_type and resource_tile_coord can be attributes or dict keys
    """
    # Get resource_type
    if hasattr(action, 'resource_type'):
        resource_type = action.resource_type
        resource_tile_coord = action.resource_tile_coord
    else:
        resource_type = action.get('resource_type')
        resource_tile_coord = action.get('resource_tile_coord')

    if resource_type == 'card':
        return 0  # card

    # resource_type == 'tile' — look up the resource tile's properties
    if resource_tile_coord is None:
        return 1  # fallback: plain tile

    rtc = tuple(resource_tile_coord) if not isinstance(resource_tile_coord, tuple) else resource_tile_coord

    # Find the resource tile in board data
    if rtc in coord_to_idx:
        tile_idx = coord_to_idx[rtc]
        tile = board[tile_idx]
    else:
        return 1  # fallback: plain tile

    has_hot = bool(tile.get('hotToken', tile.get('hot_token', False)))
    has_tahini = (tile.get('tahini', tile.get('tahini_tokens', 0)) or 0) > 0
    hot_level = 2 if _is_center_tile(rtc[0], rtc[1]) else 1

    if has_hot and has_tahini:
        return 5 if hot_level == 1 else 6  # hot+tahini or extra_hot+tahini
    elif has_hot:
        return 2 if hot_level == 1 else 3  # hot or extra_hot
    elif has_tahini:
        return 4  # tahini
    else:
        return 1  # plain


def action_to_fixed_index(action, coord_to_idx: Dict, board: List[Dict]) -> int:
    """Convert an Action (object or dict) to its fixed index in the action space.

    Args:
        action: Action object (has .action_type, .tile_coord, etc.) or dict
        coord_to_idx: {(q,r): board_list_index} mapping
        board: Board data list (for resource tile property lookup)

    Returns:
        Fixed index (0 to ACTION_SPACE_SIZE-1), or -1 if invalid
    """
    # Handle both Action objects and dicts
    if hasattr(action, 'action_type'):
        atype = action.action_type.value if hasattr(action.action_type, 'value') else str(action.action_type)
    else:
        atype = action.get('action_type', '')

    def _get(attr, default=None):
        if hasattr(action, attr):
            return getattr(action, attr)
        return action.get(attr, default)

    if atype == 'play_drink':
        drink_type = _get('drink_card_type', '')
        if drink_type in DRINK_TYPES_ORDER:
            return BASE_PLAY_DRINK + DRINK_TYPES_ORDER.index(drink_type)
        return -1

    elif atype == 'drink_token':
        drink_idx = _get('drink_index', 0)
        if 0 <= drink_idx < 3:
            return BASE_DRINK_TOKEN + drink_idx
        return -1

    elif atype == 'play_rotate':
        direction = _get('rotation_direction', 'clockwise')
        if direction in ROTATION_ORDER:
            return BASE_PLAY_ROTATE + ROTATION_ORDER.index(direction)
        return -1

    elif atype == 'add_tahini':
        tc = _get('tile_coord')
        if tc is None:
            return -1
        tc = tuple(tc) if not isinstance(tc, tuple) else tc
        if tc not in coord_to_idx:
            return -1
        tile_idx = coord_to_idx[tc]
        orient = _get('triangle_orientation', 'left')
        orient_idx = ORIENTATION_ORDER.index(orient) if orient in ORIENTATION_ORDER else 0
        return BASE_ADD_TAHINI + tile_idx * 2 + orient_idx

    elif atype == 'add_hot_sauce':
        tc = _get('tile_coord')
        if tc is None:
            return -1
        tc = tuple(tc) if not isinstance(tc, tuple) else tc
        if tc not in coord_to_idx:
            return -1
        tile_idx = coord_to_idx[tc]
        orient = _get('triangle_orientation', 'left')
        orient_idx = ORIENTATION_ORDER.index(orient) if orient in ORIENTATION_ORDER else 0
        return BASE_ADD_HOT_SAUCE + tile_idx * 2 + orient_idx

    elif atype == 'eat_dish':
        tc = _get('tile_coord')
        if tc is None:
            return -1
        tc = tuple(tc) if not isinstance(tc, tuple) else tc
        if tc not in coord_to_idx:
            return -1
        tile_idx = coord_to_idx[tc]
        resource_cat = get_resource_category(action, board, coord_to_idx)
        discard_type = _get('discard_card_type', '')
        if discard_type not in DISCARD_TYPES_ORDER:
            return -1
        discard_idx = DISCARD_TYPES_ORDER.index(discard_type)
        hot_tokens = _get('num_drink_tokens_for_hot', 0)
        if not (0 <= hot_tokens < NUM_HOT_LEVELS):
            return -1
        sub_idx = (resource_cat * NUM_DISCARD_TYPES * NUM_HOT_LEVELS +
                   discard_idx * NUM_HOT_LEVELS +
                   hot_tokens)
        return BASE_EAT_DISH + tile_idx * EAT_DISH_STRIDE_PER_TILE + sub_idx

    elif atype == 'eat_empty_tile':
        tc = _get('tile_coord')
        if tc is None:
            return -1
        tc = tuple(tc) if not isinstance(tc, tuple) else tc
        if tc not in coord_to_idx:
            return -1
        tile_idx = coord_to_idx[tc]
        discard_type = _get('discard_card_type', '')
        if discard_type not in DISCARD_TYPES_ORDER:
            return -1
        discard_idx = DISCARD_TYPES_ORDER.index(discard_type)
        hot_tokens = _get('num_drink_tokens_for_hot', 0)
        if not (0 <= hot_tokens < NUM_HOT_LEVELS):
            return -1
        sub_idx = discard_idx * NUM_HOT_LEVELS + hot_tokens
        return BASE_EAT_EMPTY_TILE + tile_idx * EAT_EMPTY_STRIDE_PER_TILE + sub_idx

    elif atype == 'end_turn':
        return INDEX_END_TURN

    elif atype == 'discard_redraw':
        return INDEX_DISCARD_REDRAW

    elif atype == 'select_special_cards':
        # Support both old format (kept_card_ids: [str]) and new format (kept_cards: [{id, name}])
        raw_kept = _get('kept_card_ids') or [c['id'] for c in (_get('kept_cards') or []) if isinstance(c, dict)]
        kept = [c if isinstance(c, str) else c.get('id', '') for c in raw_kept]
        indices = sorted(
            SPECIAL_CARD_NAME_TO_IDX[c] for c in kept if c in SPECIAL_CARD_NAME_TO_IDX
        )
        if len(indices) == 2:
            pair = (indices[0], indices[1])
            if pair in DRAFT_PAIR_TO_IDX:
                return BASE_SELECT_DRAFT + DRAFT_PAIR_TO_IDX[pair]
        return -1

    return -1


def fixed_index_to_action_params(index: int) -> Dict[str, Any]:
    """Decode a fixed action index back to action parameters (for debugging).

    Note: For eat_dish with resource_type='tile', this returns the resource
    category but not the specific resource_tile_coord.
    """
    if index >= BASE_SELECT_DRAFT:
        pair_idx = index - BASE_SELECT_DRAFT
        if pair_idx in DRAFT_IDX_TO_PAIR:
            i, j = DRAFT_IDX_TO_PAIR[pair_idx]
            return {
                'action_type': 'select_special_cards',
                'kept_card_ids': [SPECIAL_CARD_IDX_TO_NAME[i], SPECIAL_CARD_IDX_TO_NAME[j]]
            }
        return {'action_type': 'unknown'}

    if index == INDEX_DISCARD_REDRAW:
        return {'action_type': 'discard_redraw'}

    if index == INDEX_END_TURN:
        return {'action_type': 'end_turn'}

    if index >= BASE_EAT_EMPTY_TILE:
        sub = index - BASE_EAT_EMPTY_TILE
        tile_idx = sub // EAT_EMPTY_STRIDE_PER_TILE
        rem = sub % EAT_EMPTY_STRIDE_PER_TILE
        discard_idx = rem // NUM_HOT_LEVELS
        hot = rem % NUM_HOT_LEVELS
        return {
            'action_type': 'eat_empty_tile',
            'tile_idx': tile_idx,
            'discard_card_type': DISCARD_TYPES_ORDER[discard_idx],
            'num_drink_tokens_for_hot': hot
        }

    if index >= BASE_EAT_DISH:
        sub = index - BASE_EAT_DISH
        tile_idx = sub // EAT_DISH_STRIDE_PER_TILE
        rem = sub % EAT_DISH_STRIDE_PER_TILE
        resource_cat = rem // (NUM_DISCARD_TYPES * NUM_HOT_LEVELS)
        rem2 = rem % (NUM_DISCARD_TYPES * NUM_HOT_LEVELS)
        discard_idx = rem2 // NUM_HOT_LEVELS
        hot = rem2 % NUM_HOT_LEVELS
        resource_names = ['card', 'plain_tile', 'hot_tile', 'extra_hot_tile',
                          'tahini_tile', 'hot_tahini_tile', 'extra_hot_tahini_tile']
        return {
            'action_type': 'eat_dish',
            'tile_idx': tile_idx,
            'resource_category': resource_cat,
            'resource_description': resource_names[resource_cat],
            'discard_card_type': DISCARD_TYPES_ORDER[discard_idx],
            'num_drink_tokens_for_hot': hot
        }

    if index >= BASE_ADD_HOT_SAUCE:
        sub = index - BASE_ADD_HOT_SAUCE
        tile_idx = sub // 2
        orient_idx = sub % 2
        return {
            'action_type': 'add_hot_sauce',
            'tile_idx': tile_idx,
            'triangle_orientation': ORIENTATION_ORDER[orient_idx]
        }

    if index >= BASE_ADD_TAHINI:
        sub = index - BASE_ADD_TAHINI
        tile_idx = sub // 2
        orient_idx = sub % 2
        return {
            'action_type': 'add_tahini',
            'tile_idx': tile_idx,
            'triangle_orientation': ORIENTATION_ORDER[orient_idx]
        }

    if index >= BASE_PLAY_ROTATE:
        return {
            'action_type': 'play_rotate',
            'rotation_direction': ROTATION_ORDER[index - BASE_PLAY_ROTATE]
        }

    if index >= BASE_DRINK_TOKEN:
        return {
            'action_type': 'drink_token',
            'drink_index': index - BASE_DRINK_TOKEN
        }

    if index >= BASE_PLAY_DRINK:
        return {
            'action_type': 'play_drink',
            'drink_card_type': DRINK_TYPES_ORDER[index - BASE_PLAY_DRINK]
        }

    return {'action_type': 'unknown'}


class StateEncoder:
    """Encodes game state into neural network input tensor"""

    def __init__(self):
        # Calculate feature dimensions
        self.board_features_per_tile = 16 + MAX_PLAYERS  # dish(7) + hot(1) + hotToken(1) + empty(1) + removed(1) + tahini(1) + canEatEmpty(1) + q(1) + r(1) + hotSauce(1) + reachable_per_player(6)
        self.player_features = 11  # score, hand_size, hand_size_modifier, base_hand_size, super_hot_count, super_hot_value, eaten_count, tasted_all, is_current, turn_distance, water_refilled_this_turn
        self.hand_features = len(CARD_TYPES)  # count of each card type
        self.drinks_features = len(DRINK_TYPES) * 2  # count and total tokens for each drink type
        self.dish_counts_features = len(DISH_TYPES)  # count of each dish eaten
        self.special_cards_features = NUM_SPECIAL_CARDS  # 18-bit binary vector

        # Total feature size per player
        self.features_per_player = (
            self.player_features +
            self.hand_features +
            self.drinks_features +
            self.dish_counts_features +
            self.special_cards_features
        )

        # Draft context: which cards were dealt to the current player this draft step
        self.draft_dealt_features = NUM_SPECIAL_CARDS  # 19-bit one-hot over the dealt cards

        # Total state size
        self.board_features_size = BOARD_SIZE * self.board_features_per_tile
        self.players_features_size = MAX_PLAYERS * self.features_per_player
        self.deck_features_size = 0  # removed: AI only sees deck size (in meta), not composition or other hands
        self.meta_features_size = 2  # num_players, cards_remaining

        self.total_state_size = (
            self.board_features_size +
            self.players_features_size +
            self.meta_features_size +
            self.draft_dealt_features
        )

    def encode_state(self, game_state: Dict[str, Any], current_player_idx: int) -> np.ndarray:
        """
        Encode game state into a flat feature vector

        Args:
            game_state: Game state dictionary
            current_player_idx: Index of current player (for perspective)

        Returns:
            numpy array of shape (total_state_size,)
        """
        features = []

        # Compute reachability sets in rotated player order
        reachable_data = game_state.get('reachable_by_player', [])
        num_players = game_state['num_players']
        player_order = [(current_player_idx + i) % num_players for i in range(num_players)]
        reachable_sets = []
        for player_idx in player_order:
            if player_idx < len(game_state['players']):
                position = game_state['players'][player_idx].get('position', player_idx)
                if position < len(reachable_data):
                    reachable_sets.append(set(tuple(c) for c in reachable_data[position]))
                else:
                    reachable_sets.append(set())
            else:
                reachable_sets.append(set())
        while len(reachable_sets) < MAX_PLAYERS:
            reachable_sets.append(set())

        # 1. Encode board (61 tiles) with per-player reachability
        board_features = self._encode_board(game_state['board'], reachable_sets)
        features.append(board_features)

        # 2. Encode all players (rotate so current player is first)
        players_features = self._encode_players(
            game_state['players'],
            current_player_idx,
            game_state['num_players']
        )
        features.append(players_features)

        # 3. Meta features
        deck = game_state.get('deck', {})
        cards_remaining = deck.get('cards_remaining', deck.get('cardsRemaining', 0))
        meta_features = np.array([game_state['num_players'], cards_remaining / 60.0], dtype=np.float32)
        features.append(meta_features)

        # 5. Draft context: which cards were dealt to the current player this step
        draft_features = np.zeros(self.draft_dealt_features, dtype=np.float32)
        for card_id in game_state.get('draft_dealt_cards', []):
            idx = SPECIAL_CARD_NAME_TO_IDX.get(card_id)
            if idx is not None:
                draft_features[idx] = 1.0
        features.append(draft_features)

        # Concatenate all features
        state_vector = np.concatenate(features)

        return state_vector.astype(np.float32)

    def _encode_board(self, board: List[Dict], reachable_sets: List[set] = None) -> np.ndarray:
        """Encode board state (61 tiles) with per-player reachability"""
        features = np.zeros(self.board_features_size, dtype=np.float32)

        for i, tile in enumerate(board):
            offset = i * self.board_features_per_tile

            # Dish type (one-hot encoding)
            if tile['dish'] and tile['dish'] in DISH_TYPES:
                dish_idx = DISH_TYPES.index(tile['dish'])
                features[offset + dish_idx] = 1.0

            # Tile properties
            features[offset + 7] = float(tile.get('hot', False))
            features[offset + 8] = float(tile.get('hotToken', False))
            features[offset + 9] = float(tile.get('empty', False))
            features[offset + 10] = float(tile.get('removed', False))
            features[offset + 11] = float(tile.get('tahini', 0)) / 5.0  # Normalize
            features[offset + 12] = float(tile.get('canEatEmpty', False))

            # Hex coordinates (normalized)
            features[offset + 13] = tile['q'] / 4.0
            features[offset + 14] = tile['r'] / 4.0

            features[offset + 15] = float(tile.get('hotSauce', tile.get('hot_sauce', 0))) / 5.0

            # Per-player reachability (rotated: slot 0 = current player)
            if reachable_sets:
                tile_coord = (tile['q'], tile['r'])
                for p in range(MAX_PLAYERS):
                    features[offset + 16 + p] = 1.0 if tile_coord in reachable_sets[p] else 0.0

        return features

    def _encode_players(self, players: List[Dict], current_idx: int, num_players: int) -> np.ndarray:
        """
        Encode all players (current player first, then others in order)
        Note: After rotation, current player is at index 0
        This matters for _encode_deck which needs to know which player to skip
        """
        features = np.zeros(self.players_features_size, dtype=np.float32)

        # Rotate player order so current player is first
        player_order = [(current_idx + i) % num_players for i in range(num_players)]

        for i, player_idx in enumerate(player_order):
            if player_idx >= len(players):
                continue  # Empty slot

            player = players[player_idx]
            offset = i * self.features_per_player

            # Basic player stats
            features[offset + 0] = player['score'] / 100.0  # Normalize
            features[offset + 1] = len(player['hand']) / MAX_HAND_SIZE
            features[offset + 2] = (player.get('handSizeModifier', player.get('hand_size_modifier', 0)) + 5) / 10.0  # Shift and normalize
            features[offset + 3] = player.get('baseHandSize', player.get('base_hand_size', 5)) / 10.0
            features[offset + 4] = player.get('superHotCount', player.get('super_hot_count', 0)) / 10.0
            features[offset + 5] = player.get('superHotValue', player.get('super_hot_value', 2)) / 10.0
            features[offset + 6] = len(player.get('eaten', [])) / 20.0  # Normalize
            features[offset + 7] = float(player.get('tastedAllTypes', False))
            features[offset + 8] = 1.0 if i == 0 else 0.0  # is_current_player
            features[offset + 9] = i / max(1, num_players - 1)  # turn_distance (0.0=current, 1.0=last)
            features[offset + 10] = float(player.get('waterRefilledThisTurn', player.get('water_refilled_this_turn', False)))

            # Hand composition (only for current player)
            hand_offset = offset + self.player_features
            if i == 0:  # Current player
                for card in player['hand']:
                    card_type = card.get('type', card.get('name', ''))
                    if 'Injera' in card_type:
                        features[hand_offset + 0] += 1.0 / MAX_HAND_SIZE
                    elif 'Rotate' in card_type:
                        features[hand_offset + 1] += 1.0 / MAX_HAND_SIZE
                    elif 'Beer' in card_type:
                        features[hand_offset + 2] += 1.0 / MAX_HAND_SIZE
                    elif 'Water' in card_type:
                        features[hand_offset + 3] += 1.0 / MAX_HAND_SIZE
                    elif 'Coffee' in card_type:
                        features[hand_offset + 4] += 1.0 / MAX_HAND_SIZE
                    elif 'Tahini' in card_type:
                        features[hand_offset + 5] += 1.0 / MAX_HAND_SIZE
                    elif 'Hot Sauce' in card_type or 'HotSauce' in card_type:
                        features[hand_offset + 6] += 1.0 / MAX_HAND_SIZE

            # Drinks
            drinks_offset = hand_offset + len(CARD_TYPES)
            for drink in player.get('drinks', []):
                drink_type = drink['type']
                if drink_type in DRINK_TYPES:
                    drink_idx = DRINK_TYPES.index(drink_type)
                    features[drinks_offset + drink_idx * 2] += 1.0 / 3.0  # Count (max 3)
                    features[drinks_offset + drink_idx * 2 + 1] += drink['tokens'] / 9.0  # Total tokens (max 3*3)

            # Dish counts
            dish_counts_offset = drinks_offset + len(DRINK_TYPES) * 2
            dish_counts = player.get('dishCounts', player.get('dish_counts', {}))
            for dish_type in DISH_TYPES:
                if dish_type in dish_counts:
                    dish_idx = DISH_TYPES.index(dish_type)
                    features[dish_counts_offset + dish_idx] = dish_counts[dish_type] / 7.0  # Max 7

            # Special cards (18-bit binary vector) — only for current player (secret from others)
            sc_offset = dish_counts_offset + len(DISH_TYPES)
            if i == 0:
                special_cards = player.get('specialCards', player.get('special_cards', []))
                for card_item in special_cards:
                    # JS sends objects {id, name, description}; Python sends plain ints
                    raw = card_item['id'] if isinstance(card_item, dict) else card_item
                    card_idx = SPECIAL_CARD_NAME_TO_IDX.get(raw, raw) if isinstance(raw, str) else int(raw)
                    if 0 <= card_idx < NUM_SPECIAL_CARDS:
                        features[sc_offset + card_idx] = 1.0

        return features

    def _encode_deck(self, deck: Dict, players: List[Dict]) -> np.ndarray:
        """
        Unused — kept for reference. AI now only sees deck size (via meta features).
        Other players' hand types are also not exposed; only hand COUNT is encoded per player.
        """
        features = np.zeros(self.deck_features_size, dtype=np.float32)

        # Only encode other players' hand cards (current player can't see these)
        composition = {}

        # Add cards from OTHER players' hands (current player can't see these)
        # Note: In encode_state, current player is first (index 0) after rotation
        # So we skip the first player and count cards from others
        for player_idx, player in enumerate(players):
            # Skip current player (they already know their own hand)
            if player_idx == 0:
                continue

            # Add this player's hand cards to the "unseen" pool
            for card in player.get('hand', []):
                card_type = card.get('type', card.get('name', ''))

                # Normalize card type names
                if 'Injera' in card_type:
                    card_key = 'Injera'
                elif 'Rotate' in card_type:
                    card_key = 'Rotate'
                elif 'Beer' in card_type:
                    card_key = 'Beer'
                elif 'Water' in card_type:
                    card_key = 'Water'
                elif 'Coffee' in card_type:
                    card_key = 'Coffee'
                elif 'Tahini' in card_type:
                    card_key = 'Tahini'
                else:
                    continue  # Unknown card type

                # Add to composition
                if card_key in composition:
                    composition[card_key] += 1
                else:
                    composition[card_key] = 1

        # Encode the combined unseen cards
        for card_type in CARD_TYPES:
            if card_type in composition:
                features[CARD_TYPES.index(card_type)] = composition[card_type] / 50.0  # Max ~50 unseen cards

        return features

    def encode_action_mask(self, valid_actions, board: List[Dict] = None) -> np.ndarray:
        """
        Create fixed action mask for valid actions.

        Each legal action is mapped to its fixed index in the ACTION_SPACE_SIZE-dim
        vector. The mask has 1.0 at each valid fixed index and 0.0 elsewhere.

        Args:
            valid_actions: List of Action objects (from ActionGenerator)
            board: Board data list (list of tile dicts). Required for correct mapping.

        Returns:
            Binary mask array of shape (ACTION_SPACE_SIZE,)
        """
        mask = np.zeros(ACTION_SPACE_SIZE, dtype=np.float32)

        if board is None:
            # Fallback: can't compute fixed indices without board
            return mask

        coord_to_idx = build_coord_to_board_idx(board)

        for action in valid_actions:
            idx = action_to_fixed_index(action, coord_to_idx, board)
            if 0 <= idx < ACTION_SPACE_SIZE:
                mask[idx] = 1.0

        return mask

    def get_state_shape(self) -> Tuple[int]:
        """Get the shape of the state tensor"""
        return (self.total_state_size,)

    def get_action_space_size(self) -> int:
        """Get fixed action space size"""
        return ACTION_SPACE_SIZE


# Example usage
if __name__ == "__main__":
    encoder = StateEncoder()
    print(f"State size: {encoder.total_state_size}")
    print(f"  - Board: {encoder.board_features_size}")
    print(f"  - Players: {encoder.players_features_size}")
    print(f"  - Deck: {encoder.deck_features_size}")
    print(f"  - Meta: {encoder.meta_features_size}")
    print(f"Action space: {encoder.get_action_space_size()}")
    print(f"\nFixed action space layout ({ACTION_SPACE_SIZE} slots):")
    print(f"  [{BASE_PLAY_DRINK}-{BASE_PLAY_DRINK+2}]: play_drink (3)")
    print(f"  [{BASE_DRINK_TOKEN}-{BASE_DRINK_TOKEN+2}]: drink_token (3)")
    print(f"  [{BASE_PLAY_ROTATE}-{BASE_PLAY_ROTATE+1}]: play_rotate (2)")
    print(f"  [{BASE_ADD_TAHINI}-{BASE_ADD_TAHINI+BOARD_SIZE*2-1}]: add_tahini ({BOARD_SIZE*2})")
    print(f"  [{BASE_EAT_DISH}-{BASE_EAT_DISH+BOARD_SIZE*EAT_DISH_STRIDE_PER_TILE-1}]: eat_dish ({BOARD_SIZE*EAT_DISH_STRIDE_PER_TILE})")
    print(f"  [{BASE_EAT_EMPTY_TILE}-{BASE_EAT_EMPTY_TILE+BOARD_SIZE*EAT_EMPTY_STRIDE_PER_TILE-1}]: eat_empty_tile ({BOARD_SIZE*EAT_EMPTY_STRIDE_PER_TILE})")
    print(f"  [{INDEX_END_TURN}]: end_turn (1)")
