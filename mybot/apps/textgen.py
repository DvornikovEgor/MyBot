"""Демо 3: символьная RNN учится разговаривать (генерация текста).

Запуск::

    python -m mybot.apps.textgen --steps 800            # обучение + примеры
    python -m mybot.apps.textgen --load --chat          # поболтать с обученной моделью
    python -m mybot.apps.textgen --text my_novel.txt    # обучить на своём тексте

Модель предсказывает следующий символ по предыдущим. Она не «знает» ответов,
но выучивает структуру диалога и правдоподобно его продолжает.
"""

from __future__ import annotations

import argparse
import math
import random
import sys
from pathlib import Path

from ..data import CharVocab, TextDataset, load_text
from ..engine import Adam
from ..engine.utils import ProgressBar, clip_grad_norm, load_checkpoint, save_checkpoint, set_seed
from ..models.char_rnn import CharRNN, one_hot_input

DEFAULT_CHECKPOINT = Path(__file__).resolve().parents[2] / "checkpoints" / "char_rnn.json"

SAMPLE_PROMPTS = [
    "человек: привет!\nбот:",
    "человек: что такое нейросеть?\nбот:",
    "человек: расскажи анекдот.\nбот:",
]


def train(text: str, seq_len: int = 32, hidden: int = 96, steps: int = 800,
          lr: float = 5e-3, batch_size: int = 1, sample_every: int = 100,
          sample_len: int = 160, temperature: float = 0.9, seed: int = 42,
          clip: float = 5.0, verbose: bool = True, checkpoint: str = None):
    """Обучить символьную RNN и вернуть (модель, словарь, историю ошибок)."""
    set_seed(seed)
    vocab = CharVocab.from_text(text)
    ids = vocab.encode(text)
    dataset = TextDataset(ids, seq_len)
    model = CharRNN(len(vocab), hidden)
    opt = Adam(model.parameters(), lr=lr)
    rng = random.Random(seed + 1)
    history = []

    if verbose:
        print("текст: %d символов, словарь: %d символов, окон для обучения: %d"
              % (len(text), len(vocab), len(dataset)))
        print("модель: %s, параметров: %d"
              % (model, sum(p.size for p in model.parameters())))
        print("-" * 60)

    bar = ProgressBar(steps) if verbose else None
    for step in range(1, steps + 1):
        total = None
        for _ in range(batch_size):
            xs, ys = dataset.random_item(rng)
            inputs = [one_hot_input(len(vocab), i) for i in xs]
            logits, _ = model.forward(inputs)
            loss = model.sequence_loss(logits, ys)
            total = loss if total is None else total + loss
        loss = total / batch_size

        opt.zero_grad()
        loss.backward()
        grad_norm = clip_grad_norm(model.parameters(), clip)
        opt.step()

        value = loss.item()
        history.append(value)
        if bar:
            bar.update(step, "ошибка %.3f | perplexity %.1f | |g| %.2f"
                       % (value, math.exp(min(value, 20.0)), grad_norm))

        if verbose and sample_every and (step % sample_every == 0 or step == 1):
            if bar:
                bar.stream.write("\n")
            print("[шаг %d] %s" % (step, _sample_line(model, vocab, temperature, sample_len)))
    if bar:
        bar.close()

    if checkpoint:
        Path(checkpoint).parent.mkdir(parents=True, exist_ok=True)
        save_checkpoint(model, checkpoint,
                        meta={"vocab": vocab.to_dict(), "hidden": hidden, "seq_len": seq_len,
                              "steps": steps, "loss": history[-1] if history else None})
        if verbose:
            print("веса сохранены: %s" % checkpoint)
    return model, vocab, history


def _sample_line(model, vocab, temperature: float, length: int) -> str:
    """Короткая иллюстрация: одно сгенерированное продолжение."""
    prompt = SAMPLE_PROMPTS[random.randrange(len(SAMPLE_PROMPTS))]
    return model.generate(vocab, prompt=prompt, length=length,
                          temperature=temperature).replace("\n", " ⏎ ")


def show_samples(model, vocab, temperature: float = 0.9, length: int = 200) -> None:
    """Напечатать несколько продолжений для разных реплик."""
    print("\n" + "=" * 60)
    print("Что получилось (продолжение после «бот:»):")
    print("=" * 60)
    for prompt in SAMPLE_PROMPTS:
        answer = model.generate(vocab, prompt=prompt, length=length, temperature=temperature)
        print("\n%s%s" % (prompt, answer))


def chat(model, vocab, temperature: float = 0.85, length: int = 160) -> None:
    """Диалог с моделью в консоли. Пустая строка или «выход» — завершение."""
    print("\nРежим диалога. Пишите реплики, пустая строка или «выход» — конец.")
    while True:
        try:
            line = input("вы: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nбот: до встречи!")
            return
        if not line or line.lower() in ("выход", "exit", "quit", "пока"):
            print("бот: до встречи!")
            return
        prompt = "человек: %s\nбот:" % line.lower()
        answer = model.generate(vocab, prompt=prompt, length=length,
                                temperature=temperature, stop="\nчеловек")
        print("бот:%s" % answer)


def cli() -> None:
    parser = argparse.ArgumentParser(
        description="Символьная языковая модель: обучение и генерация текста")
    parser.add_argument("--text", type=str, default=None,
                        help="свой текстовый файл (по умолчанию встроенный корпус)")
    parser.add_argument("--steps", type=int, default=800)
    parser.add_argument("--seq-len", type=int, default=32)
    parser.add_argument("--hidden", type=int, default=96)
    parser.add_argument("--lr", type=float, default=5e-3)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--sample-every", type=int, default=100)
    parser.add_argument("--temperature", type=float, default=0.9)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--checkpoint", type=str, default=str(DEFAULT_CHECKPOINT))
    parser.add_argument("--load", action="store_true", help="загрузить веса и не обучать")
    parser.add_argument("--chat", action="store_true", help="после обучения запустить диалог")
    parser.add_argument("--length", type=int, default=200, help="длина генерации")
    args = parser.parse_args()

    if args.load:
        meta = _load_or_die(args)
        vocab = CharVocab.from_dict(meta["vocab"])
        model = CharRNN(len(vocab), meta.get("hidden", args.hidden))
        load_checkpoint(model, args.checkpoint)
        print("загружены веса из %s" % args.checkpoint)
    else:
        text = load_text(args.text)
        model, vocab, _ = train(text, seq_len=args.seq_len, hidden=args.hidden,
                                steps=args.steps, lr=args.lr, batch_size=args.batch_size,
                                sample_every=args.sample_every, temperature=args.temperature,
                                seed=args.seed, checkpoint=args.checkpoint)
        show_samples(model, vocab, temperature=args.temperature, length=args.length)

    if args.chat:
        chat(model, vocab, temperature=args.temperature, length=args.length)
    elif args.load:
        show_samples(model, vocab, temperature=args.temperature, length=args.length)


def _load_or_die(args) -> dict:
    path = Path(args.checkpoint)
    if not path.exists():
        sys.exit("нет файла с весами: %s\nСначала запустите обучение: "
                 "python -m mybot.apps.textgen --steps 800" % path)
    import json
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f).get("meta", {})


if __name__ == "__main__":
    cli()
