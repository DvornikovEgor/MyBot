"""
Предсказание нейросети MyBot из командной строки.

Примеры:
    python -m src.predict --image my_digit.png      # распознать файл с цифрой
    python -m src.predict --sample 7                # показать пример из датасета
    python -m src.predict --demo 10                 # прогнать 10 случайных примеров
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np

from .nn import Model
from .preprocess import from_data_url, from_image, to_ascii

MODEL_PATH = os.path.join("models", "digits_model.npz")


def load_model(path: str = MODEL_PATH) -> Model:
    if not os.path.exists(path):
        raise SystemExit(
            f"Модель не найдена: {path}\n"
            "Сначала обучите её:  python -m src.train"
        )
    return Model.load(path)


def model_side(model: Model) -> int:
    """Сторона входной картинки: sqrt от размера входного слоя."""
    n_in = model.layers[0].W.shape[0]
    side = int(round(n_in ** 0.5))
    assert side * side == n_in, f"вход модели {n_in} не является квадратом"
    return side


def predict_file(model: Model, path: str) -> int:
    from PIL import Image

    side = model_side(model)
    img = Image.open(path)
    x = from_image(img, side=side)
    probs = model.predict_proba(x)[0]
    print(f"Файл: {path}")
    print(to_ascii(x[0]))
    _print_probs(probs)
    return int(probs.argmax())


def predict_dataset_sample(model: Model, index: int | None = None) -> int:
    samples = np.load(os.path.join("data", "digits_samples.npz"))
    images, labels = samples["images"], samples["y"]
    idx = np.random.default_rng().integers(len(images)) if index is None else index
    x = images[idx].reshape(1, -1) / 16.0
    probs = model.predict_proba(x)[0]
    print(f"Пример из датасета №{idx} (правильный ответ: {labels[idx]})")
    print(to_ascii(images[idx] / 16.0))
    _print_probs(probs)
    return int(probs.argmax())


def random_demo(model: Model, n: int = 10) -> None:
    samples = np.load(os.path.join("data", "digits_samples.npz"))
    images, labels = samples["images"], samples["y"]
    rng = np.random.default_rng()
    idx = rng.choice(len(images), size=n, replace=False)
    x = images[idx].reshape(len(idx), -1) / 16.0
    pred = model.predict(x)
    ok = int((pred == labels[idx]).sum())
    print(f"Правильно {ok} из {n}:")
    for i, p, t in zip(idx, pred, labels[idx]):
        mark = "✓" if p == t else "✗"
        print(f"  №{i:>4}: модель = {p}, истина = {t}  {mark}")


def _print_probs(probs: np.ndarray) -> None:
    print("\nУверенность модели по классам:")
    for d, p in enumerate(probs):
        bar = "█" * int(round(p * 30))
        print(f"  {d}: {p:6.1%} {bar}")
    print(f"\nОтвет модели: {int(probs.argmax())}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Распознавание цифр нейросетью MyBot")
    parser.add_argument("--image", type=str, help="путь к картинке с цифрой (png/jpg)")
    parser.add_argument("--data-url", type=str, help="data-URL картинки (base64)")
    parser.add_argument("--sample", type=int, default=None,
                        help="показать пример №N из датасета")
    parser.add_argument("--demo", type=int, default=None,
                        help="прогнать N случайных примеров из датасета")
    parser.add_argument("--model", type=str, default=MODEL_PATH)
    args = parser.parse_args(argv)

    if not any([args.image, args.data_url, args.sample is not None, args.demo]):
        parser.error("укажите --image, --data-url, --sample или --demo")

    model = load_model(args.model)
    if args.image:
        predict_file(model, args.image)
    elif args.data_url:
        probs = model.predict_proba(
            from_data_url(args.data_url, side=model_side(model))
        )[0]
        _print_probs(probs)
    elif args.sample is not None:
        predict_dataset_sample(model, args.sample)
    elif args.demo:
        random_demo(model, args.demo)
    return 0


if __name__ == "__main__":
    sys.exit(main())
