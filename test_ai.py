"""
Test Script - Verify that the AI system is working correctly
"""

import sys
import os

# Fix Windows emoji support
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.game_state import GameState, PlayerState, TileState, DeckState, CardState
from engine.action_generator import ActionGenerator


def create_test_game_state():
    """Create a simple test game state"""

    # Create a minimal board with a few tiles
    board = [
        TileState(q=0, r=0, dish="Gomen", hot=False, empty=False),
        TileState(q=1, r=0, dish="Shiro", hot=False, empty=False),
        TileState(q=0, r=1, dish="Berbere Misir", hot=True, empty=False),
        TileState(q=-1, r=0, dish=None, empty=True, can_eat_empty=False),
    ]

    # Create test players
    players = [
        PlayerState(
            player_id=0,
            name="Test Human",
            position=0,
            score=0,
            hand=[
                CardState(card_type='Clean Injera', name='Clean Injera'),
                CardState(card_type='Clean Injera', name='Clean Injera'),
                CardState(card_type='Tahini', name='Tahini'),
            ],
            base_hand_size=5,
            is_ai=False
        ),
        PlayerState(
            player_id=1,
            name="Test Neural AI",
            position=1,
            score=0,
            hand=[
                CardState(card_type='Clean Injera', name='Clean Injera'),
                CardState(card_type='Drink', name='Order Coffee'),
            ],
            base_hand_size=5,
            is_ai=True,
            ai_level='neural'
        )
    ]

    # Create deck state
    deck = DeckState(
        cards_remaining=50,
        deck_size=50,
        discard_size=0,
        composition={'Injera': 30, 'Rotate': 10, 'Tahini': 5, 'Coffee': 3, 'Beer': 2}
    )

    # Reachable tiles (for simplicity, all tiles are reachable by both players)
    reachable = [[(t.q, t.r) for t in board], [(t.q, t.r) for t in board]]

    # Create game state
    state = GameState(
        num_players=2,
        current_player_idx=1,  # AI's turn
        board=board,
        players=players,
        deck=deck,
        reachable_by_player=reachable,
        final_round_active=False,
        final_round_start_player=-1,
        game_over=False
    )

    return state


def test_action_generator():
    """Test that action generator finds legal actions"""
    print("Testing Action Generator...")

    state = create_test_game_state()

    # Get legal actions for AI player (player 1)
    legal_actions = ActionGenerator.get_legal_actions(state, player_id=1)

    print(f"  Found {len(legal_actions)} legal actions for AI player")

    # Print first few actions
    for i, action in enumerate(legal_actions[:5]):
        print(f"    {i+1}. {action.action_type.value} at {action.tile_coord}")

    if len(legal_actions) > 5:
        print(f"    ... and {len(legal_actions) - 5} more")

    assert len(legal_actions) > 0, "Should find at least one legal action"
    print("  Action generator working!")
    print()


def test_game_state_serialization():
    """Test that game state can be converted to/from dict"""
    print("Testing GameState Serialization...")

    state = create_test_game_state()

    # Convert to dict
    state_dict = state.to_dict()
    print(f"  Converted to dict: {len(state_dict)} keys")

    # Convert back to GameState
    state2 = GameState.from_dict(state_dict)
    print(f"  Converted back to GameState")

    # Check that key properties match
    assert state2.num_players == state.num_players
    assert state2.current_player_idx == state.current_player_idx
    assert len(state2.board) == len(state.board)
    assert len(state2.players) == len(state.players)

    print("  Serialization working!")
    print()


def run_all_tests():
    """Run all tests"""
    print("=" * 60)
    print("INJERA AI SYSTEM TESTS")
    print("=" * 60)
    print()

    try:
        test_action_generator()
        test_game_state_serialization()

        print("=" * 60)
        print("ALL TESTS PASSED!")
        print("=" * 60)
        print()
        print("Next steps:")
        print("1. Run 'python server.py' to start the AI server")
        print("2. Open injera_game.html in your browser")
        print("3. Start playing against the Neural AI!")

    except AssertionError as e:
        print()
        print("=" * 60)
        print("TEST FAILED!")
        print("=" * 60)
        print(f"Error: {e}")
        return 1

    except Exception as e:
        print()
        print("=" * 60)
        print("UNEXPECTED ERROR!")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == '__main__':
    exit_code = run_all_tests()
    sys.exit(exit_code)
