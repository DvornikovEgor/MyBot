"""Тесты движка: прямые значения и градиенты (сверка с численной производной)."""

import math
import random
import unittest

from mybot.engine import Adam, SGD, Tensor
from mybot.engine import functional as F


def numerical_grad(fn, tensors, eps=1e-3):
    """Численный градиент функции по нескольким тензорам (центральная разность)."""
    grads = []
    for t in tensors:
        g = []
        for i in range(t.size):
            old = t.data[i]
            t.data[i] = old + eps
            plus = fn().item()
            t.data[i] = old - eps
            minus = fn().item()
            t.data[i] = old
            g.append((plus - minus) / (2 * eps))
        grads.append(g)
    return grads


def assert_close(test, got, want, tol=1e-4, msg=""):
    test.assertEqual(len(got), len(want), "длины не совпадают: " + msg)
    for i, (a, b) in enumerate(zip(got, want)):
        test.assertTrue(
            abs(a - b) <= tol + 1e-3 * abs(b),
            "%s элемент %d: получено %.6f, ожидалось %.6f" % (msg, i, a, b),
        )


class TestTensorBasics(unittest.TestCase):
    def test_shape_and_flatten(self):
        t = Tensor([[1, 2, 3], [4, 5, 6]])
        self.assertEqual(t.shape, (2, 3))
        self.assertEqual(t.data, [1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
        self.assertEqual(t.tolist(), [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])

    def test_matmul_shapes(self):
        a = Tensor([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])      # (2,3)
        b = Tensor([[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]])    # (3,2)
        self.assertEqual((a.matmul(b)).shape, (2, 2))
        self.assertEqual((a.matmul(b)).tolist(), [[4.0, 5.0], [10.0, 11.0]])

        v = Tensor([1.0, 2.0, 3.0])
        self.assertEqual(v.matmul(v).shape, (1, 1))
        self.assertEqual(v.matmul(v).item(), 14.0)
        self.assertEqual(a.matmul(Tensor([1.0, 1.0, 1.0])).shape, (2,))

    def test_broadcast_add(self):
        a = Tensor([[1.0, 2.0], [3.0, 4.0]])
        b = Tensor([[10.0, 20.0]])                      # (1,2) — как bias
        self.assertEqual((a + b).tolist(), [[11.0, 22.0], [13.0, 24.0]])
        self.assertEqual((a + 1.0).tolist(), [[2.0, 3.0], [4.0, 5.0]])
        self.assertEqual((a * Tensor([[0.0], [1.0]])).tolist(), [[0.0, 0.0], [3.0, 4.0]])

    def test_transpose_and_reshape(self):
        a = Tensor([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
        self.assertEqual(a.T.shape, (3, 2))
        self.assertEqual(a.T.tolist(), [[1.0, 4.0], [2.0, 5.0], [3.0, 6.0]])
        self.assertEqual(a.reshape(6).shape, (6,))
        self.assertEqual((a.T.T).tolist(), a.tolist())

    def test_reduce(self):
        a = Tensor([[1.0, 2.0], [3.0, 4.0]])
        self.assertEqual(a.sum().item(), 10.0)
        self.assertEqual(a.mean().item(), 2.5)
        self.assertEqual(a.sum(dim=0).tolist(), [4.0, 6.0])
        self.assertEqual(a.sum(dim=1).tolist(), [3.0, 7.0])
        self.assertEqual(a.max().item(), 4.0)
        self.assertEqual(a.max(dim=0).tolist(), [3.0, 4.0])
        self.assertEqual(a.argmax(dim=-1), [1, 1])

    def test_no_grad(self):
        from mybot.engine import no_grad
        with no_grad():
            a = Tensor([1.0, 2.0], requires_grad=True)
            b = (a * 3.0).sum()
        self.assertFalse(a.requires_grad)
        self.assertFalse(b.requires_grad)


class TestGradients(unittest.TestCase):
    def test_grad_add_mul(self):
        a = Tensor([1.0, -2.0, 3.0], requires_grad=True)
        b = Tensor([0.5, 0.5, 2.0], requires_grad=True)
        loss = (a * b + a).sum()
        loss.backward()
        ga, gb = numerical_grad(lambda: (a * b + a).sum(), [a, b])
        assert_close(self, a.grad, ga)
        assert_close(self, b.grad, gb)

    def test_grad_matmul(self):
        a = Tensor([[1.0, 2.0, 3.0], [-1.0, 0.5, 2.0]], requires_grad=True)
        b = Tensor([[0.3, 1.0], [-2.0, 0.7], [1.5, -0.5]], requires_grad=True)
        loss = a.matmul(b).sum()
        loss.backward()
        ga, gb = numerical_grad(lambda: a.matmul(b).sum(), [a, b])
        assert_close(self, a.grad, ga)
        assert_close(self, b.grad, gb)

    def test_grad_broadcast(self):
        a = Tensor([[1.0, 2.0], [3.0, 4.0]], requires_grad=True)
        b = Tensor([[1.0, -1.0]], requires_grad=True)
        loss = (a * b).sum()
        loss.backward()
        ga, gb = numerical_grad(lambda: (a * b).sum(), [a, b])
        assert_close(self, a.grad, ga)
        assert_close(self, b.grad, gb)
        # градиент по строке смещения — это сумма по строкам
        self.assertAlmostEqual(b.grad[0], a.data[0] + a.data[2])
        self.assertAlmostEqual(b.grad[1], a.data[1] + a.data[3])

    def test_grad_activations(self):
        cases = {
            "tanh": [-1.5, 0.0, 0.7, 2.0],
            "sigmoid": [-1.5, 0.0, 0.7, 2.0],
            "relu": [-1.5, 0.3, 0.7, 2.0],
            "exp": [-1.0, 0.0, 0.7, 1.2],
            "log": [0.5, 1.0, 2.0, 3.0],
        }
        for op, values in cases.items():
            with self.subTest(op=op):
                x = Tensor(values, requires_grad=True)
                out = getattr(x, op)()
                loss = (out * out).sum()
                loss.backward()
                expect = numerical_grad(lambda: (getattr(x, op)() ** 2).sum(), [x])[0]
                assert_close(self, x.grad, expect, msg=op)

    def test_grad_softmax_and_ce(self):
        logits = Tensor([[0.4, 1.2, -0.5], [2.0, 0.1, 0.3]], requires_grad=True)
        targets = [1, 0]
        loss = F.cross_entropy(logits, targets)
        loss.backward()
        g = numerical_grad(lambda: F.cross_entropy(logits, targets), [logits])[0]
        assert_close(self, logits.grad, g)
        # строки softmax дают единицу
        probs = F.softmax(logits.detach())
        for row in range(probs.shape[0]):
            self.assertAlmostEqual(sum(probs.data[row * 3:(row + 1) * 3]), 1.0, places=6)

    def test_grad_mean_and_max(self):
        x = Tensor([[1.0, 5.0, 2.0], [-3.0, 0.0, 4.0]], requires_grad=True)
        loss = x.mean() + x.max() * 0.5
        loss.backward()
        g = numerical_grad(lambda: x.mean() + x.max() * 0.5, [x])[0]
        assert_close(self, x.grad, g)

    def test_grad_transpose_reshape(self):
        x = Tensor([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]], requires_grad=True)
        loss = (x.T.matmul(x)).sum()
        loss.backward()
        g = numerical_grad(lambda: (x.T.matmul(x)).sum(), [x])[0]
        assert_close(self, x.grad, g)


class TestOptimizers(unittest.TestCase):
    def _quadratic(self, opt_cls, **kwargs):
        w = Tensor([3.0, -4.0], requires_grad=True)
        opt = opt_cls([w], **kwargs)
        first = None
        for _ in range(300):
            loss = (w * w).sum()
            if first is None:
                first = loss.item()
            opt.zero_grad()
            loss.backward()
            opt.step()
        return first, loss.item()

    def test_sgd_reduces_loss(self):
        first, last = self._quadratic(SGD, lr=0.05, momentum=0.9)
        self.assertLess(last, first * 1e-3)

    def test_adam_reduces_loss(self):
        first, last = self._quadratic(Adam, lr=0.1)
        self.assertLess(last, first * 1e-3)


if __name__ == "__main__":
    unittest.main()
