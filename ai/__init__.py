"""
AI players for Injera.

Use HeuristicPlayer — it is the only working AI in this project.
All neural / RL approaches are archived in neural_ai/_archive/ and did not succeed.
"""

from ai.heuristic_player import HeuristicPlayer
from ai.evaluator import ActionEvaluator

__all__ = ["HeuristicPlayer", "ActionEvaluator"]
