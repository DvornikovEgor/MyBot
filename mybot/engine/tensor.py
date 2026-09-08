"""Минимальный движок автоматического дифференцирования на чистом Python.

Здесь реализовано всё, что нужно для обучения нейросетей:

* ``Tensor`` — многомерный массив (плоский список чисел + форма);
* прямой проход для ~20 операций (сложения, умножения матриц, активации...);
* обратный проход: у каждой операции есть своя локальная производная,
  ``Tensor.backward()`` обходит граф вычислений в обратном топологическом
  порядке и накапливает градиенты.

Никаких зависимостей — только стандартная библиотека.
"""

from __future__ import annotations

import math
import operator
from contextlib import contextmanager
from itertools import product
from typing import Callable, Iterable, List, Optional, Sequence, Tuple

__all__ = ["Tensor", "no_grad", "grad_enabled"]

# ---------------------------------------------------------------------------
# Глобальный режим: в ``no_grad`` граф не строится (используется при генерации)
# ---------------------------------------------------------------------------

_GRAD_ENABLED = True


def grad_enabled() -> bool:
    """Включено ли построение графа вычислений."""
    return _GRAD_ENABLED


@contextmanager
def no_grad():
    """Контекст, в котором градиенты не считаются (инференс, генерация текста)."""
    global _GRAD_ENABLED
    old = _GRAD_ENABLED
    _GRAD_ENABLED = False
    try:
        yield
    finally:
        _GRAD_ENABLED = old


# ---------------------------------------------------------------------------
# Вспомогательные функции над формами и плоскими данными
# ---------------------------------------------------------------------------


def _size(shape: Sequence[int]) -> int:
    n = 1
    for d in shape:
        n *= d
    return n


def _ravel(idx: Sequence[int], shape: Sequence[int]) -> int:
    """Преобразовать мультииндекс в плоский индекс (row-major)."""
    r = 0
    for i, s in zip(idx, shape):
        r = r * s + i
    return r


def _iter_indices(shape: Sequence[int]):
    """Все мультииндексы данной формы."""
    return product(*[range(s) for s in shape])


def _flatten(obj) -> Tuple[List[float], tuple]:
    """Развернуть число / вложенные списки / Tensor в (плоский список, форма)."""
    if isinstance(obj, Tensor):
        return list(obj.data), tuple(obj.shape)
    if isinstance(obj, (int, float)):
        return [float(obj)], ()
    seq = list(obj)
    if not seq:
        return [], (0,)
    parts = [_flatten(x) for x in seq]
    first_shape = parts[0][1]
    if any(p[1] != first_shape for p in parts):
        raise ValueError("неоднородная вложенность списков: %r" % (obj,))
    flat: List[float] = []
    for p in parts:
        flat.extend(p[0])
    return flat, (len(seq),) + first_shape


def _accum(grad: Optional[List[float]], new: List[float]) -> List[float]:
    """Прибавить градиент к уже накопленному."""
    if grad is None:
        return new
    if len(grad) != len(new):
        raise ValueError("размерности градиентов не совпадают")
    return [g + n for g, n in zip(grad, new)]


def _broadcast_shapes(a: Sequence[int], b: Sequence[int]) -> Tuple[tuple, tuple, tuple]:
    """Стандартное правило бродкастинга: выравнивание справа, 1 -> растягивается."""
    nd = max(len(a), len(b))
    ra = (1,) * (nd - len(a)) + tuple(a)
    rb = (1,) * (nd - len(b)) + tuple(b)
    out = []
    for x, y in zip(ra, rb):
        if x == y:
            out.append(x)
        elif x == 1:
            out.append(y)
        elif y == 1:
            out.append(x)
        else:
            raise ValueError("формы несовместимы для бродкастинга: %r и %r" % (tuple(a), tuple(b)))
    return tuple(out), ra, rb


def _expand(flat: List[float], shape: Sequence[int], target: Sequence[int]) -> List[float]:
    """Растянуть данные до формы ``target`` (дублируя оси размера 1)."""
    if tuple(shape) == tuple(target):
        return list(flat)
    nd = len(target)
    shp = (1,) * (nd - len(shape)) + tuple(shape)
    out = [0.0] * _size(target)
    for idx in _iter_indices(target):
        src = tuple(0 if shp[d] == 1 else idx[d] for d in range(nd))
        out[_ravel(idx, target)] = flat[_ravel(src, shp)]
    return out


def _reduce_to_shape(flat: List[float], from_shape: Sequence[int], to_shape: Sequence[int]) -> List[float]:
    """Обратная операция к ``_expand``: просуммировать градиент до формы входа."""
    if tuple(from_shape) == tuple(to_shape):
        return list(flat)
    nd = len(from_shape)
    to = (1,) * (nd - len(to_shape)) + tuple(to_shape)
    out = [0.0] * _size(to)
    for idx in _iter_indices(from_shape):
        oidx = tuple(0 if to[d] == 1 else idx[d] for d in range(nd))
        out[_ravel(oidx, to)] += flat[_ravel(idx, from_shape)]
    return out


def _transpose_raw(flat: List[float], shape: Sequence[int]) -> List[float]:
    """Транспонирование двумерной матрицы."""
    r, c = shape
    out = [0.0] * (r * c)
    for i in range(r):
        row = flat[i * c:(i + 1) * c]
        for j in range(c):
            out[j * r + i] = row[j]
    return out


def _matmul_raw(a: List[float], a_shape: Sequence[int], b: List[float], b_shape: Sequence[int]) -> List[float]:
    """Умножение матриц (n,k) @ (k,m) -> (n,m)."""
    n, k = a_shape
    k2, m = b_shape
    if k != k2:
        raise ValueError("несовместимые размеры матриц: %r и %r" % (tuple(a_shape), tuple(b_shape)))
    # столбцы второй матрицы — так внутренний цикл сворачивается в sum(map(mul,...))
    cols = [[b[r * m + j] for r in range(k2)] for j in range(m)]
    out = [0.0] * (n * m)
    mul = operator.mul
    for i in range(n):
        arow = a[i * k:(i + 1) * k]
        base = i * m
        for j in range(m):
            out[base + j] = sum(map(mul, arow, cols[j]))
    return out


def _reduce(data: List[float], shape: Sequence[int], dims: Optional[Sequence[int]], keepdim: bool):
    """Суммирование по осям. Возвращает (результат, форма, отображение индексов)."""
    if dims is None:
        dims = tuple(range(len(shape)))
    dims = tuple(d if d >= 0 else d + len(shape) for d in dims)
    out_shape = tuple(
        1 if d in dims else s for d, s in enumerate(shape)
    ) if keepdim else tuple(s for d, s in enumerate(shape) if d not in dims)
    mapping: List[int] = []
    for idx in _iter_indices(shape):
        oidx = tuple(0 if d in dims else idx[d] for d in range(len(shape)))
        if not keepdim:
            oidx = tuple(v for d, v in enumerate(oidx) if d not in dims)
        mapping.append(_ravel(oidx, out_shape))
    out = [0.0] * _size(out_shape)
    for i, oi in enumerate(mapping):
        out[oi] += data[i]
    return out, out_shape, mapping


# ---------------------------------------------------------------------------
# Тензор
# ---------------------------------------------------------------------------


class Tensor:
    """Массив чисел с поддержкой автоматического дифференцирования."""

    __slots__ = ("data", "shape", "grad", "requires_grad", "_backward", "_prev", "op")

    def __init__(self, data, shape: Optional[Sequence[int]] = None, *,
                 requires_grad: bool = False, _children: Iterable["Tensor"] = (), op: str = ""):
        global _GRAD_ENABLED
        if isinstance(data, Tensor):
            data, shape = data.data, data.shape
        else:
            flat, inferred = _flatten(data)
            data = flat
            if shape is None:
                shape = inferred
        shape = () if shape is None else tuple(int(s) for s in shape)
        if shape == ():
            shape = ()
        self.data: List[float] = [float(v) for v in data]
        if shape != () and _size(shape) != len(self.data):
            raise ValueError(
                "форма %r не соответствует числу элементов %d" % (shape, len(self.data))
            )
        if shape == () and len(self.data) != 1:
            raise ValueError("скалярный тензор должен содержать один элемент")
        self.shape: tuple = shape
        self.grad: Optional[List[float]] = None
        self.requires_grad: bool = bool(requires_grad) and _GRAD_ENABLED
        self._backward: Optional[Callable[[], None]] = None
        self._prev: Tuple[Tensor, ...] = tuple(_children)
        self.op: str = op

    # --- служебное ---------------------------------------------------------

    @property
    def ndim(self) -> int:
        return len(self.shape)

    @property
    def size(self) -> int:
        return _size(self.shape)

    @property
    def T(self) -> "Tensor":
        """Транспонирование (для 1D возвращается копия)."""
        return self.transpose()

    def item(self) -> float:
        return self.data[0]

    def tolist(self):
        """Преобразовать обратно во вложенные списки питоновских float."""
        if self.ndim == 0:
            return self.data[0]
        out = self.data
        for d in reversed(self.shape[1:]):
            out = [out[i * d:(i + 1) * d] for i in range(len(out) // d)]
        return out

    def reshape(self, *new_shape) -> "Tensor":
        if len(new_shape) == 1 and isinstance(new_shape[0], (tuple, list)):
            new_shape = tuple(new_shape[0])
        new_shape = tuple(int(s) for s in new_shape)
        if _size(new_shape) != self.size:
            raise ValueError("нельзя преобразовать %r в %r" % (self.shape, new_shape))
        out = Tensor(self.data, new_shape, requires_grad=self.requires_grad,
                     _children=(self,) if self.requires_grad else (), op="reshape")
        if self.requires_grad:
            def _backward():
                self.grad = _accum(self.grad, list(out.grad))
            out._backward = _backward
        return out

    def transpose(self) -> "Tensor":
        if self.ndim == 0:
            return self.reshape(())
        if self.ndim == 1:
            return self.reshape(self.shape)
        r, c = self.shape
        out = Tensor(_transpose_raw(self.data, self.shape), (c, r),
                     requires_grad=self.requires_grad,
                     _children=(self,) if self.requires_grad else (), op="T")
        if self.requires_grad:
            def _backward():
                self.grad = _accum(self.grad, _transpose_raw(out.grad, out.shape))
            out._backward = _backward
        return out

    def detach(self) -> "Tensor":
        """Копия без градиента (отрезать от графа)."""
        return Tensor(self.data, self.shape, requires_grad=False)

    def copy(self) -> "Tensor":
        return Tensor(self.data, self.shape, requires_grad=self.requires_grad)

    def zero_grad(self) -> None:
        self.grad = None

    # --- обратный проход ---------------------------------------------------

    def backward(self, grad=None) -> None:
        """Посчитать градиенты всех параметров, от которых зависит тензор."""
        if grad is None:
            if self.size != 1:
                raise RuntimeError(
                    "backward() без аргумента допустим только для скаляра; "
                    "передайте внешний градиент"
                )
            grad = [1.0]
        else:
            grad = [float(g) for g in _flatten(grad)[0]]
            if len(grad) == 1 and self.size > 1:
                grad = grad * self.size
            if len(grad) != self.size:
                raise ValueError("размер внешнего градиента не совпадает с тензором")
        self.grad = _accum(self.grad, grad)

        # топологическая сортировка графа (итеративный DFS)
        topo: List[Tensor] = []
        seen = set()
        stack = [(self, False)]
        while stack:
            node, processed = stack.pop()
            if processed:
                topo.append(node)
                continue
            if id(node) in seen:
                continue
            seen.add(id(node))
            stack.append((node, True))
            for child in node._prev:
                if child.requires_grad:
                    stack.append((child, False))
        for node in reversed(topo):
            if node._backward is not None:
                node._backward()

    def _walk_graph(self):
        """Все узлы графа (для обнуления градиентов)."""
        seen = set()
        stack = [self]
        while stack:
            node = stack.pop()
            if id(node) in seen:
                continue
            seen.add(id(node))
            yield node
            stack.extend(node._prev)

    def zero_grad_tree(self) -> None:
        """Обнулить градиенты во всём графе."""
        for node in self._walk_graph():
            node.grad = None

    # --- поэлементные операции --------------------------------------------

    @staticmethod
    def _unary(a: "Tensor", f: Callable[[float], float],
               df: Callable[[float], float], op: str) -> "Tensor":
        data = [f(x) for x in a.data]
        out = Tensor(data, a.shape, requires_grad=a.requires_grad,
                     _children=(a,) if a.requires_grad else (), op=op)
        if a.requires_grad:
            def _backward():
                a.grad = _accum(a.grad, [df(x) * g for x, g in zip(a.data, out.grad)])
            out._backward = _backward
        return out

    @classmethod
    def _binary(cls, a, b, f, da, db, op: str) -> "Tensor":
        if not isinstance(a, Tensor):
            a = Tensor(a)
        if not isinstance(b, Tensor):
            b = Tensor(b)
        out_shape, sa, sb = _broadcast_shapes(a.shape, b.shape)
        A = _expand(a.data, a.shape, out_shape)
        B = _expand(b.data, b.shape, out_shape)
        data = [f(x, y) for x, y in zip(A, B)]
        requires = a.requires_grad or b.requires_grad
        out = Tensor(data, out_shape, requires_grad=requires,
                     _children=(a, b) if requires else (), op=op)
        if requires:
            def _backward():
                go = out.grad
                if a.requires_grad:
                    g = [da(x, y) * gv for x, y, gv in zip(A, B, go)]
                    a.grad = _accum(a.grad, _reduce_to_shape(g, out_shape, a.shape))
                if b.requires_grad:
                    g = [db(x, y) * gv for x, y, gv in zip(A, B, go)]
                    b.grad = _accum(b.grad, _reduce_to_shape(g, out_shape, b.shape))
            out._backward = _backward
        return out

    def __add__(self, other):
        return Tensor._binary(self, other, lambda x, y: x + y,
                              lambda x, y: 1.0, lambda x, y: 1.0, "+")

    __radd__ = __add__

    def __sub__(self, other):
        return Tensor._binary(self, other, lambda x, y: x - y,
                              lambda x, y: 1.0, lambda x, y: -1.0, "-")

    def __rsub__(self, other):
        return Tensor._binary(other, self, lambda x, y: x - y,
                              lambda x, y: 1.0, lambda x, y: -1.0, "-")

    def __mul__(self, other):
        return Tensor._binary(self, other, lambda x, y: x * y,
                              lambda x, y: y, lambda x, y: x, "*")

    __rmul__ = __mul__

    def __truediv__(self, other):
        return Tensor._binary(self, other, lambda x, y: x / y,
                              lambda x, y: 1.0 / y, lambda x, y: -x / (y * y), "/")

    def __rtruediv__(self, other):
        return Tensor._binary(other, self, lambda x, y: x / y,
                              lambda x, y: 1.0 / y, lambda x, y: -x / (y * y), "/")

    def __neg__(self):
        return self._unary(self, lambda x: -x, lambda x: -1.0, "neg")

    def __pow__(self, power: float):
        p = float(power)
        return self._unary(self, lambda x: x ** p, lambda x: p * x ** (p - 1.0), "pow")

    def exp(self):
        return self._unary(self, math.exp, math.exp, "exp")

    def log(self):
        return self._unary(self, lambda x: math.log(x + 1e-12), lambda x: 1.0 / (x + 1e-12), "log")

    def tanh(self):
        def f(x):
            if x > 20.0:
                return 1.0
            if x < -20.0:
                return -1.0
            return math.tanh(x)
        return self._unary(self, f, lambda x: 1.0 - f(x) ** 2, "tanh")

    def relu(self):
        return self._unary(self, lambda x: x if x > 0.0 else 0.0,
                           lambda x: 1.0 if x > 0.0 else 0.0, "relu")

    def sigmoid(self):
        def f(x):
            if x >= 0.0:
                return 1.0 / (1.0 + math.exp(-x))
            e = math.exp(x)
            return e / (1.0 + e)
        return self._unary(self, f, lambda x: f(x) * (1.0 - f(x)), "sigmoid")

    def matmul(self, other: "Tensor") -> "Tensor":
        """Матричное умножение: (n,k) @ (k,m), (k,) @ (k,m), (n,k) @ (k,) и т.д."""
        a, b = self, other
        if not isinstance(b, Tensor):
            b = Tensor(b)
        a2 = a if a.ndim == 2 else a.reshape(1, a.size)
        b2 = b if b.ndim == 2 else b.reshape(b.size, 1)
        n, k = a2.shape
        k2, m = b2.shape
        if k != k2:
            raise ValueError("несовместимые размеры: %r и %r" % (a.shape, b.shape))
        data = _matmul_raw(a2.data, a2.shape, b2.data, b2.shape)
        if a.ndim == 1 and b.ndim == 1:
            out_shape = (1, 1)
        elif a.ndim == 1:
            out_shape = (m,)
        elif b.ndim == 1:
            out_shape = (n,)
        else:
            out_shape = (n, m)
        requires = a.requires_grad or b.requires_grad
        out = Tensor(data, out_shape, requires_grad=requires,
                     _children=(a, b) if requires else (), op="@")
        if requires:
            bT = _transpose_raw(b2.data, b2.shape)     # (m,k)
            aT = _transpose_raw(a2.data, a2.shape)     # (k,n)

            def _backward():
                gy = out.grad            # (n,m) в плоском виде
                if a.requires_grad:
                    ga = _matmul_raw(gy, (n, m), bT, (m, k))
                    a.grad = _accum(a.grad, ga)
                if b.requires_grad:
                    gb = _matmul_raw(aT, (k, n), gy, (n, m))
                    b.grad = _accum(b.grad, gb)
            out._backward = _backward
        return out

    # --- свёртки (редукции) -------------------------------------------------

    def sum(self, dim=None, keepdim: bool = False) -> "Tensor":
        dims = None if dim is None else (dim if isinstance(dim, (tuple, list)) else (dim,))
        data, out_shape, mapping = _reduce(self.data, self.shape, dims, keepdim)
        count = self.size // max(_size(out_shape), 1)
        out = Tensor(data, out_shape, requires_grad=self.requires_grad,
                     _children=(self,) if self.requires_grad else (), op="sum")
        if self.requires_grad:
            def _backward():
                g = [out.grad[m] for m in mapping]
                self.grad = _accum(self.grad, g)
            out._backward = _backward
        return out

    def max(self, dim=None, keepdim: bool = False) -> "Tensor":
        """Максимум по осям (градиент течёт только через максимальный элемент)."""
        nd = self.ndim
        if dim is None:
            dims = tuple(range(nd))
        else:
            dims = (dim,) if isinstance(dim, int) else tuple(dim)
        dims = tuple(d if d >= 0 else d + nd for d in dims)
        out_shape = tuple(
            1 if d in dims else s for d, s in enumerate(self.shape)
        ) if keepdim else tuple(s for d, s in enumerate(self.shape) if d not in dims)

        mapping: List[int] = []
        for idx in _iter_indices(self.shape):
            oidx = tuple(0 if d in dims else idx[d] for d in range(nd))
            if not keepdim:
                oidx = tuple(v for d, v in enumerate(oidx) if d not in dims)
            mapping.append(_ravel(oidx, out_shape))
        out = [0.0] * _size(out_shape)
        argmax: List[int] = [-1] * _size(out_shape)
        for i, oi in enumerate(mapping):
            v = self.data[i]
            if argmax[oi] < 0 or v > out[oi]:
                out[oi] = v
                argmax[oi] = i

        res = Tensor(out, out_shape, requires_grad=self.requires_grad,
                     _children=(self,) if self.requires_grad else (), op="max")
        if self.requires_grad:
            def _backward():
                g = [0.0] * self.size
                for i, oi in enumerate(mapping):
                    if argmax[oi] == i:
                        g[i] += res.grad[oi]
                self.grad = _accum(self.grad, g)
            res._backward = _backward
        return res

    def argmax(self, dim: int = -1) -> List[int]:
        """Индексы максимума (обычный список, без градиентов)."""
        if self.ndim == 0:
            return [0]
        d = dim if dim >= 0 else dim + self.ndim
        other = [s for i, s in enumerate(self.shape) if i != d]
        out = []
        for rest in _iter_indices(other):
            best_i, best_v = 0, None
            for i in range(self.shape[d]):
                idx = list(rest[:d]) + [i] + list(rest[d:])
                v = self.data[_ravel(idx, self.shape)]
                if best_v is None or v > best_v:
                    best_i, best_v = i, v
            out.append(best_i)
        return out

    def mean(self, dim=None, keepdim: bool = False) -> "Tensor":
        dims = None if dim is None else (dim if isinstance(dim, (tuple, list)) else (dim,))
        data, out_shape, mapping = _reduce(self.data, self.shape, dims, keepdim)
        count = self.size / max(_size(out_shape), 1)
        data = [v / count for v in data]
        out = Tensor(data, out_shape, requires_grad=self.requires_grad,
                     _children=(self,) if self.requires_grad else (), op="mean")
        if self.requires_grad:
            def _backward():
                g = [out.grad[m] / count for m in mapping]
                self.grad = _accum(self.grad, g)
            out._backward = _backward
        return out

    def __repr__(self) -> str:
        head = ", ".join("%+.4f" % v for v in self.data[:6])
        if len(self.data) > 6:
            head += ", ..."
        extra = ", grad" if self.grad is not None else ""
        return "Tensor([%s], shape=%r, op=%r%s)" % (head, self.shape, self.op or "leaf", extra)

    def __eq__(self, other):  # сравнение по значению (для тестов)
        if not isinstance(other, Tensor):
            other = Tensor(other)
        return self.shape == other.shape and self.data == other.data

    __hash__ = object.__hash__
