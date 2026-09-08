"""Демо 2: классификация двух спиралей + карта решений в консоли.

Запуск::

    python -m mybot.apps.spiral

Данные генерируются сами (две закрученные спирали), сеть учится разделять их
нелинейной границей. В конце печатается ASCII-карта: где сеть отвечает «0»,
а где «1».
"""

from __future__ import annotations

import argparse
import math
import random

from ..engine import Adam, F, Tensor
from ..engine.utils import accuracy, batches, set_seed, train_test_split
from ..models.mlp import MLP


def make_spirals(n_per_arm: int = 150, turns: float = 1.5, noise: float = 0.05,
                 seed: int = 0):
    """Две закрученные спирали: точки и метки 0/1."""
    rnd = random.Random(seed)
    data, labels = [], []
    for arm in range(2):
        for i in range(n_per_arm):
            t = i / max(n_per_arm - 1, 1)
            r = 0.15 + 0.85 * t
            theta = turns * 2.0 * math.pi * t + arm * math.pi
            x = r * math.sin(theta) + rnd.gauss(0.0, noise)
            y = r * math.cos(theta) + rnd.gauss(0.0, noise)
            data.append([x, y])
            labels.append(arm)
    idx = list(range(len(data)))
    rnd.shuffle(idx)
    return [data[i] for i in idx], [labels[i] for i in idx]


def main(epochs: int = 300, hidden: int = 32, lr: float = 0.03, batch_size: int = 32,
         points: int = 150, seed: int = 42, activation: str = "relu", verbose: bool = True):
    set_seed(seed)
    data, labels = make_spirals(n_per_arm=points, seed=seed)
    train_pairs, test_pairs = train_test_split(list(zip(data, labels)), test_ratio=0.25, seed=seed)
    train_x = [p[0] for p in train_pairs]
    train_y = [p[1] for p in train_pairs]
    test_x = [p[0] for p in test_pairs]
    test_y = [p[1] for p in test_pairs]

    model = MLP([2, hidden, hidden, 2], hidden_activation=activation)
    opt = Adam(model.parameters(), lr=lr)
    order = list(range(len(train_x)))

    for epoch in range(1, epochs + 1):
        random.shuffle(order)
        epoch_loss, seen = 0.0, 0
        for chunk in batches(order, batch_size):
            xs = Tensor([train_x[i] for i in chunk], (len(chunk), 2))
            ys = [train_y[i] for i in chunk]
            logits = model(xs)
            loss = F.cross_entropy(logits, ys)
            opt.zero_grad()
            loss.backward()
            opt.step()
            epoch_loss += loss.item() * len(chunk)
            seen += len(chunk)
        if verbose and (epoch % max(epochs // 10, 1) == 0 or epoch == 1):
            train_acc = accuracy(model(Tensor(train_x, (len(train_x), 2))), train_y)
            test_acc = accuracy(model(Tensor(test_x, (len(test_x), 2))), test_y)
            print("эпоха %4d | ошибка %.4f | точность: обучение %.1f%%, проверка %.1f%%"
                  % (epoch, epoch_loss / max(seen, 1), 100 * train_acc, 100 * test_acc))

    test_logits = model(Tensor(test_x, (len(test_x), 2)))
    return model, (train_x, train_y), (test_x, test_y), accuracy(test_logits, test_y)


def decision_map(model, data, labels, size: int = 25, span: float = 1.35) -> str:
    """ASCII-карта предсказаний сети на сетке size x size."""
    grid = []
    for row in range(size):
        y = span - 2.0 * span * row / (size - 1)
        for col in range(size):
            x = -span + 2.0 * span * col / (size - 1)
            grid.append([x, y])
    preds = model(Tensor(grid, (len(grid), 2))).argmax(dim=-1)

    canvas = [["·" if preds[r * size + c] == 0 else "▒" for c in range(size)]
              for r in range(size)]
    for (x, y), label in zip(data, labels):
        col = int(round((x + span) / (2 * span) * (size - 1)))
        row = int(round((span - y) / (2 * span) * (size - 1)))
        if 0 <= row < size and 0 <= col < size:
            canvas[row][col] = "0" if label == 0 else "1"
    return "\n".join("".join(row) for row in canvas)


def cli() -> None:
    parser = argparse.ArgumentParser(description="Классификация двух спиралей")
    parser.add_argument("--epochs", type=int, default=300)
    parser.add_argument("--hidden", type=int, default=32)
    parser.add_argument("--lr", type=float, default=0.03)
    parser.add_argument("--points", type=int, default=150, help="точек в каждой спирали")
    parser.add_argument("--activation", type=str, default="relu", choices=["relu", "tanh"])
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    model, (tx, ty), (vx, vy), acc = main(epochs=args.epochs, hidden=args.hidden,
                                          lr=args.lr, points=args.points, seed=args.seed,
                                          activation=args.activation)
    print("\nТочность на проверочной части: %.1f%%" % (100 * acc))
    print("\nКарта решений (0 и 1 — точки данных, · и ▒ — ответ сети):\n")
    print(decision_map(model, tx + vx, ty + vy))


if __name__ == "__main__":
    cli()
