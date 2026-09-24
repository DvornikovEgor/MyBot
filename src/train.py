"""
Обучение нейросети MyBot.

Примеры:
    python -m src.train                                  # датасет digits, всё по умолчанию
    python -m src.train --epochs 50 --hidden 256,128     # побольше сеть
    python -m src.train --dataset mnist                  # полный MNIST (нужен интернет)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np


def build_model(n_in: int, n_classes: int, hidden: list[int], seed: int = 42):
    from .nn import Dense, Dropout, Model, ReLU

    layers = []
    prev = n_in
    for h in hidden:
        layers.append(Dense(prev, h))
        layers.append(ReLU())
        prev = h
    layers.append(Dense(prev, n_classes))
    return Model(layers, seed=seed)


def plot_history(history: list[dict], out_path: str) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib не установлен — график пропускаю")
        return
    epochs = [e["epoch"] for e in history]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    axes[0].plot(epochs, [e["train_loss"] for e in history], label="train")
    if "val_loss" in history[-1]:
        axes[0].plot(epochs, [e["val_loss"] for e in history], label="val")
    axes[0].set(title="Функция потерь", xlabel="эпоха", ylabel="loss")
    axes[0].legend(); axes[0].grid(alpha=0.3)
    axes[1].plot(epochs, [e["train_acc"] for e in history], label="train")
    if "val_acc" in history[-1]:
        axes[1].plot(epochs, [e["val_acc"] for e in history], label="val")
    axes[1].set(title="Точность", xlabel="эпоха", ylabel="accuracy")
    axes[1].legend(); axes[1].grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    print(f"График обучения сохранён: {out_path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Обучение нейросети MyBot с нуля")
    parser.add_argument("--dataset", choices=["digits", "mnist"], default="digits",
                        help="датасет: digits (встроенный, офлайн) или mnist (28×28)")
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=2e-3, help="скорость обучения (Adam)")
    parser.add_argument("--hidden", type=str, default="128,64",
                        help="размеры скрытых слоёв через запятую, напр. 256,128")
    parser.add_argument("--weight-decay", type=float, default=1e-4,
                        help="L2-регуляризация")
    parser.add_argument("--augment", type=int, default=6,
                        help="сколько «нарисованных» копий добавить к каждому примеру")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--data-home", type=str, default="data")
    parser.add_argument("--model-out", type=str, default=None,
                        help="куда сохранить веса (по умолчанию models/<dataset>_model.npz)")
    parser.add_argument("--no-plot", action="store_true")
    args = parser.parse_args(argv)

    from .data import get_dataset

    hidden = [int(h) for h in args.hidden.split(",") if h.strip()]
    os.makedirs("models", exist_ok=True)
    model_out = args.model_out or os.path.join("models", f"{args.dataset}_model.npz")

    print(f"Загружаю датасет: {args.dataset}")
    x_tr, y_tr, x_va, y_va, n_in, n_classes = get_dataset(args.dataset, args.data_home)
    side = int(np.sqrt(n_in))
    print(f"  обучающих примеров: {len(x_tr)}, валидационных: {len(x_va)}")

    # --- аугментация: симулируем «нарисованные человеком» варианты ------------
    from .preprocess import augment_dataset, simulate_drawing

    print(f"Аугментация: +{args.augment} искажённых копий каждого примера "
          f"(масштаб/поворот/сдвиг)…")
    x_tr_aug, y_tr_aug = augment_dataset(x_tr, y_tr, side,
                                         copies=args.augment, seed=args.seed)
    print(f"  стало обучающих примеров: {len(x_tr_aug)}")
    # «нарисованный» валидационный набор — метрика, ближе всего к реальному
    # использованию (человек рисует цифру мышкой)
    rng_draw = np.random.default_rng(123)
    x_va_draw = np.stack([simulate_drawing(xi, side, rng_draw) for xi in x_va])

    model = build_model(n_in, n_classes, hidden, seed=args.seed)
    total_params = sum(p.size for l in model.layers for p in l.params)
    arch = " → ".join(["вход"] + [f"{h}" for h in hidden] + [f"{n_classes} (softmax)"])
    print(f"Архитектура: {arch} | обучаемых параметров: {total_params:,}\n")

    t0 = time.time()
    history = model.fit(
        x_tr_aug, y_tr_aug, x_va, y_va,
        epochs=args.epochs, batch_size=args.batch_size,
        lr=args.lr, weight_decay=args.weight_decay,
    )
    dt = time.time() - t0

    m_raw = model.evaluate(x_va, y_va)
    m_draw = model.evaluate(x_va_draw, y_va)
    print(f"\nИтог за {dt:.1f} c:")
    print(f"  точность на «сырых» валидационных примерах: {m_raw['accuracy']:.2%}")
    print(f"  точность на «нарисованных» вариантах:       {m_draw['accuracy']:.2%}")

    model.save(model_out)
    print(f"Веса сохранены: {model_out}")

    hist_path = os.path.join("outputs", f"{args.dataset}_history.json")
    os.makedirs("outputs", exist_ok=True)
    with open(hist_path, "w", encoding="utf-8") as f:
        json.dump({"arch": arch, "params": total_params, "history": history,
                   "val_accuracy_raw": m_raw["accuracy"],
                   "val_accuracy_drawn": m_draw["accuracy"]},
                  f, ensure_ascii=False, indent=2)
    print(f"История обучения: {hist_path}")

    if not args.no_plot:
        plot_history(history, os.path.join("outputs", f"{args.dataset}_curve.png"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
