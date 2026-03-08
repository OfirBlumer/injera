"""
Injera Board Game - A strategic board game with hexagonal tiles
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Set
import random
import math


# ============================================================================
# ENUMS AND CONSTANTS
# ============================================================================

class DishType(Enum):
    """7 vegan Ethiopian dish types"""
    # Non-hot dishes (1 point, +15 bonus for eating all 7 tiles of one type)
    GOMEN = "Gomen"              # Collard greens
    MISIR_WOT = "Misir Wot"      # Red lentils
    SHIRO = "Shiro"              # Chickpea stew
    
    # Medium-hot dishes (2 points, no bonus)
    KIK_ALICHA = "Kik Alicha"    # Yellow split peas
    AZIFA = "Azifa"              # Lentil salad
    TIKEL_GOMEN = "Tikel Gomen"  # Cabbage with carrots
    
    # Super-hot dish (center only, progressive scoring)
    BERBERE_MISIR = "Berbere Misir"  # Very spicy red lentils
    
    @staticmethod
    def get_non_hot():
        return [DishType.MISIR_WOT, DishType.GOMEN, DishType.SHIRO]
    
    @staticmethod
    def get_medium_hot():
        return [DishType.KIK_ALICHA, DishType.AZIFA, DishType.TIKEL_GOMEN]
    
    @staticmethod
    def get_super_hot():
        return DishType.BERBERE_MISIR


class CardType(Enum):
    INJERA = "Clean Injera"
    DRINK = "Drink"
    TAHINI = "Tahini"
    ROTATE = "Rotate"
    HOT_SAUCE = "Hot Sauce"


class DrinkType(Enum):
    COFFEE = "Coffee"  # +1 point per token, +1 hand size when finished
    BEER = "Beer"      # +3 points per token, -1 hand size when finished
    WATER = "Water"    # 0 points, just for eating hot dishes


# ============================================================================
# HEX COORDINATE SYSTEM (Axial Coordinates)
# ============================================================================

@dataclass(frozen=True)
class HexCoord:
    """Axial coordinates for hexagonal grid (q, r)"""
    q: int  # column
    r: int  # row
    
    def __add__(self, other):
        return HexCoord(self.q + other.q, self.r + other.r)
    
    def neighbors(self) -> List['HexCoord']:
        """Returns all 6 neighboring hex coordinates"""
        directions = [
            HexCoord(1, 0),   HexCoord(1, -1),  HexCoord(0, -1),
            HexCoord(-1, 0),  HexCoord(-1, 1),  HexCoord(0, 1)
        ]
        return [self + d for d in directions]
    
    def distance(self, other: 'HexCoord') -> int:
        """Manhattan distance in hex grid"""
        return (abs(self.q - other.q) 
                + abs(self.q + self.r - other.q - other.r)
                + abs(self.r - other.r)) // 2


# ============================================================================
# TILE AND BOARD
# ============================================================================

@dataclass
class HexTile:
    """Represents a single hexagonal tile on the board"""
    coord: HexCoord
    has_injera: bool = True
    dish_type: Optional[DishType] = None
    tahini_tokens: int = 0
    hot_sauce_tokens: int = 0
    is_hot: bool = False  # Whether the dish is hot
    has_hot_token: bool = False  # Hot token left after eating hot dish
    is_removed: bool = False  # Tile completely removed from board
    
    @property
    def is_empty(self) -> bool:
        """Tile is empty if dish has been eaten but tile still exists"""
        return self.dish_type is None and not self.is_removed
    
    @property
    def dish_value(self) -> int:
        """Base value + tahini tokens"""
        if self.is_empty or self.is_removed:
            return 0
        return 1 + self.tahini_tokens
    
    def eat_dish(self) -> Optional[DishType]:
        """Remove dish from tile, keep hot token if it was hot"""
        if self.is_empty or self.is_removed:
            return None
        dish = self.dish_type
        was_hot = self.is_hot
        self.dish_type = None
        self.is_hot = False
        if was_hot:
            self.has_hot_token = True  # Hot token stays on empty tile
        self.hot_sauce_tokens = 0  # Hot sauce does not carry over to revealed empty tile
        return dish
    
    def use_injera(self):
        """Use this tile's injera (removes tile completely from board)"""
        self.has_injera = False
        self.is_removed = True
        self.dish_type = None
        self.has_hot_token = False


class Board:
    """Hexagonal game board"""
    
    def __init__(self, radius: int = 5):
        """Create a hexagonal board with given radius (tiles per edge)"""
        self.radius = radius
        self.tiles: dict[HexCoord, HexTile] = {}
        self._initialize_board()
    
    def _initialize_board(self):
        """Generate hexagonal grid of tiles"""
        for q in range(-self.radius + 1, self.radius):
            r1 = max(-self.radius + 1, -q - self.radius + 1)
            r2 = min(self.radius - 1, -q + self.radius - 1)
            for r in range(r1, r2 + 1):
                coord = HexCoord(q, r)
                self.tiles[coord] = HexTile(coord=coord)
    
    def get_tile(self, coord: HexCoord) -> Optional[HexTile]:
        """Get tile at coordinate"""
        return self.tiles.get(coord)
    
    def get_neighbors(self, coord: HexCoord) -> List[HexTile]:
        """Get all neighboring tiles"""
        return [self.tiles[n] for n in coord.neighbors() if n in self.tiles]
    
    def is_edge_tile(self, coord: HexCoord) -> bool:
        """Check if tile is on the edge of the board"""
        return coord.distance(HexCoord(0, 0)) >= self.radius - 1
    
    def get_hexagon_cluster(self, center: HexCoord) -> List[HexCoord]:
        """Get a cluster of 7 hexagons (center + 6 neighbors)"""
        cluster = [center]
        cluster.extend(center.neighbors())
        # Filter to only include tiles that exist on the board
        return [c for c in cluster if c in self.tiles]
    
    def place_dishes(self, num_players: int):
        """Place dishes in corner and center hexagons with symmetric alternating pattern"""
        # Corner positions (6 vertices around the board)
        corner_centers = [
            HexCoord(3, 0),    # East
            HexCoord(0, 3),    # South-East  
            HexCoord(-3, 3),   # South-West
            HexCoord(-3, 0),   # West
            HexCoord(0, -3),   # North-West
            HexCoord(3, -3),   # North-East
        ]
        center_position = HexCoord(0, 0)
        
        # Get dish types
        non_hot = DishType.get_non_hot()
        medium_hot = DishType.get_medium_hot()
        super_hot = DishType.get_super_hot()
        
        # Assign center dish (super-hot, always hot)
        center_cluster = self.get_hexagon_cluster(center_position)
        for coord in center_cluster:
            if coord in self.tiles:
                self.tiles[coord].dish_type = super_hot
                self.tiles[coord].is_hot = True  # Super-hot is always hot
        
        # Assign corner dishes alternating: non-hot, medium-hot, non-hot, medium-hot, ...
        for i, corner_center in enumerate(corner_centers):
            cluster = self.get_hexagon_cluster(corner_center)
            
            # Alternate between non-hot and medium-hot
            if i % 2 == 0:
                # Even positions (0, 2, 4): non-hot
                dish_type = non_hot[i // 2]  # 0->0, 2->1, 4->2
                is_hot = False
            else:
                # Odd positions (1, 3, 5): medium-hot
                dish_type = medium_hot[i // 2]  # 1->0, 3->1, 5->2
                is_hot = True  # Medium-hot dishes are hot
            
            for coord in cluster:
                if coord in self.tiles:
                    self.tiles[coord].dish_type = dish_type
                    self.tiles[coord].is_hot = is_hot
        
        # Leave remaining tiles empty - they already have injera
        for tile in self.tiles.values():
            if tile.dish_type is None:
                tile.dish_type = None
                tile.has_injera = True
    
    def can_eat_empty_tile(self, coord: HexCoord) -> bool:
        """
        Check if an empty tile can be eaten.
        Rule: Must have at least 2 adjacent positions that are either:
          - Off the board (never existed), OR
          - Removed tiles (eaten empty injera)
        """
        tile = self.get_tile(coord)
        if not tile or not tile.is_empty or tile.is_removed:
            return False
        
        # Count how many neighbor positions are "nothing" (off-board or removed)
        empty_neighbors = 0
        for neighbor_coord in coord.neighbors():
            if neighbor_coord not in self.tiles:
                # Position is off the board
                empty_neighbors += 1
            else:
                neighbor_tile = self.tiles[neighbor_coord]
                if neighbor_tile.is_removed:
                    # Tile was removed (eaten)
                    empty_neighbors += 1
        
        return empty_neighbors >= 2
    
    def rotate_board(self, clockwise: bool = True):
        """
        Rotate the entire board by 60 degrees.
        This rotates all tile coordinates around the center.
        """
        direction = 1 if clockwise else -1
        
        # Rotation matrix for hexagonal coordinates (60 degrees)
        # Clockwise: (q, r) -> (-r, q+r)
        # Counter-clockwise: (q, r) -> (q+r, -q)
        
        new_tiles = {}
        for coord, tile in self.tiles.items():
            if clockwise:
                new_coord = HexCoord(-coord.r, coord.q + coord.r)
            else:
                new_coord = HexCoord(coord.q + coord.r, -coord.q)
            
            # Update tile's coordinate
            tile.coord = new_coord
            new_tiles[new_coord] = tile
        
        self.tiles = new_tiles
    
    def get_reachable_tiles(self, player_position: int, num_players: int) -> Set[HexCoord]:
        """
        Get tiles reachable by a player from their position.
        Players sit at vertices of a FLAT-TOP hexagon (edges on top/bottom).
        
        Flat-top hexagon has vertices at: 0Â°, 60Â°, 120Â°, 180Â°, 240Â°, 300Â° (every 60Â°)
        In canvas: 0Â°=right, 60Â°=bottom-right, 120Â°=bottom-left, 180Â°=left, 240Â°=top-left, 300Â°=top-right
        
        Reachable areas (each player gets one half):
        - 0Â° (right): q >= 0
        - 60Â° (bottom-right): q + r >= 0  
        - 120Â° (bottom-left): r >= 0
        - 180Â° (left): q <= 0
        - 240Â° (top-left): q + r <= 0
        - 300Â° (top-right): r <= 0
        """
        reachable = set()
        
        # Flat-top hexagon vertices and their reachable halves
        vertex_conditions = {
            0:   lambda q, r: q >= 0,           # Right
            60:  lambda q, r: q + r >= 0,       # Bottom-right
            120: lambda q, r: r >= 0,           # Bottom-left
            180: lambda q, r: q <= 0,           # Left
            240: lambda q, r: q + r <= 0,       # Top-left
            300: lambda q, r: r <= 0            # Top-right
        }
        
        # Assign players to vertices
        if num_players == 2:
            player_vertices = [300, 120]  # P1: top-right, P2: bottom-left (opposite)
        elif num_players == 3:
            player_vertices = [300, 60, 180]  # P1: top-right, P2: bottom-right, P3: left (120Â° apart)
        elif num_players == 4:
            # Symmetric: two pairs across from each other
            player_vertices = [300, 0, 120, 180]  # P1: top-right, P2: right, P3: bottom-left, P4: left
        elif num_players == 5:
            player_vertices = [300, 0, 60, 120, 240]  # skip 180Â° (left)
        elif num_players == 6:
            player_vertices = [300, 0, 60, 120, 180, 240]  # all vertices
        
        vertex_angle = player_vertices[player_position]
        condition = vertex_conditions[vertex_angle]
        
        for coord, tile in self.tiles.items():
            if condition(coord.q, coord.r):
                reachable.add(coord)
        
        return reachable
    
    def count_remaining_dishes(self) -> int:
        """Count how many dishes are left on the board"""
        return sum(1 for tile in self.tiles.values() if not tile.is_empty)
    
    def __len__(self):
        return len(self.tiles)
    
    def visualize(self, reachable_coords: Set[HexCoord] = None) -> str:
        """
        Create a text-based visualization of the hex board
        reachable_coords: optional set of coordinates to highlight
        """
        if reachable_coords is None:
            reachable_coords = set()
        
        lines = []
        lines.append("\n" + "=" * 80)
        lines.append("INJERA BOARD".center(80))
        lines.append("=" * 80)
        
        # Find the range of coordinates
        min_q = min(t.coord.q for t in self.tiles.values())
        max_q = max(t.coord.q for t in self.tiles.values())
        min_r = min(t.coord.r for t in self.tiles.values())
        max_r = max(t.coord.r for t in self.tiles.values())
        
        # Print row by row
        for r in range(min_r, max_r + 1):
            # Calculate indent for this row (makes it look hexagonal)
            indent = abs(r) * 2
            line = " " * indent
            
            for q in range(min_q, max_q + 1):
                coord = HexCoord(q, r)
                tile = self.get_tile(coord)
                
                if tile:
                    # Choose symbol based on tile state
                    if tile.is_empty:
                        symbol = "[ ]"  # Empty tile
                    else:
                        # Show first letter of dish type
                        dish_letter = tile.dish_type.value[0]
                        if tile.is_hot:
                            symbol = f"[{dish_letter}*]"  # Hot dish (asterisk)
                        else:
                            symbol = f"[{dish_letter}Â·]"  # Normal dish (dot)
                        
                        # Add tahini indicator
                        if tile.tahini_tokens > 0:
                            symbol = f"[{dish_letter}{tile.tahini_tokens}]"
                    
                    # Highlight reachable tiles
                    if coord in reachable_coords:
                        symbol = f">{symbol[1:-1]}<"
                    
                    line += symbol + " "
            
            lines.append(line)
        
        # Add legend
        lines.append("\n" + "-" * 80)
        lines.append("LEGEND:")
        lines.append("  [XÂ·] = Dish (X=first letter), Â· = normal temperature")
        lines.append("  [X*] = Hot dish (requires drink)")
        lines.append("  [X2] = Dish with 2 tahini tokens")
        lines.append("  [ ] = Empty tile (dish eaten)")
        lines.append("  >X< = Reachable by current player")
        lines.append("-" * 80)
        
        # Show dish types
        lines.append("\nDISH TYPES:")
        for dish_type in DishType:
            count = sum(1 for t in self.tiles.values() 
                       if not t.is_empty and t.dish_type == dish_type)
            lines.append(f"  {dish_type.value[0]} = {dish_type.value} ({count} remaining)")
        
        lines.append("=" * 80 + "\n")
        
        return "\n".join(lines)


# ============================================================================
# CARDS
# ============================================================================

@dataclass
class Card:
    """Base card class"""
    card_type: CardType
    name: str


@dataclass
class InjeraCard(Card):
    """Clean injera card for eating dishes"""
    def __init__(self):
        super().__init__(CardType.INJERA, "Clean Injera")


@dataclass
class DrinkCard(Card):
    """Drink card with tokens and abilities"""
    drink_type: DrinkType
    tokens: int = 3  # Default 3 uses
    
    def __init__(self, drink_type: DrinkType, tokens: int = 3):
        super().__init__(CardType.DRINK, drink_type.value)
        self.drink_type = drink_type
        self.tokens = tokens


@dataclass
class TahiniCard(Card):
    """Tahini card to add value tokens to tiles"""
    tokens: int = 1  # Number of tahini tokens this card provides (per tile in triangle)
    
    def __init__(self, tokens: int = 1):
        super().__init__(CardType.TAHINI, "Tahini")
        self.tokens = tokens


@dataclass
class RotateCard(Card):
    """Card to rotate the board/access different tiles"""
    def __init__(self):
        super().__init__(CardType.ROTATE, "Rotate Injera")


@dataclass
class HotSauceCard(Card):
    """Hot sauce card to add hotness tokens to tiles"""
    def __init__(self):
        super().__init__(CardType.HOT_SAUCE, "Add Hot Sauce")


# ============================================================================
# DECK
# ============================================================================

class Deck:
    """Manages the deck of cards"""
    
    def __init__(self):
        self.cards: List[Card] = []
        self.discard: List[Card] = []
        self._initialize_deck()
    
    def _initialize_deck(self):
        """Create the initial deck composition"""
        # 30 Injera cards
        for _ in range(30):
            self.cards.append(InjeraCard())

        # 5 Hot Sauce cards
        for _ in range(5):
            self.cards.append(HotSauceCard())
        
        # 3 of each drink type (3 tokens each)
        for _ in range(3):
            self.cards.append(DrinkCard(DrinkType.COFFEE, tokens=3))
            self.cards.append(DrinkCard(DrinkType.BEER, tokens=3))
            self.cards.append(DrinkCard(DrinkType.WATER, tokens=3))
        
        # 6 Tahini cards
        for _ in range(6):
            self.cards.append(TahiniCard(tokens=1))
        
        # 10 Rotate cards
        for _ in range(10):
            self.cards.append(RotateCard())
        
        # Shuffle the deck
        random.shuffle(self.cards)
    
    def draw(self) -> Optional[Card]:
        """Draw one card from the deck"""
        if len(self.cards) == 0:
            # Reshuffle discard pile into deck
            if len(self.discard) == 0:
                return None  # No cards left at all
            self.cards = self.discard.copy()
            self.discard = []
            random.shuffle(self.cards)
        
        return self.cards.pop() if self.cards else None
    
    def draw_multiple(self, count: int) -> List[Card]:
        """Draw multiple cards, reshuffling discard pile as needed"""
        drawn = []
        for _ in range(count):
            card = self.draw()
            if card:
                drawn.append(card)
            else:
                # draw() returns None only when both deck and discard are empty
                break
        return drawn
    
    def add_to_discard(self, card: Card):
        """Add a card to the discard pile"""
        self.discard.append(card)
    
    def cards_remaining(self) -> int:
        """Total cards remaining (deck + discard)"""
        return len(self.cards) + len(self.discard)


# ============================================================================
# ACTIVE DRINK (on the table)
# ============================================================================

@dataclass
class ActiveDrink:
    """A drink that has been played and is active"""
    drink_type: DrinkType
    tokens_remaining: int
    
    def use_token(self) -> bool:
        """Use one token, return True if successful"""
        if self.tokens_remaining > 0:
            self.tokens_remaining -= 1
            return True
        return False
    
    @property
    def is_finished(self) -> bool:
        return self.tokens_remaining <= 0


# ============================================================================
# PLAYER
# ============================================================================

@dataclass
class Player:
    """Represents a player in the game"""
    name: str
    position: int  # 0-3 for seat around the board
    hand: List[Card] = field(default_factory=list)
    score: int = 0
    eaten_dishes: List[DishType] = field(default_factory=list)
    active_drinks: List[ActiveDrink] = field(default_factory=list)
    hand_size_modifier: int = 0  # Reserved (unused after drink rule change)
    super_hot_eaten_count: int = 0  # Track how many super-hot tiles eaten (flat scoring: always 3)
    base_hand_size: int = 5  # Set based on num_players: 2-3: 5, 4-5: 4, 6: 3
    pending_beer_penalty: int = 0  # Reduces refill target by 1 for next end-of-turn draw (one-time)
    tahini_consumed: int = 0  # Total tahini tokens eaten
    hot_dishes_eaten: int = 0  # Hot dish tiles eaten (not berbere)
    total_hot_eaten: int = 0  # All hot dishes including berbere
    special_cards: List[int] = field(default_factory=list)  # Card indices (0-17) held
    
    @property
    def max_hand_size(self) -> int:
        """Current maximum hand size"""
        return self.base_hand_size + self.hand_size_modifier
    
    def get_super_hot_value(self) -> int:
        """Get value of super-hot (Berbere) dish - flat 3 points"""
        return 3
    
    def count_dish_type(self, dish_type: DishType) -> int:
        """Count how many tiles of a specific dish type have been eaten"""
        return self.eaten_dishes.count(dish_type)
    
    def has_tasted_all_dish_types(self) -> bool:
        """Check if player has eaten at least 1 of each dish type"""
        all_types = list(DishType)
        return all(any(d == dt for d in self.eaten_dishes) for dt in all_types)
    
    def draw_card(self, card: Card):
        """Add card to hand"""
        self.hand.append(card)
    
    def play_card(self, card_index: int) -> Optional[Card]:
        """Remove and return card from hand"""
        if 0 <= card_index < len(self.hand):
            return self.hand.pop(card_index)
        return None
    
    def play_drink_card(self, drink_card: DrinkCard):
        """Play a drink card - add it to active drinks"""
        active = ActiveDrink(drink_type=drink_card.drink_type, tokens_remaining=drink_card.tokens)
        self.active_drinks.append(active)
    def drink_token(self, drink_index: int, deck) -> tuple[int, int]:
        """
        Drink one token from specified active drink.
        Returns (points earned, cards drawn from Water refill).
        Deck parameter needed for Water's special ability.
        """
        if 0 <= drink_index < len(self.active_drinks):
            drink = self.active_drinks[drink_index]
            if drink.use_token():
                # Award points based on drink type
                points = 0
                cards_drawn = 0
                if drink.drink_type == DrinkType.COFFEE:
                    points = 1
                elif drink.drink_type == DrinkType.BEER:
                    points = 2
                # Water gives 0 points
                
                # Check if drink is now finished
                if drink.is_finished:
                    # Coffee: draw 1 bonus card immediately (one-time, not permanent)
                    if drink.drink_type == DrinkType.COFFEE:
                        cards_drawn = 1
                    # Beer: next end-of-turn refill is to hand_size - 1 (one-time, not permanent)
                    elif drink.drink_type == DrinkType.BEER:
                        self.pending_beer_penalty += 1
                    # Water refill handled by game engine
                    # (first Water per turn = refill, second+ = end turn)

                return points, cards_drawn
        return 0, 0
    
    def has_active_drink(self) -> bool:
        """Check if player has any active drinks"""
        return any(not d.is_finished for d in self.active_drinks)
    
    def can_eat_hot_dish(self) -> bool:
        """Check if player can eat a hot dish (has active drink with tokens)"""
        return any(not d.is_finished for d in self.active_drinks)
    
    def eat_dish(self, dish_type: DishType, base_value: int, tahini_tokens: int = 0) -> int:
        """
        Record eating a dish and calculate points.
        Returns total points earned (including bonuses).
        """
        # Calculate base points
        points = base_value + tahini_tokens

        # Track tahini consumed
        if tahini_tokens > 0:
            self.tahini_consumed += tahini_tokens

        # Track super-hot progression
        if dish_type == DishType.BERBERE_MISIR:
            self.super_hot_eaten_count += 1
            self.total_hot_eaten += 1
        elif dish_type in DishType.get_medium_hot():
            self.hot_dishes_eaten += 1
            self.total_hot_eaten += 1

        # Add to eaten list
        self.eaten_dishes.append(dish_type)

        # Check for completion bonus: +15 if all 7 tiles of one non-hot dish eaten
        if dish_type in DishType.get_non_hot():
            if self.count_dish_type(dish_type) == 7:
                points += 15

        self.score += points
        return points
    
    def get_variety_bonus(self) -> int:
        """
        Calculate variety bonus: 2 points per unique dish type eaten.
        This is calculated at the end of the game.
        """
        unique_types = len(set(self.eaten_dishes))
        return 2 * unique_types
    
    def show_hand(self) -> str:
        """Display player's hand"""
        return f"{self.name}'s hand: " + ", ".join([f"{i}: {c.name}" for i, c in enumerate(self.hand)])


# ============================================================================
# MAIN - Testing the structure
# ============================================================================

if __name__ == "__main__":
    print("=== Injera Board Game - Testing Core Structure ===\n")
    
    # Create board
    board = Board(radius=5)
    print(f"Board created with {len(board)} tiles")
    
    # Place dishes
    board.place_dishes(num_players=4)
    print(f"Dishes placed: {board.count_remaining_dishes()} dishes on board\n")
    
    # Create some cards
    cards = [
        InjeraCard(),
        DrinkCard(DrinkType.COFFEE),
        TahiniCard(),
        RotateCard()
    ]
    
    # Create a player
    player = Player(name="Player 1", position=0)
    for card in cards:
        player.draw_card(card)
    
    print(player.show_hand())
    print(f"\nPlayer score: {player.score}")
    print(f"Dishes eaten: {len(player.eaten_dishes)}")
    
    print("\nâœ“ Core structure is working!")
