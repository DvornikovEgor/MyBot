#!/usr/bin/env python3
"""Набор тестов, доказывающих, что бот отвечает без ошибок.

Запуск:
    python3 test_bot.py
"""

import unittest

from bot import ChatBot, _safe_eval, normalize


class TestMath(unittest.TestCase):
    def test_safe_eval(self):
        self.assertEqual(_safe_eval("2+2"), "4")
        self.assertEqual(_safe_eval("5*8-3"), "37")
        self.assertEqual(_safe_eval("(2+3)*4"), "20")
        self.assertEqual(_safe_eval("10/4"), "2.5")
        self.assertEqual(_safe_eval("7 == 7"), "Да")

    def test_unsafe_returns_empty(self):
        # Побочный код не должен исполняться.
        self.assertEqual(_safe_eval("__import__('os')"), "")
        self.assertEqual(_safe_eval(""), "")


class TestNoErrors(unittest.TestCase):
    def setUp(self):
        self.bot = ChatBot()

    def test_empty_and_weird_inputs_never_crash(self):
        weird_inputs = [
            "",
            "   ",
            "😀😀😀",
            "exec",
            "open('x').read()",
            "а" * 5000,
            "\n\t" * 100,
            "м" * 2000,
        ]
        for text in weird_inputs:
            with self.subTest(text=text[:20]):
                reply = self.bot.reply(text)
                self.assertIsInstance(reply, str)
                self.assertTrue(reply.strip() != "")

    def test_math_not_triggered_by_dates_or_counts(self):
        for text in ["у меня 2 кота", "приду в 5 часов", "мне 10 лет"]:
            with self.subTest(text=text):
                reply = self.bot.reply(text)
                self.assertFalse(reply.startswith("Посчитал:"),
                                 f"{text!r} не должно считаться как математика: {reply!r}")

    def test_reply_chain_keeps_working(self):
        for text in [
            "Привет",
            "как дела?",
            "меня зовут Ира",
            "сколько будет 123*456?",
            "который час?",
            "расскажи анекдот",
            "что ты умеешь?",
            "мне скучно",
            "пока",
        ]:
            reply = self.bot.reply(text)
            self.assertIsInstance(reply, str)
            self.assertTrue(reply.strip())

    def test_memory_none_object(self):
        self.bot.reply("меня зовут Маша")
        self.assertEqual(self.bot.user_name, "Маша")
        self.bot.reset()
        self.assertIsNone(self.bot.user_name)

    def test_normalize(self):
        self.assertEqual(normalize("  Привет!?  "), "привет")

    def test_context_and_personal_memory(self):
        self.bot.reply("меня зовут Ира")
        self.bot.reply("я живу в Майкопе")
        self.bot.reply("мне нравится музыка")
        memory = self.bot.reply("что ты помнишь обо мне?")
        self.assertIn("Ира", memory)
        self.assertIn("майкопе", memory)
        self.assertIn("музыка", memory)
        self.assertIn("facts", self.bot.state())

        reply = self.bot.reply("а ты?")
        self.assertTrue(any(word in reply.lower() for word in ("программа", "личных вкусов", "обсуждать")))

    def test_name_extractor_does_not_confuse_verbs_with_names(self):
        self.bot.reply("я живу в Майкопе")
        self.bot.reply("я работаю инженером")
        self.assertIsNone(self.bot.user_name)
        self.assertEqual(self.bot.state()["facts"]["город"], "майкопе")


if __name__ == "__main__":
    unittest.main(verbosity=2)
