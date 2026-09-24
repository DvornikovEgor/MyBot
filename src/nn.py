"""
MyBot AI — полносвязная нейросеть, написанная С НУЛЯ на чистом NumPy.

Здесь нет ни PyTorch, ни TensorFlow — только математика:
  * прямой проход (forward pass)
  * обратное распространение ошибки (backpropagation)
  * оптимизатор Adam
  * softmax + перекрёстная энтропия

Архитектура собирается из слоёв, как из кубиков:
    model = Model(
        Dense(64, 128), ReLU(),
        Dense(128, 64), ReLU(),
        Dense(64, 10),
    )
"""
from __future__ import annotations

import json
from typing import List, Optional, Sequence

import numpy as np


# --------------------------------------------------------------------------- #
#  Слои
# --------------------------------------------------------------------------- #
class Layer:
    """Базовый класс слоя. forward возвращает активации, backward — градиенты."""

    def forward(self, x: np.ndarray, training: bool = True) -> np.ndarray:
        raise NotImplementedError

    def backward(self, grad: np.ndarray) -> np.ndarray:
        raise NotImplementedError

    @property
    def params(self) -> List[np.ndarray]:
        """Обучаемые параметры слоя."""
        return []

    @property
    def grads(self) -> List[np.ndarray]:
        """Градиенты по параметрам (заполняются в backward)."""
        return []

    @property
    def param_names(self) -> List[str]:
        return []


class Dense(Layer):
    """Полносвязный слой: y = x @ W + b.

    Инициализация He — оптимальна для ReLU-сетей.
    """

    def __init__(self, n_in: int, n_out: int, rng: Optional[np.random.Generator] = None):
        rng = rng or np.random.default_rng()
        # He initialization: N(0, sqrt(2 / n_in))
        self.W = rng.normal(0.0, np.sqrt(2.0 / n_in), size=(n_in, n_out))
        self.b = np.zeros(n_out)
        self._dW = np.zeros_like(self.W)
        self._db = np.zeros_like(self.b)
        self._x: Optional[np.ndarray] = None

    def forward(self, x: np.ndarray, training: bool = True) -> np.ndarray:
        if training:
            self._x = x
        return x @ self.W + self.b

    def backward(self, grad: np.ndarray) -> np.ndarray:
        x = self._x
        assert x is not None, "backward() вызван до forward()"
        self._dW[...] = x.T @ grad
        self._db[...] = grad.sum(axis=0)
        return grad @ self.W.T  # градиент по входу

    @property
    def params(self) -> List[np.ndarray]:
        return [self.W, self.b]

    @property
    def grads(self) -> List[np.ndarray]:
        return [self._dW, self._db]

    @property
    def param_names(self) -> List[str]:
        return ["W", "b"]


class ReLU(Layer):
    """ rectified linear unit: max(0, x) """

    def __init__(self):
        self._mask: Optional[np.ndarray] = None

    def forward(self, x: np.ndarray, training: bool = True) -> np.ndarray:
        mask = x > 0
        if training:
            self._mask = mask
        return x * mask

    def backward(self, grad: np.ndarray) -> np.ndarray:
        assert self._mask is not None, "backward() вызван до forward()"
        return grad * self._mask


class Dropout(Layer):
    """Случайно «выключает» долю p нейронов при обучении (регуляризация)."""

    def __init__(self, p: float, rng: Optional[np.random.Generator] = None):
        assert 0.0 <= p < 1.0
        self.p = p
        self.rng = rng or np.random.default_rng()
        self._mask: Optional[np.ndarray] = None

    def forward(self, x: np.ndarray, training: bool = True) -> np.ndarray:
        if not training or self.p == 0.0:
            self._mask = None
            return x
        keep = 1.0 - self.p
        self._mask = (self.rng.random(x.shape) < keep) / keep
        return x * self._mask

    def backward(self, grad: np.ndarray) -> np.ndarray:
        if self._mask is None:
            return grad
        return grad * self._mask


# --------------------------------------------------------------------------- #
#  Функция потерь: softmax + перекрёстная энтропия (стабильная версия)
# --------------------------------------------------------------------------- #
class SoftmaxCrossEntropy:
    """Комбинированный softmax + cross-entropy.

    Градиент получается аналитически простым: (probs - one_hot) / batch.
    Это численно стабильно и быстро.
    """

    def forward(self, logits: np.ndarray, y_true: np.ndarray) -> float:
        shifted = logits - logits.max(axis=1, keepdims=True)
        exp = np.exp(shifted)
        self._probs = exp / exp.sum(axis=1, keepdims=True)
        n = logits.shape[0]
        self._y = y_true
        # log-likelihood правильного класса
        true_logit = shifted[np.arange(n), y_true]
        log_softmax = true_logit - np.log(exp.sum(axis=1))
        return float(-log_softmax.mean())

    def backward(self) -> np.ndarray:
        n = self._probs.shape[0]
        grad = self._probs.copy()
        grad[np.arange(n), self._y] -= 1.0
        return grad / n

    @property
    def probs(self) -> np.ndarray:
        return self._probs


# --------------------------------------------------------------------------- #
#  Оптимизаторы
# --------------------------------------------------------------------------- #
class Adam:
    """Adam (Kingma & Ba, 2015) — адаптивный градиентный спуск с моментом."""

    def __init__(self, lr: float = 1e-3, beta1: float = 0.9, beta2: float = 0.999,
                 eps: float = 1e-8, weight_decay: float = 0.0):
        self.lr, self.beta1, self.beta2, self.eps = lr, beta1, beta2, eps
        self.weight_decay = weight_decay
        self.t = 0
        self._m: List[np.ndarray] = []
        self._v: List[np.ndarray] = []

    def _lazy_init(self, params: Sequence[np.ndarray]) -> None:
        if not self._m:
            self._m = [np.zeros_like(p) for p in params]
            self._v = [np.zeros_like(p) for p in params]

    def step(self, layers: Sequence[Layer]) -> None:
        params: List[np.ndarray] = []
        grads: List[np.ndarray] = []
        for layer in layers:
            for name, p, g in zip(layer.param_names, layer.params, layer.grads):
                # L2-регуляризация не применяется к bias
                if self.weight_decay and name == "W":
                    g = g + self.weight_decay * p
                params.append(p)
                grads.append(g)
        self._lazy_init(params)
        self.t += 1
        bc1 = 1.0 - self.beta1 ** self.t
        bc2 = 1.0 - self.beta2 ** self.t
        for p, g, m, v in zip(params, grads, self._m, self._v):
            m[...] = self.beta1 * m + (1.0 - self.beta1) * g
            v[...] = self.beta2 * v + (1.0 - self.beta2) * g * g
            m_hat = m / bc1
            v_hat = v / bc2
            p -= self.lr * m_hat / (np.sqrt(v_hat) + self.eps)


# --------------------------------------------------------------------------- #
#  Модель
# --------------------------------------------------------------------------- #
class Model:
    """Последовательная нейросеть из слоёв."""

    def __init__(self, layers: Sequence[Layer], seed: int = 42):
        self.rng = np.random.default_rng(seed)
        self.layers: List[Layer] = [l for l in layers]
        # подсовываем общий генератор случайных чисел слоям, которым он нужен
        for layer in self.layers:
            if isinstance(layer, (Dense, Dropout)):
                layer.rng = self.rng
        self.loss_fn = SoftmaxCrossEntropy()
        self.history: List[dict] = []

    # -- прямой и обратный проходы ----------------------------------------- #
    def forward(self, x: np.ndarray, training: bool = True) -> np.ndarray:
        for layer in self.layers:
            x = layer.forward(x, training=training)
        return x  # logits

    def backward(self, grad: np.ndarray) -> None:
        for layer in reversed(self.layers):
            grad = layer.backward(grad)

    def predict_proba(self, x: np.ndarray) -> np.ndarray:
        logits = self.forward(x, training=False)
        shifted = logits - logits.max(axis=1, keepdims=True)
        exp = np.exp(shifted)
        return exp / exp.sum(axis=1, keepdims=True)

    def predict(self, x: np.ndarray) -> np.ndarray:
        return self.predict_proba(x).argmax(axis=1)

    # -- обучение ----------------------------------------------------------- #
    def loss(self, x: np.ndarray, y: np.ndarray) -> float:
        logits = self.forward(x, training=False)
        return self.loss_fn.forward(logits, y)

    def evaluate(self, x: np.ndarray, y: np.ndarray, batch_size: int = 512) -> dict:
        """Loss и accuracy на наборе данных (пакетами, чтобы не раздувать память)."""
        total_loss, correct, n = 0.0, 0, x.shape[0]
        logits_all = self.forward(x, training=False)
        shifted = logits_all - logits_all.max(axis=1, keepdims=True)
        exp = np.exp(shifted)
        probs = exp / exp.sum(axis=1, keepdims=True)
        log_probs = shifted[np.arange(n), y] - np.log(exp.sum(axis=1))
        total_loss = float(-log_probs.mean())
        pred = probs.argmax(axis=1)
        correct = int((pred == y).sum())
        return {"loss": total_loss, "accuracy": correct / n}

    def fit(self, x_train, y_train, x_val=None, y_val=None, epochs: int = 30,
            batch_size: int = 32, lr: float = 1e-3, weight_decay: float = 0.0,
            verbose: bool = True, log=None) -> List[dict]:
        """Классический цикл обучения: перемешиваем данные, мини-батчи, Adam."""
        optimizer = Adam(lr=lr)
        n = x_train.shape[0]
        self.history = []
        for epoch in range(1, epochs + 1):
            perm = self.rng.permutation(n)
            for start in range(0, n, batch_size):
                idx = perm[start:start + batch_size]
                logits = self.forward(x_train[idx], training=True)
                self.loss_fn.forward(logits, y_train[idx])
                self.backward(self.loss_fn.backward())
                optimizer.weight_decay = weight_decay
                optimizer.step(self.layers)

            train_metrics = self.evaluate(x_train, y_train)
            entry = {"epoch": epoch, "train_loss": train_metrics["loss"],
                     "train_acc": train_metrics["accuracy"]}
            if x_val is not None and y_val is not None:
                val_metrics = self.evaluate(x_val, y_val)
                entry.update({"val_loss": val_metrics["loss"],
                              "val_acc": val_metrics["accuracy"]})
            self.history.append(entry)
            if verbose:
                msg = (f"Эпоха {epoch:>3}/{epochs} | "
                       f"loss: {entry['train_loss']:.4f} | acc: {entry['train_acc']:.4f}")
                if "val_acc" in entry:
                    msg += f" | val_loss: {entry['val_loss']:.4f} | val_acc: {entry['val_acc']:.4f}"
                print(msg, flush=True) if log is None else log(msg)
        return self.history

    # -- сохранение / загрузка ---------------------------------------------- #
    def save(self, path: str) -> None:
        arrays: dict = {}
        meta = {"layer_types": []}
        for i, layer in enumerate(self.layers):
            meta["layer_types"].append(type(layer).__name__)
            for name, p in zip(layer.param_names, layer.params):
                arrays[f"layer{i}_{name}"] = p
        np.savez(path, __meta__=json.dumps(meta), **arrays)

    @classmethod
    def load(cls, path: str) -> "Model":
        data = np.load(path, allow_pickle=False)
        meta = json.loads(str(data["__meta__"]))
        # Восстанавливаем архитектуру: чередование Dense/ReLU определяется
        # по последовательности типов и сохранённым размерностям весов.
        layers: List[Layer] = []
        pending_in = None
        for i, ltype in enumerate(meta["layer_types"]):
            if ltype == "Dense":
                w = data[f"layer{i}_W"]
                b = data[f"layer{i}_b"]
                dense = Dense.__new__(Dense)
                dense.W = w.copy()
                dense.b = b.copy()
                dense._dW = np.zeros_like(dense.W)
                dense._db = np.zeros_like(dense.b)
                dense._x = None
                layers.append(dense)
                pending_in = None
            elif ltype == "ReLU":
                layers.append(ReLU())
            elif ltype == "Dropout":
                layers.append(Dropout(0.0))  # при инференсе dropout не работает
            else:
                raise ValueError(f"Неизвестный слой: {ltype}")
        model = cls.__new__(cls)
        model.layers = layers
        model.rng = np.random.default_rng()
        model.loss_fn = SoftmaxCrossEntropy()
        model.history = []
        return model
