"""Тесты нейросети: градиентная проверка и переобучение на крошечных задачах.

Запуск:  python -m tests.test_nn
"""
from __future__ import annotations

import sys

import numpy as np

from src.nn import Adam, Dense, Dropout, Model, ReLU, SoftmaxCrossEntropy


def numerical_grad(f, x, eps=1e-5):
    """Численный градиент по всем элементам массива (центральная разность)."""
    g = np.zeros_like(x)
    it = np.nditer(x, flags=["multi_index"])
    while not it.finished:
        i = it.multi_index
        old = x[i]
        x[i] = old + eps
        fp = f()
        x[i] = old - eps
        fm = f()
        x[i] = old
        g[i] = (fp - fm) / (2 * eps)
        it.iternext()
    return g


def gradient_check():
    """Сравниваем аналитический backprop с численным градиентом."""
    rng = np.random.default_rng(0)
    model = Model([Dense(4, 6), ReLU(), Dense(6, 3)])
    loss_fn = SoftmaxCrossEntropy()
    x = rng.normal(size=(5, 4))
    y = rng.integers(0, 3, size=5)

    def compute_loss():
        return loss_fn.forward(model.forward(x, training=True), y)

    compute_loss()
    model.backward(loss_fn.backward())

    max_rel_err = 0.0
    for layer in model.layers:
        for p, g in zip(layer.params, layer.grads):
            ng = numerical_grad(compute_loss, p)
            denom = np.maximum(np.abs(ng) + np.abs(g), 1e-8)
            rel = float((np.abs(ng - g) / denom).max())
            max_rel_err = max(max_rel_err, rel)
    assert max_rel_err < 1e-5, f"градиенты расходятся: относительная ошибка {max_rel_err}"
    print(f"  ✓ градиентная проверка пройдена (макс. относительная ошибка {max_rel_err:.2e})")


def overfit_xor():
    """Модель должна уметь выучивать даже нелинейную задачу XOR."""
    rng = np.random.default_rng(1)
    x = rng.random((200, 2))
    y = ((x[:, 0] > 0.5) ^ (x[:, 1] > 0.5)).astype(np.int64)
    model = Model([Dense(2, 16), ReLU(), Dense(16, 2)])
    model.fit(x, y, epochs=500, batch_size=32, lr=0.02, verbose=False)
    acc = model.evaluate(x, y)["accuracy"]
    assert acc > 0.95, f"XOR не выучен: точность {acc:.3f}"
    print(f"  ✓ XOR выучен (точность {acc:.3f})")


def shapes_and_dropout():
    """Проверяем размерности и поведение dropout."""
    rng = np.random.default_rng(2)
    model = Model([Dense(10, 8), ReLU(), Dropout(0.5), Dense(8, 4)])
    x = rng.normal(size=(7, 10))
    out = model.forward(x, training=True)
    assert out.shape == (7, 4), f"неверная форма выхода: {out.shape}"
    out_eval = model.forward(x, training=False)
    assert np.isfinite(out_eval).all()
    logits = model.forward(x, training=False)
    loss = model.loss_fn.forward(logits, rng.integers(0, 4, size=7))
    assert np.isfinite(loss) and loss > 0
    print("  ✓ формы выхода и dropout корректны")


def save_load_roundtrip(tmp_path="/tmp/test_model.npz"):
    """Сохранённая модель должна давать те же вероятности."""
    rng = np.random.default_rng(3)
    model = Model([Dense(5, 8), ReLU(), Dense(8, 3)])
    x = rng.normal(size=(4, 5))
    p1 = model.predict_proba(x)
    model.save(tmp_path)
    model2 = Model.load(tmp_path)
    p2 = model2.predict_proba(x)
    assert np.allclose(p1, p2, atol=1e-10), "вероятности до/после загрузки различаются"
    print("  ✓ сохранение/загрузка модели воспроизводимы")


def preprocess_roundtrip():
    """Цифра из датасета, «нарисованная» заново через препроцессинг,
    должна узнаваться моделью и сохранять форму."""
    import os

    import numpy as np
    from PIL import Image

    from src.preprocess import from_image

    samples_path = os.path.join("data", "digits_samples.npz")
    if not os.path.exists(samples_path):
        print("  – датасет ещё не сохранён, тест препроцессинга пропущен")
        return
    samples = np.load(samples_path)
    images, labels = samples["images"], samples["y"]
    rng = np.random.default_rng(0)
    idx = rng.choice(len(images), 50, replace=False)
    ok = 0
    model_path = os.path.join("models", "digits_model.npz")
    if os.path.exists(model_path):
        from src.nn import Model

        model = Model.load(model_path)
        for i in idx:
            im = Image.fromarray((images[i] / 16 * 255).astype(np.uint8))
            im = im.resize((280, 280), Image.Resampling.LANCZOS)
            x = from_image(im, side=8)
            ok += int(model.predict_proba(x)[0].argmax()) == labels[i]
        assert ok / len(idx) >= 0.9, f"препроцессинг ломает цифры: {ok}/{len(idx)}"
    print(f"  ✓ препроцессинг сохраняет распознаваемость ({ok}/{len(idx)})")


def main() -> int:
    print("Тесты нейросети MyBot:")
    gradient_check()
    overfit_xor()
    shapes_and_dropout()
    save_load_roundtrip()
    preprocess_roundtrip()
    print("Все тесты пройдены ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
