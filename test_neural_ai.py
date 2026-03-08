#!/usr/bin/env python3
"""
Test script to verify neural AI setup
"""

import sys
from pathlib import Path
import numpy as np

print("="*60)
print("Testing Neural AI Setup")
print("="*60 + "\n")

# Test 1: Import checks
print("1. Checking imports...")
try:
    import torch
    print(f"   ✓ PyTorch {torch.__version__}")
except ImportError as e:
    print(f"   ✗ PyTorch not installed: {e}")
    print("   Install with: pip install torch")
    sys.exit(1)

try:
    import numpy as np
    print(f"   ✓ NumPy {np.__version__}")
except ImportError as e:
    print(f"   ✗ NumPy not installed: {e}")
    sys.exit(1)

# Test 2: Module imports
print("\n2. Checking neural AI modules...")
try:
    from neural_ai.state_encoder import StateEncoder
    print("   ✓ StateEncoder")
except ImportError as e:
    print(f"   ✗ StateEncoder: {e}")
    sys.exit(1)

try:
    from neural_ai.policy_network import PolicyNetwork, ValueNetwork
    print("   ✓ PolicyNetwork, ValueNetwork")
except ImportError as e:
    print(f"   ✗ Policy/Value networks: {e}")
    sys.exit(1)

try:
    from neural_ai.trainer import SelfPlayTrainer
    print("   ✓ SelfPlayTrainer")
except ImportError as e:
    print(f"   ✗ SelfPlayTrainer: {e}")
    sys.exit(1)

# Test 3: State encoder
print("\n3. Testing state encoder...")
try:
    encoder = StateEncoder()
    print(f"   State size: {encoder.total_state_size}")
    print(f"   Action space: {encoder.get_action_space_size()}")
    print("   ✓ State encoder working")
except Exception as e:
    print(f"   ✗ State encoder error: {e}")
    sys.exit(1)

# Test 4: Neural networks
print("\n4. Testing neural networks...")
try:
    policy_net = PolicyNetwork(
        state_size=encoder.total_state_size,
        action_size=encoder.get_action_space_size()
    )
    value_net = ValueNetwork(state_size=encoder.total_state_size)

    # Test forward pass
    batch_size = 2
    state = torch.randn(batch_size, encoder.total_state_size)
    action_mask = torch.ones(batch_size, encoder.get_action_space_size())
    action_mask[:, 10:] = 0  # Only first 10 actions valid

    action_probs, _ = policy_net(state, action_mask)
    values = value_net(state)

    assert action_probs.shape == (batch_size, encoder.get_action_space_size())
    assert values.shape == (batch_size, 1)
    assert torch.allclose(action_probs.sum(dim=1), torch.ones(batch_size), atol=1e-4)

    print(f"   Policy network params: {sum(p.numel() for p in policy_net.parameters()):,}")
    print(f"   Value network params: {sum(p.numel() for p in value_net.parameters()):,}")
    print("   ✓ Neural networks working")
except Exception as e:
    print(f"   ✗ Neural network error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 5: Trainer
print("\n5. Testing trainer...")
try:
    trainer = SelfPlayTrainer(
        state_size=encoder.total_state_size,
        action_size=encoder.get_action_space_size(),
        learning_rate=1e-4,
        gamma=0.99,
        use_baseline=True
    )
    print(f"   Device: {trainer.device}")
    print("   ✓ Trainer initialized")
except Exception as e:
    print(f"   ✗ Trainer error: {e}")
    sys.exit(1)

# Test 6: Model save/load
print("\n6. Testing model save/load...")
try:
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        save_path = Path(tmpdir)
        trainer.save_checkpoint(save_path, episode=1)
        checkpoint_path = save_path / "checkpoint_episode_1.pt"
        assert checkpoint_path.exists()

        # Load
        trainer.load_checkpoint(checkpoint_path)
        print("   ✓ Model save/load working")
except Exception as e:
    print(f"   ✗ Save/load error: {e}")
    sys.exit(1)

# Test 7: Directory structure
print("\n7. Checking directory structure...")
models_dir = Path("neural_ai/models")
if not models_dir.exists():
    models_dir.mkdir(parents=True)
    print("   ✓ Created models directory")
else:
    print("   ✓ Models directory exists")

# Summary
print("\n" + "="*60)
print("✓ All tests passed!")
print("="*60)
print("\nYou're ready to train the neural AI!")
print("\nQuick start:")
print("  python train_neural_ai.py --games 50 --save-every 10")
print("\nFor help:")
print("  python train_neural_ai.py --help")
print()
