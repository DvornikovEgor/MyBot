"""
Загрузка данных для обучения.

Два источника:
  1) `digits` — встроенный в scikit-learn датасет рукописных цифр
     (1797 образцов 8×8, полностью офлайн, идёт в комплекте с библиотекой).
  2) `mnist` — классический MNIST (60 000 + 10 000 картинок 28×28).
     Файлы ищутся в папке `data/` (train-images-idx3-ubyte.gz, …).
     Если файлов нет — пытаемся скачать (нужен интернет).
"""
from __future__ import annotations

import gzip
import os
import struct
import urllib.request
from typing import Tuple

import numpy as np

MNIST_MIRRORS = [
    "https://ossci-datasets.s3.amazonaws.com/mnist/",
    "https://storage.googleapis.com/cvdf-datasets/mnist/",
]

MNIST_FILES = {
    "train_images": "train-images-idx3-ubyte.gz",
    "train_labels": "train-labels-idx1-ubyte.gz",
    "test_images": "t10k-images-idx3-ubyte.gz",
    "test_labels": "t10k-labels-idx1-ubyte.gz",
}


# --------------------------------------------------------------------------- #
#  Встроенный датасет цифр (8×8)
# --------------------------------------------------------------------------- #
def load_digits_data(data_home: str = "data") -> Tuple[np.ndarray, ...]:
    """Датасет из sklearn: X — [N, 64] в [0,1], y — метки 0..9.

    Дополнительно сохраняет копию картинок (8×8, значения 0..16) в
    `data/digits_samples.npz`, чтобы веб-интерфейс мог показывать примеры.
    """
    from sklearn.datasets import load_digits

    ds = load_digits()
    images = ds.images.astype(np.float32)          # [N, 8, 8], значения 0..16
    X = images.reshape(len(images), -1) / 16.0     # [N, 64] в [0, 1]
    y = ds.target.astype(np.int64)

    os.makedirs(data_home, exist_ok=True)
    samples_path = os.path.join(data_home, "digits_samples.npz")
    if not os.path.exists(samples_path):
        np.savez_compressed(samples_path, images=images, y=y)
    return split(X, y, seed=0)


# --------------------------------------------------------------------------- #
#  MNIST (28×28)
# --------------------------------------------------------------------------- #
def _read_idx(path: str) -> np.ndarray:
    """Разбирает файл формата IDX (см. спецификацию MNIST).

    Магическое число: 2 старших байта = 0, третий байт — тип данных,
    четвёртый — число размерностей. Далее идут размеры по каждой оси.
    """
    open_fn = gzip.open if path.endswith(".gz") else open
    with open_fn(path, "rb") as f:
        magic = struct.unpack(">I", f.read(4))[0]
        ndim = magic & 0xFF
        sizes = [struct.unpack(">I", f.read(4))[0] for _ in range(ndim)]
        data = np.frombuffer(f.read(), dtype=np.uint8)
    if ndim == 1:  # файл меток
        return data.astype(np.int64)
    return data.reshape(sizes).astype(np.float32) / 255.0


def _download_mnist(data_home: str) -> bool:
    os.makedirs(data_home, exist_ok=True)
    for name, fname in MNIST_FILES.items():
        dest = os.path.join(data_home, fname)
        if os.path.exists(dest):
            continue
        ok = False
        for mirror in MNIST_MIRRORS:
            url = mirror + fname
            try:
                print(f"Скачиваю {url} …")
                urllib.request.urlretrieve(url, dest)
                ok = True
                break
            except Exception as exc:  # noqa: BLE001
                print(f"  не удалось: {exc}")
        if not ok:
            return False
    return True


def load_mnist_data(data_home: str = "data") -> Tuple[np.ndarray, ...]:
    """Полный MNIST. Файлы берутся из `data_home`, при отсутствии скачиваются."""
    paths = {k: os.path.join(data_home, v) for k, v in MNIST_FILES.items()}
    if not all(os.path.exists(p) for p in paths.values()):
        print("Файлы MNIST не найдены, пробую скачать…")
        if not _download_mnist(data_home):
            raise RuntimeError(
                "Не удалось получить MNIST. Скачайте 4 файла вручную в папку "
                f"'{data_home}': " + ", ".join(MNIST_FILES.values())
            )
    x_tr = _read_idx(paths["train_images"]).reshape(-1, 784)
    y_tr = _read_idx(paths["train_labels"])
    x_te = _read_idx(paths["test_images"]).reshape(-1, 784)
    y_te = _read_idx(paths["test_labels"])
    return x_tr, y_tr, x_te, y_te


# --------------------------------------------------------------------------- #
#  Утилиты
# --------------------------------------------------------------------------- #
def split(X: np.ndarray, y: np.ndarray, val_frac: float = 0.2,
          seed: int = 42) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Перемешивает и делит выборку на train/val стратифицированно по классам."""
    rng = np.random.default_rng(seed)
    tr_idx, val_idx = [], []
    for cls in np.unique(y):
        idx = np.flatnonzero(y == cls)
        rng.shuffle(idx)
        cut = int(round(len(idx) * (1.0 - val_frac)))
        tr_idx.extend(idx[:cut])
        val_idx.extend(idx[cut:])
    tr_idx, val_idx = np.array(tr_idx), np.array(val_idx)
    rng.shuffle(tr_idx)
    rng.shuffle(val_idx)
    return X[tr_idx], y[tr_idx], X[val_idx], y[val_idx]


def get_dataset(name: str, data_home: str = "data"):
    """Возвращает (x_train, y_train, x_val, y_val, n_inputs, n_classes)."""
    if name == "digits":
        x_tr, y_tr, x_te, y_te = load_digits_data(data_home)
        return x_tr, y_tr, x_te, y_te, 64, 10
    if name == "mnist":
        x_tr, y_tr, x_te, y_te = load_mnist_data(data_home)
        # часть train выделяем под валидацию
        x_tr, y_tr, x_va, y_va = split(x_tr, y_tr, val_frac=0.05, seed=1)
        return x_tr, y_tr, x_va, y_va, 784, 10
    raise ValueError(f"Неизвестный датасет: {name!r} (доступны: digits, mnist)")
