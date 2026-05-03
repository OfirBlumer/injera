"""
AI Server - Flask API that provides AI moves to the web interface.

Run: python server.py
"""

from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
import sys
import os
import json
import math
from datetime import datetime
from pathlib import Path

# Fix Windows emoji support
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.game_state import GameState, Action, ActionType
from engine.action_generator import ActionGenerator
from ai.heuristic_player import HeuristicPlayer
from ai.evaluator import ActionEvaluator
from ai.turn_planner import TurnPlanner, actions_match

app = Flask(__name__)
CORS(app)

# Committed turn sequences: player_id -> remaining List[Action] from the planned sequence.
# A new sequence is generated whenever the stored plan is empty or stale.
player_plans: dict = {}


def _find_legal_match(planned: Action, legal: list):
    """Return the legal action that semantically matches `planned`, or None."""
    for a in legal:
        if actions_match(planned, a):
            return a
    return None

# ──────────────────────────────────────────────────────────────────────────────
# Game recording state
# ──────────────────────────────────────────────────────────────────────────────

recordings_dir = Path('recordings')
recordings_dir.mkdir(exist_ok=True)

active_recording = {
    'active': False,
    'game_id': None,
    'actions': [],
    'metadata': {}
}

GAME_DATA_DIR = Path(__file__).parent / 'game_data'


# ──────────────────────────────────────────────────────────────────────────────
# Health / session
# ──────────────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return send_file('injera_game.html')

@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory('.', filename)


@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'ok',
        'ai_loaded': True,
        'ai_type': 'heuristic',
        'message': 'AI server is running'
    })


@app.route('/reset_session', methods=['POST'])
def reset_session():
    player_plans.clear()
    return jsonify({'status': 'ok'})


# ──────────────────────────────────────────────────────────────────────────────
# AI move — policy-only (no MCTS simulations)
# ──────────────────────────────────────────────────────────────────────────────

@app.route('/ai_move', methods=['POST'])
def get_ai_move():
    """
    Get a heuristic AI move for the current player.

    Expected JSON:  { "game_state": { ...full game state... } }
    Returns:        { "action": {...}, "message": "...", "debug": {...} }
    """
    try:
        data            = request.json
        game_state_data = data.get('game_state')

        if not game_state_data:
            return jsonify({'error': 'No game_state provided'}), 400

        state          = GameState.from_dict(game_state_data)
        current_player = state.current_player_idx
        legal          = ActionGenerator.get_legal_actions(state, current_player)

        if not legal:
            return jsonify({'error': 'No legal actions available'}), 400

        # ── Draft phase: delegate to HeuristicPlayer ──────────────────────────
        if legal[0].action_type == ActionType.SELECT_SPECIAL_CARDS:
            hp     = HeuristicPlayer(player_id=current_player)
            action = hp.choose_action(state) or legal[0]
            plan_source = 'draft'
            remaining_plan: list = []
        else:
            # ── Committed sequence logic ───────────────────────────────────────
            action      = None
            plan_source = 'cached'
            plan        = player_plans.get(current_player, [])

            if plan:
                matched = _find_legal_match(plan[0], legal)
                if matched:
                    action = matched
                    player_plans[current_player] = plan[1:]
                else:
                    # Plan is stale (hand changed unexpectedly); discard it
                    player_plans[current_player] = []
                    plan_source = 'stale'

            if action is None:
                new_plan = TurnPlanner(current_player).plan_sequence(state)
                if new_plan:
                    matched = _find_legal_match(new_plan[0], legal)
                    action  = matched if matched else new_plan[0]
                    player_plans[current_player] = new_plan[1:]
                else:
                    action = legal[0]
                    player_plans[current_player] = []
                plan_source = 'new'

            remaining_plan = player_plans.get(current_player, [])

        # ── Debug scoring (individual action scores for display) ───────────────
        evaluator  = ActionEvaluator(state, current_player)
        scored     = sorted(
            ((evaluator.score_action(a), a) for a in legal),
            key=lambda x: x[0],
            reverse=True
        )

        _temperature = 0.4
        _all_scores  = [s for s, _ in scored]
        _max_score   = _all_scores[0]
        _weights     = [math.exp((s - _max_score) / _temperature) for s in _all_scores]
        _total       = sum(_weights)
        _probs       = [w / _total for w in _weights]

        top_actions = [
            {
                'score': round(s, 3),
                'prob':  round(p * 100, 1),
                'action': _describe_action_short(a, state),
            }
            for (s, a), p in zip(scored[:8], _probs[:8])
        ]

        chosen_desc  = _describe_action_short(action, state)
        chosen_score = evaluator.score_action(action)
        chosen_prob  = math.exp((chosen_score - _max_score) / _temperature) / _total

        if not any(e['action'] == chosen_desc for e in top_actions):
            top_actions.append({
                'score': round(chosen_score, 3),
                'prob':  round(chosen_prob * 100, 1),
                'action': chosen_desc,
            })

        plan_ahead = [_describe_action_short(a, state) for a in remaining_plan[:6]]
        plan_label = {'new': '[new plan]', 'cached': '[from plan]', 'stale': '[stale→new]', 'draft': '[draft]'}[plan_source]

        print(f"\n--- P{current_player} {plan_label}: {action.action_type.value} ---")
        if plan_source in ('new', 'stale', 'draft'):
            for entry in top_actions:
                print(f"  {entry['score']:+.2f}  {entry['prob']:5.1f}%  {entry['action']}")
        if plan_ahead:
            print(f"  Next: {' → '.join(plan_ahead)}")

        action_msg = _generate_action_message(action, state)
        seq_str = ' → '.join([chosen_desc] + plan_ahead) if plan_ahead else chosen_desc
        if plan_source in ('new', 'stale', 'draft'):
            top_lines = '\n'.join(
                f"  {'▸' if e['action'] == chosen_desc else ' '} {e['prob']:5.1f}%  {e['action']}"
                for e in top_actions
            )
            message = f"{action_msg}\n{top_lines}\n  Plan: {seq_str}"
        else:
            message = f"{action_msg}\n  Plan: {seq_str}"

        return jsonify({
            'action':   action.to_dict(),
            'message':  message,
            'ai_level': 'heuristic',
            'debug': {
                'player_name':         state.get_current_player().name,
                'total_legal_actions': len(legal),
                'actions_by_type':     _count_by_type(legal),
                'chosen_action':       action.action_type.value,
                'temperature':         _temperature,
                'top_actions':         top_actions,
                'plan_source':         plan_source,
                'plan_ahead':          plan_ahead,
            }
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ──────────────────────────────────────────────────────────────────────────────
# Legal actions (debug)
# ──────────────────────────────────────────────────────────────────────────────

@app.route('/legal_actions', methods=['POST'])
def get_legal_actions():
    try:
        data      = request.json
        state     = GameState.from_dict(data.get('game_state'))
        player_id = data.get('player_id', state.current_player_idx)
        legal     = ActionGenerator.get_legal_actions(state, player_id)
        return jsonify({'actions': [a.to_dict() for a in legal], 'count': len(legal)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ──────────────────────────────────────────────────────────────────────────────
# Recording endpoints
# ──────────────────────────────────────────────────────────────────────────────

@app.route('/start_recording', methods=['POST'])
def start_recording():
    data    = request.json or {}
    game_id = datetime.now().strftime('%Y%m%d_%H%M%S')
    active_recording['active']   = True
    active_recording['game_id']  = game_id
    active_recording['actions']  = []
    active_recording['metadata'] = {
        'start_time':       datetime.now().isoformat(),
        'num_players':      data.get('num_players', 2),
        'human_player_ids': data.get('human_player_ids', [0]),
        'label':            data.get('label', '')
    }
    print(f"\n>>> RECORDING STARTED: game_{game_id}")
    return jsonify({'status': 'ok', 'game_id': game_id})


@app.route('/record_action', methods=['POST'])
def record_action():
    if not active_recording['active']:
        return jsonify({'error': 'No active recording'}), 400
    data       = request.json
    game_state = data.get('game_state')
    action     = data.get('action')
    player_id  = data.get('player_id', 0)
    if not game_state or not action:
        return jsonify({'error': 'Missing game_state or action'}), 400
    active_recording['actions'].append({
        'game_state': game_state,
        'action':     action,
        'player_id':  player_id,
        'step':       len(active_recording['actions'])
    })
    step = len(active_recording['actions'])
    print(f"  Recorded step {step}: player {player_id} -> {action.get('action_type', '?')}")
    return jsonify({'status': 'ok', 'step': step})


@app.route('/stop_recording', methods=['POST'])
def stop_recording():
    if not active_recording['active']:
        return jsonify({'error': 'No active recording'}), 400
    data    = request.json or {}
    game_id = active_recording['game_id']
    active_recording['metadata']['end_time']     = datetime.now().isoformat()
    active_recording['metadata']['total_steps']  = len(active_recording['actions'])
    active_recording['metadata']['final_scores'] = data.get('final_scores', [])
    active_recording['metadata']['winner']        = data.get('winner', '')
    if data.get('bonus_details'):
        active_recording['metadata']['bonus_details'] = data.get('bonus_details')
    save_path      = recordings_dir / f"game_{game_id}.json"
    recording_data = {'metadata': active_recording['metadata'], 'actions': active_recording['actions']}
    with open(save_path, 'w') as f:
        json.dump(recording_data, f)
    total = len(active_recording['actions'])
    print(f">>> RECORDING SAVED: {save_path} ({total} steps)")
    active_recording['active']   = False
    active_recording['game_id']  = None
    active_recording['actions']  = []
    active_recording['metadata'] = {}
    return jsonify({'status': 'ok', 'file': str(save_path), 'total_steps': total})


@app.route('/recording_status', methods=['GET'])
def recording_status():
    return jsonify({
        'active':  active_recording['active'],
        'game_id': active_recording['game_id'],
        'steps':   len(active_recording['actions'])
    })


@app.route('/save_game', methods=['POST'])
def save_game():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    GAME_DATA_DIR.mkdir(exist_ok=True)
    ts     = data.pop('ts', None) or datetime.now().strftime('%Y%m%d%H%M%S')
    n      = data.get('config', {}).get('players', 'x')
    has_ai = any(p != 'human' for ck in [data.get('config', {}).get('checkpoints', [])] for p in ck)
    mode   = 'n' if has_ai else 'h'
    filename = GAME_DATA_DIR / f'game_{n}p_{ts}_{mode}.json'
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)
    return jsonify({'saved': str(filename)})


@app.route('/save_recording', methods=['POST'])
def save_recording():
    body = request.get_json()
    if not body:
        return jsonify({'error': 'No data provided'}), 400
    GAME_DATA_DIR.mkdir(exist_ok=True)
    recording = body.get('data', {})
    ts   = body.get('ts', datetime.now().strftime('%Y%m%d%H%M%S'))
    mode = body.get('mode', 'h')
    n    = recording.get('num_players', 'x')
    filename = GAME_DATA_DIR / f'recording_{n}p_{ts}_{mode}.json'
    with open(filename, 'w') as f:
        json.dump(recording, f, indent=2)
    return jsonify({'saved': str(filename)})


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _count_by_type(actions):
    counts = {}
    for a in actions:
        counts[a.action_type.value] = counts.get(a.action_type.value, 0) + 1
    return counts


def _describe_action_short(action: Action, state: GameState) -> str:
    try:
        if action.action_type == ActionType.EAT_DISH:
            tile     = state.get_tile(action.tile_coord[0], action.tile_coord[1])
            dish     = tile.dish if tile else "?"
            resource = "card" if action.resource_type == 'card' else f"tile@{action.resource_tile_coord}"
            hot      = f" hot:{action.num_drink_tokens_for_hot}d" if action.num_drink_tokens_for_hot else ""
            discard  = f" dis:{action.discard_card_type}" if action.discard_card_type else ""
            return f"EAT {dish} @{action.tile_coord} w/{resource}{discard}{hot}"
        elif action.action_type == ActionType.EAT_EMPTY_TILE:
            hot = f" hot:{action.num_drink_tokens_for_hot}d" if action.num_drink_tokens_for_hot else ""
            return f"EAT_EMPTY @{action.tile_coord}{hot}"
        elif action.action_type == ActionType.PLAY_DRINK:
            return f"ORDER {action.drink_card_type or '?'}"
        elif action.action_type == ActionType.DRINK_TOKEN:
            pid    = action.player_id if action.player_id is not None else state.current_player_index
            player = state.players[pid] if pid < len(state.players) else state.get_current_player()
            idx    = action.drink_index
            if idx is not None and idx < len(player.drinks):
                label = player.drinks[idx].drink_type
            else:
                # Drink may not exist yet (plan precedes the PLAY_DRINK that adds it)
                active = [d for d in player.drinks if d.tokens > 0]
                label  = active[0].drink_type if active else "token"
            return f"DRINK_TOKEN {label}"
        elif action.action_type == ActionType.PLAY_ROTATE:
            return f"ROTATE {action.rotation_direction}"
        elif action.action_type == ActionType.ADD_TAHINI:
            return f"ADD_TAHINI @{action.tile_coord}"
        elif action.action_type == ActionType.ADD_AWAZE:
            return f"ADD_AWAZE @{action.tile_coord}"
        elif action.action_type == ActionType.DISCARD_REDRAW:
            return "DISCARD_REDRAW"
        elif action.action_type == ActionType.END_TURN:
            return "END_TURN"
    except Exception:
        pass
    return str(action.action_type.value)


def _generate_action_message(action: Action, state: GameState) -> str:
    player = state.get_current_player()
    if action.action_type == ActionType.EAT_DISH:
        tile = state.get_tile(action.tile_coord[0], action.tile_coord[1])
        if tile:
            resource = "Injera card" if action.resource_type == 'card' else "empty tile"
            discard  = f", discard {action.discard_card_type}" if action.discard_card_type else ""

            # Hotness from the dish itself
            is_hot   = tile.hot or tile.dish == 'Key Sir'
            base_hot = (2 if tile.dish == 'Key Sir' else 1) if is_hot else 0
            awaze    = getattr(tile, 'awaze', 0)
            tahini   = getattr(tile, 'tahini', 0)
            dish_hot = max(0, base_hot + awaze - tahini)

            # Hotness from the resource tile's hot token (eating via empty tile)
            tile_hot = 0
            if action.resource_type == 'tile' and action.resource_tile_coord:
                rt = state.get_tile(action.resource_tile_coord[0], action.resource_tile_coord[1])
                if rt and rt.hot_token:
                    q, r = action.resource_tile_coord
                    tile_hot = 2 if (abs(q) <= 1 and abs(r) <= 1 and abs(q + r) <= 1) else 1

            total_hot   = dish_hot + tile_hot
            drink_used  = action.num_drink_tokens_for_hot or 0
            injera_used = max(0, total_hot - drink_used)

            hot = ""
            if total_hot > 0 or tahini > 0:
                parts = []
                if tahini:
                    parts.append(f"tahini×{tahini} cools dish")
                if tile_hot:
                    parts.append(f"resource tile hot×{tile_hot}")
                if drink_used:
                    parts.append(f"{drink_used}× drink token")
                if injera_used:
                    parts.append(f"{injera_used}× injera")
                if not parts:
                    parts.append("tahini covers all")
                hot = f" [hot: {', '.join(parts)}]"

            return f"{player.name} eats {tile.dish} via {resource}{discard}{hot}"
        return f"{player.name} eats a dish"
    elif action.action_type == ActionType.EAT_EMPTY_TILE:
        tile = state.get_tile(action.tile_coord[0], action.tile_coord[1])
        hot = ""
        if tile and tile.hot_token:
            q, r = action.tile_coord
            hot_level   = 2 if (abs(q) <= 1 and abs(r) <= 1 and abs(q + r) <= 1) else 1
            tahini      = getattr(tile, 'tahini', 0)
            net_hot     = max(0, hot_level - tahini)
            drink_used  = action.num_drink_tokens_for_hot or 0
            injera_used = max(0, net_hot - drink_used)
            parts = []
            if tahini:
                parts.append(f"tahini×{tahini} cools")
            if drink_used:
                parts.append(f"{drink_used}× drink token")
            if injera_used:
                parts.append(f"{injera_used}× injera")
            if not parts:
                parts.append("tahini covers all")
            hot = f" [hot: {', '.join(parts)}]"
        return f"{player.name} eats an empty tile{hot}"
    elif action.action_type == ActionType.PLAY_DRINK:
        return f"{player.name} orders {action.drink_card_type or 'a drink'}"
    elif action.action_type == ActionType.DRINK_TOKEN:
        drink = state.get_current_player().drinks[action.drink_index] if action.drink_index is not None else None
        return f"{player.name} drinks {drink.drink_type if drink else 'a drink'}"
    elif action.action_type == ActionType.PLAY_ROTATE:
        return f"{player.name} rotates the board {action.rotation_direction}"
    elif action.action_type == ActionType.ADD_TAHINI:
        return f"{player.name} adds tahini"
    elif action.action_type == ActionType.ADD_AWAZE:
        return f"{player.name} adds awaze"
    elif action.action_type == ActionType.DISCARD_REDRAW:
        return f"{player.name} discards hand and redraws"
    elif action.action_type == ActionType.END_TURN:
        return f"{player.name} ends their turn"
    return f"{player.name} makes a move"


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description="Injera AI Server (heuristic player)")
    parser.add_argument('--port', type=int, default=5000)
    args = parser.parse_args()

    print("=" * 60)
    print("INJERA AI SERVER  (heuristic player)")
    print("=" * 60)
    print(f"  URL:  http://localhost:{args.port}")
    print("  Press Ctrl+C to stop")
    print("=" * 60)

    app.run(host='localhost', port=args.port, debug=False, threaded=True)
