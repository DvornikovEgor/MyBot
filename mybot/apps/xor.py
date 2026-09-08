"""Демо 1: полносвязная сеть учится логической функции XOR.

Запуск::

    python -m mybot.apps.xor

XOR — классический пример задачи, которую нельзя решить одной прямой линией:
нужен хотя бы один скрытый слой. Сеть учится с нуля за несколько секунд.
"""

from __future__ import annotations

import argparse

from ..engine import Adam, F, Tensor
from ..engine.utils import accuracy, set_seed
from ..models.mlp import MLP

# таблица истинности
X = [[0.0, 0.0], [0.0, 1.0], [1.0, 0.0], [1.0, 1.0]]
Y = [0, 1, 1, 0]


def main(epochs: int = 500, hidden: int = 8, lr: float = 0.05, seed: int = 42,
         verbose: bool = True) -> float:
    set_seed(seed)
    model = MLP([2, hidden, 2], hidden_activation="tanh")
    opt = Adam(model.parameters(), lr=lr)

    x = Tensor(X, (len(X), 2))
    history = []

    for step in range(1, epochs + 1):
        logits = model(x)
        loss = F.cross_entropy(logits, Y)
        acc = accuracy(logits, Y)

        opt.zero_grad()
        loss.backward()
        opt.step()
        history.append(loss.item())

        if verbose and (step % max(epochs // 10, 1) == 0 or step == 1):
            print("шаг %5d | ошибка %.4f | точность %.0f%%"
                  % (step, loss.item(), 100 * acc))

    logits = model(x)
    acc = accuracy(logits, Y)
    if verbose:
        print("\nИтог (точность %.0f%%):" % (100 * acc))
        for i, row in enumerate(X):
            row_logits = model(Tensor([row], (1, 2)))
            pr = model.predict_proba(Tensor([row], (1, 2))).data
            pred = row_logits.argmax(dim=-1)[0]
            mark = "+" if pred == Y[i] else "-"
            print("  %s %s -> %d (верно %d, вероятность %.3f)"
                  % (mark, row, pred, Y[i], pr[pred]))
    return acc


def cli() -> None:
    parser = argparse.ArgumentParser(description="Обучение MLP на функции XOR")
    parser.add_argument("--epochs", type=int, default=500)
    parser.add_argument("--hidden", type=int, default=8)
    parser.add_argument("--lr", type=float, default=0.05)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    main(epochs=args.epochs, hidden=args.hidden, lr=args.lr, seed=args.seed)


if __name__ == "__main__":
    cli()
