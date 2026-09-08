"""MyBot — маленькая нейросетевая библиотека на чистом Python.

Без numpy, без PyTorch: тензоры, автоградиент, слои, оптимизаторы и пара
обучаемых моделей (MLP и символьная RNN).

Пример::

    from mybot import Tensor, Linear, Adam, F

    model = Linear(2, 1)
    opt = Adam(model.parameters(), lr=0.1)
    x, y = Tensor([[0.0, 0.0], [1.0, 1.0]]), Tensor([[0.0], [1.0]])
    for _ in range(100):
        loss = F.mse_loss(model(x), y)
        opt.zero_grad()
        loss.backward()
        opt.step()
"""

from .engine import (
    Tensor, no_grad, grad_enabled, F, nn, utils,
    Module, Linear, RNNCell, Sequential, Dropout, Tanh, ReLU, Sigmoid, SGD, Adam,
)
from .models import MLP, CharRNN
from .data import CharVocab, TextDataset, load_text
from .imaging import generate as generate_image, TextToImage

__version__ = "0.2.0"

__all__ = [
    "Tensor", "no_grad", "grad_enabled", "F", "nn", "utils",
    "Module", "Linear", "RNNCell", "Sequential", "Dropout", "Tanh", "ReLU", "Sigmoid",
    "SGD", "Adam", "MLP", "CharRNN", "CharVocab", "TextDataset", "load_text",
    "generate_image", "TextToImage",
    "__version__",
]
