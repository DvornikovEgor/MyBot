"""Слои и модели: всё, из чего собирается нейросеть."""

from __future__ import annotations

import math
import random
from typing import Dict, Iterable, List, Optional

from .tensor import Tensor, no_grad

__all__ = ["Module", "Linear", "RNNCell", "Sequential", "Dropout", "Tanh", "ReLU", "Sigmoid"]


class Module:
    """Базовый класс для всех слоёв и моделей."""

    training: bool = True

    def forward(self, *args, **kwargs):
        raise NotImplementedError

    def __call__(self, *args, **kwargs):
        return self.forward(*args, **kwargs)

    # --- параметры ---------------------------------------------------------

    def _named_params(self, prefix: str = "", out=None, seen=None):
        if out is None:
            out = []
        if seen is None:
            seen = set()
        for name, value in sorted(self.__dict__.items()):
            if name.startswith("_"):
                continue
            key = "%s.%s" % (prefix, name) if prefix else name
            if isinstance(value, Tensor):
                if value.requires_grad and id(value) not in seen:
                    seen.add(id(value))
                    out.append((key, value))
            elif isinstance(value, Module):
                value._named_params(key, out, seen)
            elif isinstance(value, (list, tuple)):
                for i, item in enumerate(value):
                    if isinstance(item, Module):
                        item._named_params("%s[%d]" % (key, i), out, seen)
                    elif isinstance(item, Tensor) and item.requires_grad and id(item) not in seen:
                        seen.add(id(item))
                        out.append(("%s[%d]" % (key, i), item))
            elif isinstance(value, dict):
                for k, item in value.items():
                    if isinstance(item, Module):
                        item._named_params("%s[%r]" % (key, k), out, seen)
        return out

    def parameters(self) -> List[Tensor]:
        """Все обучаемые тензоры модели."""
        return [p for _, p in self._named_params()]

    def named_parameters(self):
        return self._named_params()

    def zero_grad(self) -> None:
        for p in self.parameters():
            p.grad = None

    def state_dict(self) -> Dict[str, dict]:
        """Веса модели (простой JSON-совместимый формат)."""
        return {name: {"shape": list(p.shape), "data": list(p.data)}
                for name, p in self._named_params()}

    def load_state_dict(self, state: Dict[str, dict]) -> None:
        params = dict(self._named_params())
        for name, blob in state.items():
            if name not in params:
                raise KeyError("в модели нет параметра %r" % name)
            p = params[name]
            if tuple(blob["shape"]) != tuple(p.shape):
                raise ValueError("форма параметра %r не совпадает: %r != %r"
                                 % (name, tuple(blob["shape"]), tuple(p.shape)))
            p.data = [float(v) for v in blob["data"]]

    def train(self, mode: bool = True) -> "Module":
        self.training = mode
        for value in self.__dict__.values():
            if isinstance(value, Module):
                value.train(mode)
        return self

    def eval(self) -> "Module":
        return self.train(False)

    def __repr__(self) -> str:
        extra = "  (parameters: %d)" % len(self.parameters()) if self.parameters() else ""
        return "%s(%s)" % (self.__class__.__name__, extra)


# ---------------------------------------------------------------------------
# Слои
# ---------------------------------------------------------------------------


def _init_weight(in_features: int, out_features: int, scale: Optional[float] = None) -> List[float]:
    """Инициализация Кайминга (Хе) — подходит для tanh/relu."""
    std = scale if scale is not None else math.sqrt(2.0 / max(in_features, 1))
    return [random.gauss(0.0, std) for _ in range(in_features * out_features)]


class Linear(Module):
    """Полносвязный слой: y = x @ W + b."""

    def __init__(self, in_features: int, out_features: int, bias: bool = True,
                 scale: Optional[float] = None):
        super().__init__()
        self.in_features = int(in_features)
        self.out_features = int(out_features)
        self.weight = Tensor(_init_weight(self.in_features, self.out_features, scale),
                             (self.in_features, self.out_features), requires_grad=True)
        self.bias = Tensor([0.0] * self.out_features, (1, self.out_features),
                           requires_grad=True) if bias else None

    def forward(self, x: Tensor) -> Tensor:
        if x.ndim == 1:
            x = x.reshape(1, x.size)
        out = x.matmul(self.weight)
        if self.bias is not None:
            out = out + self.bias
        return out

    def __repr__(self) -> str:
        return "Linear(%d, %d, bias=%s)" % (self.in_features, self.out_features,
                                            self.bias is not None)


class RNNCell(Module):
    """Один шаг рекуррентной сети: h' = tanh(W_xh x + W_hh h + b)."""

    def __init__(self, input_size: int, hidden_size: int, nonlinearity: str = "tanh"):
        super().__init__()
        self.input_size = int(input_size)
        self.hidden_size = int(hidden_size)
        self.nonlinearity = nonlinearity
        self.x2h = Linear(input_size, hidden_size)
        self.h2h = Linear(hidden_size, hidden_size)
        if nonlinearity not in ("tanh", "relu", "none"):
            raise ValueError("неизвестная нелинейность: %r" % nonlinearity)

    def forward(self, x: Tensor, h: Tensor) -> Tensor:
        out = self.x2h(x) + self.h2h(h)
        if self.nonlinearity == "tanh":
            return out.tanh()
        if self.nonlinearity == "relu":
            return out.relu()
        return out

    def __repr__(self) -> str:
        return "RNNCell(%d, %d, %s)" % (self.input_size, self.hidden_size, self.nonlinearity)


class Sequential(Module):
    """Последовательность слоёв."""

    def __init__(self, *modules: Module):
        super().__init__()
        self.layers = list(modules)

    def forward(self, x: Tensor) -> Tensor:
        for layer in self.layers:
            x = layer(x)
        return x

    def __repr__(self) -> str:
        return "Sequential(\n  " + "\n  ".join(repr(l) for l in self.layers) + "\n)"


class Dropout(Module):
    """Регуляризация: в режиме обучения часть нейронов зануляется."""

    def __init__(self, p: float = 0.5):
        super().__init__()
        if not 0.0 <= p < 1.0:
            raise ValueError("вероятность dropout должна быть в [0, 1)")
        self.p = float(p)

    def forward(self, x: Tensor) -> Tensor:
        if not self.training or self.p == 0.0:
            return x
        keep = 1.0 - self.p
        mask = [1.0 if random.random() < keep else 0.0 for _ in range(x.size)]
        with no_grad():
            m = Tensor(mask, x.shape)
        return x * m * (1.0 / keep)

    def __repr__(self) -> str:
        return "Dropout(p=%s)" % self.p


class Tanh(Module):
    def forward(self, x: Tensor) -> Tensor:
        return x.tanh()


class ReLU(Module):
    def forward(self, x: Tensor) -> Tensor:
        return x.relu()


class Sigmoid(Module):
    def forward(self, x: Tensor) -> Tensor:
        return x.sigmoid()
