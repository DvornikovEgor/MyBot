"""Функции активации и функции потерь, собранные на операциях тензора."""

from __future__ import annotations

from typing import Iterable, List, Sequence, Union

from .tensor import Tensor

__all__ = [
    "relu", "tanh", "sigmoid", "softmax", "log_softmax",
    "mse_loss", "cross_entropy", "one_hot",
]


def relu(x: Tensor) -> Tensor:
    return x.relu()


def tanh(x: Tensor) -> Tensor:
    return x.tanh()


def sigmoid(x: Tensor) -> Tensor:
    return x.sigmoid()


def softmax(x: Tensor, dim: int = -1) -> Tensor:
    """Численно устойчивый softmax по последней оси."""
    if x.ndim <= 1:
        e = (x - x.max()).exp()
        return e / e.sum()
    e = (x - x.max(dim=dim, keepdim=True)).exp()
    return e / e.sum(dim=dim, keepdim=True)


def log_softmax(x: Tensor, dim: int = -1) -> Tensor:
    """log(softmax(x)), устойчивый к большим логитам."""
    if x.ndim <= 1:
        z = x - x.max()
        return z - z.exp().sum().log()
    z = x - x.max(dim=dim, keepdim=True)
    return z - z.exp().sum(dim=dim, keepdim=True).log()


def one_hot(indices: Sequence[int], num_classes: int) -> Tensor:
    """One-hot матрица формы (len(indices), num_classes)."""
    data = [0.0] * (len(indices) * num_classes)
    for i, t in enumerate(indices):
        data[i * num_classes + int(t)] = 1.0
    return Tensor(data, (len(indices), num_classes))


def mse_loss(pred: Tensor, target: Union[Tensor, Sequence[float]]) -> Tensor:
    """Среднеквадратичная ошибка."""
    if not isinstance(target, Tensor):
        target = Tensor(target, pred.shape)
    diff = pred - target
    return (diff * diff).sum() / max(pred.size, 1)


def cross_entropy(logits: Tensor, targets: Union[Tensor, Sequence[int]]) -> Tensor:
    """Кросс-энтропия для мультиклассовой классификации.

    ``logits`` — форма (N, C); ``targets`` — либо список/тензор с номерами
    классов (форма (N,)), либо one-hot матрица (N, C).
    """
    if logits.ndim != 2:
        raise ValueError("logits должны быть формы (N, C), получено %r" % (logits.shape,))
    n, c = logits.shape
    log_probs = log_softmax(logits, dim=-1)
    if isinstance(targets, Tensor) and targets.ndim == 2:
        probs = targets.detach()
    else:
        idxs = targets.data if isinstance(targets, Tensor) else list(targets)
        idxs = [int(round(v)) for v in idxs]
        if len(idxs) != n:
            raise ValueError("число меток не совпадает с числом примеров")
        probs = one_hot(idxs, c)
    return -(log_probs * probs).sum() / max(n, 1)
