"""Оптимизаторы: как именно обновляются веса."""

from __future__ import annotations

import math
from typing import Iterable, List

from .tensor import Tensor

__all__ = ["Optimizer", "SGD", "Adam"]


class Optimizer:
    """Базовый оптимизатор."""

    def __init__(self, params: Iterable[Tensor], lr: float):
        self.params: List[Tensor] = [p for p in params if p.requires_grad]
        if not self.params:
            raise ValueError("в оптимизатор переданы параметры без requires_grad")
        self.lr = float(lr)

    def zero_grad(self) -> None:
        for p in self.params:
            p.grad = None

    def step(self) -> None:
        raise NotImplementedError

    def __repr__(self) -> str:
        return "%s(lr=%g, params=%d)" % (self.__class__.__name__, self.lr, len(self.params))


class SGD(Optimizer):
    """Стохастический градиентный спуск с импульсом (и, по желанию, затуханием lr)."""

    def __init__(self, params: Iterable[Tensor], lr: float = 0.1, momentum: float = 0.9,
                 decay: float = 0.0):
        super().__init__(params, lr)
        self.momentum = float(momentum)
        self.decay = float(decay)
        self.velocities = [None] * len(self.params)
        self.t = 0

    def step(self) -> None:
        self.t += 1
        lr = self.lr / (1.0 + self.decay * (self.t - 1))
        for i, p in enumerate(self.params):
            if p.grad is None:
                continue
            g = p.grad
            if self.momentum:
                v = self.velocities[i]
                if v is None:
                    v = [0.0] * p.size
                v = [self.momentum * vj + gj for vj, gj in zip(v, g)]
                self.velocities[i] = v
                g = v
            p.data = [pj - lr * gj for pj, gj in zip(p.data, g)]


class Adam(Optimizer):
    """Adam: адаптивный шаг для каждого параметра отдельно."""

    def __init__(self, params: Iterable[Tensor], lr: float = 0.01,
                 betas: Iterable[float] = (0.9, 0.999), eps: float = 1e-8,
                 decay: float = 0.0):
        super().__init__(params, lr)
        self.b1, self.b2 = (float(b) for b in betas)
        self.eps = float(eps)
        self.decay = float(decay)
        self.t = 0
        self.m = [None] * len(self.params)
        self.v = [None] * len(self.params)

    def step(self) -> None:
        self.t += 1
        lr = self.lr / (1.0 + self.decay * (self.t - 1))
        bias1 = 1.0 - self.b1 ** self.t
        bias2 = 1.0 - self.b2 ** self.t
        for i, p in enumerate(self.params):
            if p.grad is None:
                continue
            g = p.grad
            m = self.m[i] or [0.0] * p.size
            v = self.v[i] or [0.0] * p.size
            m = [self.b1 * mj + (1.0 - self.b1) * gj for mj, gj in zip(m, g)]
            v = [self.b2 * vj + (1.0 - self.b2) * gj * gj for vj, gj in zip(v, g)]
            self.m[i], self.v[i] = m, v
            p.data = [
                pj - lr * (mj / bias1) / (math.sqrt(vj / bias2) + self.eps)
                for pj, mj, vj in zip(p.data, m, v)
            ]
