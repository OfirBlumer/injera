"""
Policy Network for Neural AI
Neural network that outputs action probabilities
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from typing import Tuple


class PolicyNetwork(nn.Module):
    """
    Policy network that takes game state and outputs action probabilities
    Uses masked softmax to handle variable number of valid actions
    """

    def __init__(self, state_size: int, action_size: int, hidden_sizes: Tuple[int, ...] = (512, 256, 128)):
        """
        Args:
            state_size: Size of input state vector
            action_size: Maximum number of actions
            hidden_sizes: Tuple of hidden layer sizes
        """
        super(PolicyNetwork, self).__init__()

        self.state_size = state_size
        self.action_size = action_size

        # Build network layers
        layers = []
        prev_size = state_size

        for hidden_size in hidden_sizes:
            layers.append(nn.Linear(prev_size, hidden_size))
            layers.append(nn.ReLU())
            layers.append(nn.Dropout(0.2))
            prev_size = hidden_size

        # Output layer (no activation, will use masked softmax)
        layers.append(nn.Linear(prev_size, action_size))

        self.network = nn.Sequential(*layers)

    def forward(self, state: torch.Tensor, action_mask: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Forward pass with action masking

        Args:
            state: State tensor of shape (batch_size, state_size)
            action_mask: Binary mask of shape (batch_size, action_size) indicating valid actions

        Returns:
            action_probs: Probability distribution over valid actions (batch_size, action_size)
            logits: Raw logits before softmax (batch_size, action_size)
        """
        # Get raw logits
        logits = self.network(state)

        # Apply mask (set invalid actions to large negative value)
        masked_logits = logits.clone()
        masked_logits[action_mask == 0] = -1e9

        # Softmax over valid actions
        action_probs = F.softmax(masked_logits, dim=-1)

        return action_probs, masked_logits

    def select_action(self, state: np.ndarray, action_mask: np.ndarray, deterministic: bool = False) -> Tuple[int, float]:
        """
        Select an action given a state

        Args:
            state: State vector (state_size,)
            action_mask: Binary mask (action_size,)
            deterministic: If True, select argmax. If False, sample from distribution

        Returns:
            action_idx: Selected action index
            log_prob: Log probability of selected action
        """
        self.eval()
        with torch.no_grad():
            state_tensor = torch.FloatTensor(state).unsqueeze(0)
            mask_tensor = torch.FloatTensor(action_mask).unsqueeze(0)

            action_probs, _ = self.forward(state_tensor, mask_tensor)

            if deterministic:
                action_idx = torch.argmax(action_probs[0]).item()
            else:
                # Sample from distribution
                dist = torch.distributions.Categorical(action_probs[0])
                action_idx = dist.sample().item()

            log_prob = torch.log(action_probs[0, action_idx] + 1e-10).item()

        return action_idx, log_prob


class ValueNetwork(nn.Module):
    """
    Value network for advantage estimation (optional, for actor-critic)
    """

    def __init__(self, state_size: int, hidden_sizes: Tuple[int, ...] = (512, 256, 128)):
        super(ValueNetwork, self).__init__()

        layers = []
        prev_size = state_size

        for hidden_size in hidden_sizes:
            layers.append(nn.Linear(prev_size, hidden_size))
            layers.append(nn.ReLU())
            layers.append(nn.Dropout(0.2))
            prev_size = hidden_size

        # Output single value
        layers.append(nn.Linear(prev_size, 1))

        self.network = nn.Sequential(*layers)

    def forward(self, state: torch.Tensor) -> torch.Tensor:
        """
        Forward pass

        Args:
            state: State tensor of shape (batch_size, state_size)

        Returns:
            value: Estimated value of state (batch_size, 1)
        """
        return self.network(state)


# Example usage
if __name__ == "__main__":
    # Test network
    state_size = 1500  # Example size
    action_size = 500
    batch_size = 4

    policy_net = PolicyNetwork(state_size, action_size)
    value_net = ValueNetwork(state_size)

    # Create dummy input
    state = torch.randn(batch_size, state_size)
    action_mask = torch.ones(batch_size, action_size)
    action_mask[:, 10:] = 0  # Only first 10 actions are valid

    # Forward pass
    action_probs, logits = policy_net(state, action_mask)
    values = value_net(state)

    print("Policy network output shape:", action_probs.shape)
    print("Value network output shape:", values.shape)
    print("Action probabilities sum:", action_probs.sum(dim=1))
    print("First 15 action probs:", action_probs[0, :15])
