#!/usr/bin/env python3
"""
Fix import issues for neural AI
Run this from the injera_ai directory
"""

import sys
from pathlib import Path

# Add current directory to Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

print("Testing imports...")
print(f"Current directory: {current_dir}")
print(f"Python path: {sys.path[0]}")
print()

# Test 1: State encoder
print("1. Testing state_encoder...")
try:
    from neural_ai.state_encoder import StateEncoder
    encoder = StateEncoder()
    print(f"   [OK] StateEncoder working (state size: {encoder.total_state_size})")
except Exception as e:
    print(f"   [ERROR] Error: {e}")
    sys.exit(1)

# Test 2: Policy network
print("\n2. Testing policy_network...")
try:
    from neural_ai.policy_network import PolicyNetwork
    net = PolicyNetwork(encoder.total_state_size, encoder.get_action_space_size())
    print(f"   [OK] PolicyNetwork working")
except Exception as e:
    print(f"   [ERROR] Error: {e}")
    sys.exit(1)

# Test 3: Game engine
print("\n3. Testing game engine imports...")
try:
    from engine.game_state import GameState
    from engine.action_generator import ActionGenerator
    print(f"   [OK] Game engine imports working")
except Exception as e:
    print(f"   [ERROR] Error: {e}")
    print(f"\n   Make sure you're running this from the injera_ai directory!")
    sys.exit(1)

# Test 4: Neural player
print("\n4. Testing neural_player...")
try:
    from neural_ai.neural_player import NeuralAIPlayer, create_game_runner
    print(f"   [OK] NeuralAIPlayer working")
except Exception as e:
    print(f"   [ERROR] Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "="*60)
print("[SUCCESS] All imports working correctly!")
print("="*60)
print("\nYou can now:")
print("  • Train: python train_neural_ai.py --games 50")
print("  • Test: python test_neural_ai.py")
