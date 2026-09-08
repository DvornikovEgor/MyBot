"""Модели, собранные на движке MyBot."""

from .mlp import MLP
from .char_rnn import CharRNN, one_hot_input

__all__ = ["MLP", "CharRNN", "one_hot_input"]
