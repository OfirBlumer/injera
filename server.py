"""
AI Server - Flask API that provides AI moves to the web interface
Run this server alongside the HTML interface to enable AI players
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import sys
import os
import json
from datetime import datetime
from pathlib import Path

# Fix Windows emoji support
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Add parent directory to path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.game_state import GameState, Action, ActionType
from engine.action_generator import ActionGenerator
app = Flask(__name__)
CORS(app)  # Enable CORS for local development

# Try to load neural AI if a model exists
neural_ai_instance = None
try:
    from neural_ai.neural_player import NeuralAIPlayer
    from pathlib import Path
    # Find the latest checkpoint
    models_dir = Path('neural_ai/models')
    if models_dir.exists():
        checkpoints = sorted(models_dir.glob('checkpoint_episode_*.pt'),
                             key=lambda p: int(p.stem.split('_')[-1]))
        if checkpoints:
            latest = checkpoints[-1]
            neural_ai_instance = NeuralAIPlayer(str(latest))
            print(f"Neural AI loaded from: {latest.name}")
except Exception as e:
    print(f"Neural AI not available: {e}")


# ==================== GAME RECORDING ====================
recordings_dir = Path('recordings')
recordings_dir.mkdir(exist_ok=True)

# Active recording state
active_recording = {
    'active': False,
    'game_id': None,
    'actions': [],        # List of {game_state, action, player_id, timestamp}
    'metadata': {}
}


@app.route('/health', methods=['GET'])
def health_check():
    """Simple health check endpoint"""
    return jsonify({'status': 'ok', 'message': 'AI server is running'})


@app.route('/start_recording', methods=['POST'])
def start_recording():
    """Start recording a new game"""
    data = request.json or {}
    game_id = datetime.now().strftime('%Y%m%d_%H%M%S')

    active_recording['active'] = True
    active_recording['game_id'] = game_id
    active_recording['actions'] = []
    active_recording['metadata'] = {
        'start_time': datetime.now().isoformat(),
        'num_players': data.get('num_players', 2),
        'human_player_ids': data.get('human_player_ids', [0]),
        'label': data.get('label', '')
    }

    print(f"\n>>> RECORDING STARTED: game_{game_id}")
    return jsonify({'status': 'ok', 'game_id': game_id})


@app.route('/record_action', methods=['POST'])
def record_action():
    """Record a single (game_state, action) pair"""
    if not active_recording['active']:
        return jsonify({'error': 'No active recording. Call /start_recording first.'}), 400

    data = request.json
    game_state = data.get('game_state')
    action = data.get('action')
    player_id = data.get('player_id', 0)

    if not game_state or not action:
        return jsonify({'error': 'Missing game_state or action'}), 400

    active_recording['actions'].append({
        'game_state': game_state,
        'action': action,
        'player_id': player_id,
        'step': len(active_recording['actions'])
    })

    step = len(active_recording['actions'])
    print(f"  Recorded step {step}: player {player_id} -> {action.get('action_type', '?')}")
    return jsonify({'status': 'ok', 'step': step})


@app.route('/stop_recording', methods=['POST'])
def stop_recording():
    """Stop recording and save to file"""
    if not active_recording['active']:
        return jsonify({'error': 'No active recording'}), 400

    data = request.json or {}
    game_id = active_recording['game_id']

    # Add final metadata
    active_recording['metadata']['end_time'] = datetime.now().isoformat()
    active_recording['metadata']['total_steps'] = len(active_recording['actions'])
    active_recording['metadata']['final_scores'] = data.get('final_scores', [])
    active_recording['metadata']['winner'] = data.get('winner', '')
    if data.get('bonus_details'):
        active_recording['metadata']['bonus_details'] = data.get('bonus_details')

    # Save to file
    save_path = recordings_dir / f"game_{game_id}.json"
    recording_data = {
        'metadata': active_recording['metadata'],
        'actions': active_recording['actions']
    }

    with open(save_path, 'w') as f:
        json.dump(recording_data, f)

    total = len(active_recording['actions'])
    print(f">>> RECORDING SAVED: {save_path} ({total} steps)")

    # Reset
    active_recording['active'] = False
    active_recording['game_id'] = None
    active_recording['actions'] = []
    active_recording['metadata'] = {}

    return jsonify({'status': 'ok', 'file': str(save_path), 'total_steps': total})


@app.route('/recording_status', methods=['GET'])
def recording_status():
    """Check if recording is active"""
    return jsonify({
        'active': active_recording['active'],
        'game_id': active_recording['game_id'],
        'steps': len(active_recording['actions'])
    })


GAME_DATA_DIR = Path(__file__).parent / 'game_data'

@app.route('/save_game', methods=['POST'])
def save_game():
    """Save a single game's data JSON to the game_data/ directory."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    GAME_DATA_DIR.mkdir(exist_ok=True)
    ts = data.pop('ts', None) or datetime.now().strftime('%Y%m%d%H%M%S')
    n = data.get('config', {}).get('players', 'x')
    has_ai = any(p != 'human' for ck in [data.get('config', {}).get('checkpoints', [])] for p in ck)
    mode = 'n' if has_ai else 'h'
    filename = GAME_DATA_DIR / f'game_{n}p_{ts}_{mode}.json'
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)
    return jsonify({'saved': str(filename)})


@app.route('/save_recording', methods=['POST'])
def save_recording():
    """Save a full game recording (state, action steps) to the game_data/ directory."""
    body = request.get_json()
    if not body:
        return jsonify({'error': 'No data provided'}), 400
    GAME_DATA_DIR.mkdir(exist_ok=True)
    recording = body.get('data', {})
    ts = body.get('ts', datetime.now().strftime('%Y%m%d%H%M%S'))
    mode = body.get('mode', 'h')
    n = recording.get('num_players', 'x')
    filename = GAME_DATA_DIR / f'recording_{n}p_{ts}_{mode}.json'
    with open(filename, 'w') as f:
        json.dump(recording, f, indent=2)
    return jsonify({'saved': str(filename)})


@app.route('/ai_move', methods=['POST'])
def get_ai_move():
    """
    Get an AI move for the current game state.
    
    Expected JSON payload:
    {
        "game_state": { ... },  // Complete game state
        "ai_level": "neural"
    }

    Returns:
    {
        "action": { ... },  // Action to take
        "message": "AI's reasoning (for display)"
    }
    """
    try:
        data = request.json

        # Parse game state
        game_state_data = data.get('game_state')
        ai_level = data.get('ai_level', 'neural')

        if not game_state_data:
            return jsonify({'error': 'No game state provided'}), 400

        # Convert to GameState object
        state = GameState.from_dict(game_state_data)

        # Neural AI
        if neural_ai_instance is None:
            return jsonify({'error': 'Neural AI not available - no trained model found'}), 400
        all_legal = ActionGenerator.get_legal_actions(state, state.current_player_idx)
        action = neural_ai_instance.select_action(state, all_legal)
        if action is None:
            action = all_legal[0] if all_legal else Action(action_type=ActionType.END_TURN, player_id=state.current_player_idx)
        
        # DEBUG: Get action statistics
        all_actions = ActionGenerator.get_legal_actions(state, state.current_player_idx)
        
        action_counts = {}
        for a in all_actions:
            action_counts[a.action_type.value] = action_counts.get(a.action_type.value, 0) + 1
        
        debug_info = {
            'player_name': state.get_current_player().name,
            'hand_size': len(state.get_current_player().hand),
            'hand_cards': [c.name for c in state.get_current_player().hand],
            'total_legal_actions': len(all_actions),
            'actions_by_type': action_counts,
            'chosen_action': action.action_type.value
        }

        # Add per-action probabilities for neural AI
        if ai_level == 'neural' and neural_ai_instance is not None:
            # Use fixed-index probability lookup
            probs_full = getattr(neural_ai_instance, 'last_action_probs_full', None)
            fixed_map = getattr(neural_ai_instance, 'last_fixed_to_action', {})
            action_prob_debug = []
            if probs_full is not None:
                from neural_ai.state_encoder import build_coord_to_board_idx, action_to_fixed_index
                board = game_state_data['board']
                coord_to_idx = build_coord_to_board_idx(board)
                for a in all_legal:
                    fi = action_to_fixed_index(a, coord_to_idx, board)
                    prob = float(probs_full[fi]) if 0 <= fi < len(probs_full) else 0.0
                    action_prob_debug.append({
                        'action': _describe_action_short(a, state),
                        'probability': round(prob, 4)
                    })
            action_prob_debug.sort(key=lambda x: x['probability'], reverse=True)
            debug_info['action_probabilities'] = action_prob_debug

            # Print to server console
            player_name = state.get_current_player().name
            print(f"\n--- Neural AI move for {player_name} ({len(all_legal)} legal actions) ---")
            for entry in action_prob_debug[:10]:  # Top 10
                marker = " <<< CHOSEN" if entry['action'] == _describe_action_short(action, state) else ""
                print(f"  {entry['probability']:.4f}  {entry['action']}{marker}")
            if len(action_prob_debug) > 10:
                print(f"  ... and {len(action_prob_debug) - 10} more actions")
            print()
        
        # Generate a human-readable message about what the AI is doing
        message = _generate_action_message(action, state)
        
        # Return action as dictionary
        return jsonify({
            'action': action.to_dict(),
            'message': message,
            'ai_level': ai_level,
            'debug': debug_info  # Add debug info to response
        })
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/legal_actions', methods=['POST'])
def get_legal_actions():
    """
    Get all legal actions for the current player.
    Useful for debugging and testing.
    
    Expected JSON payload:
    {
        "game_state": { ... },
        "player_id": 0
    }
    
    Returns:
    {
        "actions": [ ... ],
        "count": int
    }
    """
    try:
        data = request.json
        game_state_data = data.get('game_state')
        player_id = data.get('player_id', 0)
        
        if not game_state_data:
            return jsonify({'error': 'No game state provided'}), 400
        
        # Convert to GameState object
        state = GameState.from_dict(game_state_data)
        
        # Get legal actions
        legal_actions = ActionGenerator.get_legal_actions(state, player_id)
        
        return jsonify({
            'actions': [action.to_dict() for action in legal_actions],
            'count': len(legal_actions)
        })
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


def _describe_action_short(action: Action, state: GameState) -> str:
    """Short description of an action for debug output"""
    try:
        if action.action_type == ActionType.EAT_DISH:
            tile = state.get_tile(action.tile_coord[0], action.tile_coord[1])
            dish = tile.dish if tile else "?"
            resource = "injera" if action.resource_type == 'card' else f"tile@{action.resource_tile_coord}"
            hot_info = f" hot:{action.num_drink_tokens_for_hot}drink" if action.num_drink_tokens_for_hot else ""
            discard = f" discard:{action.discard_card_type}" if action.discard_card_type else ""
            return f"EAT {dish} @({action.tile_coord[0]},{action.tile_coord[1]}) w/{resource}{discard}{hot_info}"
        elif action.action_type == ActionType.EAT_EMPTY_TILE:
            hot_info = f" hot:{action.num_drink_tokens_for_hot}drink" if action.num_drink_tokens_for_hot else ""
            discard = f" discard:{action.discard_card_type}" if action.discard_card_type else ""
            return f"EAT_EMPTY @({action.tile_coord[0]},{action.tile_coord[1]}){discard}{hot_info}"
        elif action.action_type == ActionType.PLAY_DRINK:
            return f"PLAY {action.drink_card_type or '?'}"
        elif action.action_type == ActionType.DRINK_TOKEN:
            player = state.get_current_player()
            drink = player.drinks[action.drink_index] if action.drink_index is not None and action.drink_index < len(player.drinks) else None
            dtype = drink.drink_type if drink else "?"
            return f"DRINK {dtype}"
        elif action.action_type == ActionType.PLAY_ROTATE:
            return f"ROTATE {action.rotation_direction}"
        elif action.action_type == ActionType.ADD_TAHINI:
            return f"ADD_TAHINI @({action.tile_coord[0]},{action.tile_coord[1]})"
        elif action.action_type == ActionType.END_TURN:
            return "END_TURN"
    except Exception:
        pass
    return str(action.action_type.value)


def _generate_action_message(action: Action, state: GameState) -> str:
    """Generate a human-readable message about the AI's action"""
    player = state.get_current_player()
    
    if action.action_type == ActionType.EAT_DISH:
        tile = state.get_tile(action.tile_coord[0], action.tile_coord[1])
        if tile:
            resource = "Injera card" if action.resource_type == 'card' else "empty tile"
            discard = f", discarding {action.discard_card_type}" if action.discard_card_type else ""
            hot = ""
            if action.num_drink_tokens_for_hot > 0:
                hot = f", using {action.num_drink_tokens_for_hot} drink token(s) for hot"
            return f"{player.name} is eating {tile.dish} using {resource}{discard}{hot}"
        return f"{player.name} is eating a dish"

    elif action.action_type == ActionType.EAT_EMPTY_TILE:
        discard = f", discarding {action.discard_card_type}" if action.discard_card_type else ""
        return f"{player.name} is eating an empty tile{discard}"

    elif action.action_type == ActionType.PLAY_DRINK:
        return f"{player.name} is ordering {action.drink_card_type or 'a drink'}"

    elif action.action_type == ActionType.DRINK_TOKEN:
        drink = player.drinks[action.drink_index] if action.drink_index is not None and action.drink_index < len(player.drinks) else None
        dtype = drink.drink_type if drink else "a drink"
        return f"{player.name} is drinking {dtype}"
    
    elif action.action_type == ActionType.PLAY_ROTATE:
        direction = "clockwise" if action.rotation_direction == 'clockwise' else "counter-clockwise"
        return f"{player.name} is rotating the board {direction}"
    
    elif action.action_type == ActionType.ADD_TAHINI:
        return f"{player.name} is adding tahini"
    
    elif action.action_type == ActionType.END_TURN:
        return f"{player.name} is ending their turn"
    
    return f"{player.name} is making a move"


if __name__ == '__main__':
    print("=" * 60)
    print("🤖 INJERA AI SERVER STARTING")
    print("=" * 60)
    print()
    print("Server will run on: http://localhost:5000")
    print()
    print("Available AI:")
    if neural_ai_instance:
        print(f"  - neural: Neural Network AI (loaded)")
    else:
        print(f"  - neural: NOT AVAILABLE (train first with train_neural_ai.py)")
    print()
    print("Endpoints:")
    print("  GET  /health           - Check if server is running")
    print("  POST /ai_move          - Get AI move for game state")
    print("  POST /legal_actions    - Get all legal actions (debug)")
    print("  POST /start_recording  - Start recording a game")
    print("  POST /record_action    - Record a (state, action) pair")
    print("  POST /stop_recording   - Stop recording and save")
    print("  GET  /recording_status - Check recording status")
    print()
    print("Press Ctrl+C to stop the server")
    print("=" * 60)
    print()
    
    app.run(host='localhost', port=5000, debug=True)