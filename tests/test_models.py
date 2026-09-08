"""Тесты моделей: MLP выучивает XOR, RNN учится на тексте, словарь корректен."""

import unittest

from mybot.data import CharVocab, TextDataset
from mybot.engine import Adam, F, Tensor
from mybot.engine.utils import accuracy, set_seed
from mybot.models import CharRNN, MLP
from mybot.models.char_rnn import one_hot_input


class TestMLP(unittest.TestCase):
    def test_learns_xor(self):
        set_seed(0)
        X = [[0.0, 0.0], [0.0, 1.0], [1.0, 0.0], [1.0, 1.0]]
        Y = [0, 1, 1, 0]
        model = MLP([2, 8, 2], hidden_activation="tanh")
        opt = Adam(model.parameters(), lr=0.05)
        x = Tensor(X, (4, 2))
        for _ in range(300):
            loss = F.cross_entropy(model(x), Y)
            opt.zero_grad()
            loss.backward()
            opt.step()
        self.assertEqual(accuracy(model(x), Y), 1.0)

    def test_shapes_and_params(self):
        model = MLP([3, 5, 4, 2])
        out = model(Tensor([[1.0, 2.0, 3.0]]))
        self.assertEqual(out.shape, (1, 2))
        # (3*5+5) + (5*4+4) + (4*2+2) = 20 + 24 + 10 = 54
        self.assertEqual(sum(p.size for p in model.parameters()), 54)

    def test_predict_proba_sums_to_one(self):
        model = MLP([2, 4, 3])
        probs = model.predict_proba(Tensor([[0.5, -0.5]]))
        self.assertAlmostEqual(sum(probs.data), 1.0, places=6)


class TestVocab(unittest.TestCase):
    def test_roundtrip(self):
        vocab = CharVocab.from_text("привет мир")
        ids = vocab.encode("привет")
        self.assertEqual(vocab.decode(ids), "привет")

    def test_unknown_chars_dropped(self):
        vocab = CharVocab.from_text("абв")
        self.assertEqual(vocab.encode("а?б"), vocab.encode("аб"))

    def test_save_load(self):
        vocab = CharVocab.from_text("абвгд")
        clone = CharVocab.from_dict(vocab.to_dict())
        self.assertEqual(clone.itos, vocab.itos)

    def test_dataset_pairs(self):
        ds = TextDataset([0, 1, 2, 3, 4], seq_len=2)
        self.assertEqual(len(ds), 3)
        x, y = ds[0]
        self.assertEqual((x, y), ([0, 1], [1, 2]))


class TestCharRNN(unittest.TestCase):
    def test_forward_shapes(self):
        model = CharRNN(vocab_size=5, hidden_size=8)
        h = model.init_hidden()
        self.assertEqual(h.shape, (1, 8))
        logits, h2 = model.step(one_hot_input(5, 2), h)
        self.assertEqual(logits.shape, (1, 5))
        self.assertEqual(h2.shape, (1, 8))

    def test_overfits_tiny_sequence(self):
        """Модель должна запомнить одну короткую строку почти дословно."""
        set_seed(1)
        text = "абвгабвг"
        vocab = CharVocab.from_text(text)
        ids = vocab.encode(text)
        model = CharRNN(len(vocab), hidden_size=32)
        opt = Adam(model.parameters(), lr=0.02)
        xs = [one_hot_input(len(vocab), i) for i in ids[:-1]]
        targets = ids[1:]
        first = last = None
        for step in range(200):
            logits, _ = model.forward(xs)
            loss = model.sequence_loss(logits, targets)
            if first is None:
                first = loss.item()
            opt.zero_grad()
            loss.backward()
            opt.step()
            last = loss.item()
        self.assertLess(last, first * 0.2)
        self.assertLess(last, 0.5)

    def test_generate_returns_text(self):
        set_seed(2)
        vocab = CharVocab.from_text("абвгде ")
        model = CharRNN(len(vocab), hidden_size=8)
        out = model.generate(vocab, prompt="аб", length=10, temperature=0.8)
        self.assertIsInstance(out, str)
        self.assertLessEqual(len(out), 10)
        self.assertTrue(all(ch in vocab.stoi for ch in out))


if __name__ == "__main__":
    unittest.main()
