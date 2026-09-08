"""Многослойный персептрон (полносвязная сеть) для классификации и регрессии."""

from __future__ import annotations

from typing import Iterable, List, Optional, Sequence

from ..engine.nn import Dropout, Linear, Module, ReLU, Sequential, Tanh
from ..engine.tensor import Tensor

__all__ = ["MLP"]


def _activation(name: str) -> Module:
    name = (name or "none").lower()
    if name == "tanh":
        return Tanh()
    if name == "relu":
        return ReLU()
    if name in ("none", "linear", ""):
        return _Identity()
    raise ValueError("неизвестная активация: %r" % name)


class _Identity(Module):
    def forward(self, x: Tensor) -> Tensor:
        return x


class MLP(Module):
    """Полносвязная сеть. `sizes` — размеры слоёв, например [2, 16, 16, 2].

    На выходе — «сырые» логиты (без softmax): для классификации их подают
    в cross_entropy, для регрессии используют как есть.
    """

    def __init__(self, sizes: Sequence[int], hidden_activation: str = "tanh",
                 dropout: float = 0.0, output_activation: Optional[str] = None):
        super().__init__()
        if len(sizes) < 2:
            raise ValueError("нужно хотя бы два размера: вход и выход")
        self.sizes = list(sizes)
        self.hidden_activation = hidden_activation
        layers: List[Module] = []
        for i in range(len(sizes) - 1):
            layers.append(Linear(sizes[i], sizes[i + 1]))
            is_last = i == len(sizes) - 2
            if not is_last:
                layers.append(_activation(hidden_activation))
                if dropout:
                    layers.append(Dropout(dropout))
            elif output_activation:
                layers.append(_activation(output_activation))
        self.net = Sequential(*layers)

    def forward(self, x: Tensor) -> Tensor:
        if not isinstance(x, Tensor):
            x = Tensor(x)
        return self.net(x)

    def predict_proba(self, x: Tensor) -> Tensor:
        from ..engine.functional import softmax
        return softmax(self.forward(x), dim=-1)

    def __repr__(self) -> str:
        return "MLP(%s, hidden=%s)" % ("->".join(map(str, self.sizes)), self.hidden_activation)
