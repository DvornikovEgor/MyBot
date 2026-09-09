"""Тесты бота: запускаются стандартным модулем unittest, без зависимостей.

Проверка:  python3 -m unittest discover tests -v
"""

import string
import random
import tempfile
import unittest

from bot import Brain
from bot import skills
from bot.markov import MarkovChain


def make_brain(tmp):
    return Brain(storage_dir=tmp)


class TestCalculator(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(skills.try_calculate("сколько будет 2+2?"), "4")

    def test_precedence(self):
        self.assertEqual(skills.try_calculate("2+2*2"), "6")

    def test_power(self):
        self.assertEqual(skills.try_calculate("2^10 равно?"), "1024")

    def test_decimal_comma(self):
        self.assertEqual(skills.try_calculate("посчитай 2,5*4"), "10")

    def test_division_by_zero(self):
        self.assertIn("нельзя", skills.try_calculate("5/0"))

    def test_no_math(self):
        self.assertIsNone(skills.try_calculate("у меня пять яблок"))

    def test_huge_power_is_rejected(self):
        self.assertIsNone(skills.try_calculate("9**999999999999"))

    def test_injection_is_impossible(self):
        self.assertIsNone(skills.try_calculate("__import__('os').system('ls')"))
        self.assertIsNone(skills.try_calculate("1 + open('/etc/passwd')"))

    def test_leading_parenthesis(self):
        self.assertEqual(skills.try_calculate("сколько будет (2+3)*4?"), "20")
        self.assertEqual(skills.try_calculate("((2+2)*3) равно"), "12")


class TestKnowledgeBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.brain = make_brain(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_starter_knowledge_loaded(self):
        self.assertGreaterEqual(len(self.brain.knowledge), 10)

    def test_exact_lookup(self):
        answer = self.brain.lookup("кто написал Евгений Онегин?")
        self.assertIn("Пушкин", answer)

    def test_fuzzy_lookup(self):
        answer = self.brain.lookup("Столица франции???")
        self.assertIn("Париж", answer)

    def test_learn_and_persist(self):
        self.brain.learn("Столица Японии", "Токио")
        self.assertIn("Токио", self.brain.lookup("столица Японии"))
        # Новая копия бота видит те же знания.
        brain2 = make_brain(self._tmp.name)
        self.assertIn("Токио", brain2.lookup("столица Японии"))

    def test_learn_updates_existing(self):
        self.brain.learn("Столица Франции", "Марсель (шутка)")
        self.assertIn("Марсель", self.brain.lookup("столица франции"))

    def test_forget(self):
        self.brain.learn("Временный факт", "Временный ответ")
        result = self.brain.forget("временный факт")
        self.assertIn("Забыл", result)
        self.assertIsNone(self.brain.lookup("временный факт"))

    def test_reply_contains_answer(self):
        answer = self.brain.reply("Сколько цветов в радуге?")
        self.assertIn("Семь", answer)


class TestDialogue(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.brain = make_brain(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_greeting(self):
        answer = self.brain.reply("привет!")
        self.assertTrue(answer)

    def test_time_skill(self):
        answer = self.brain.reply("который час?")
        self.assertIn("Время", answer)

    def test_math_via_reply(self):
        answer = self.brain.reply("сколько будет 7*8?")
        self.assertIn("56", answer)

    def test_math_with_parens_via_reply(self):
        answer = self.brain.reply("сколько будет (2+3)*4?")
        self.assertIn("20", answer)

    def test_coin_inflected_form(self):
        answer = self.brain.reply("подбрось монетку")
        self.assertTrue("Орёл" in answer or "Решка" in answer)

    def test_dice_inflected_form(self):
        answer = self.brain.reply("брось кубик")
        self.assertIn("выпало", answer)

    def test_joke_inflected_form(self):
        answer = self.brain.reply("расскажи шутку")
        self.assertNotIn("не знаю", answer)

    def test_pending_does_not_swallow_new_question(self):
        self.brain.reply("Что такое глюон?")          # бот не знает → ждёт ответ
        second = self.brain.reply("А что такое бозон?")  # новый вопрос, не ответ!
        self.assertNotIn("Запомнил", second)
        learned = self.brain.reply("Частица-переносчик взаимодействия.")
        self.assertIn("бозон", learned)
        self.assertIn("Частица-переносчик", self.brain.reply("что такое бозон?"))

    def test_remember_name(self):
        self.brain.reply("Привет! Меня зовут Маша")
        self.assertEqual(self.brain.profile["name"], "Маша")
        brain2 = make_brain(self._tmp.name)
        self.assertEqual(brain2.profile["name"], "Маша")

    def test_teaching_flow(self):
        first = self.brain.reply("Что такое кварк?")
        self.assertIn("не знаю", first)
        learned = self.brain.reply("Это элементарная частица.")
        self.assertIn("Запомнил", learned)
        self.assertIn("элементарная частица", self.brain.reply("что такое кварк?"))

    def test_skip_teaching(self):
        self.brain.reply("Что такое изотоп?")
        answer = self.brain.reply("пропустить")
        self.assertIn("проехали", answer)

    def test_commands(self):
        self.assertIn("Команды", self.brain.reply("/помощь"))
        self.assertIn("Запомнил", self.brain.reply("/учить любимый цвет | синий"))
        self.assertIn("синий", self.brain.reply("какой мой любимый цвет?") or "")
        self.assertIn("записей", self.brain.reply("/база"))
        self.assertIn("Не знаю такой команды", self.brain.reply("/телепорт"))

    def test_story(self):
        story = self.brain.tell_story()
        self.assertIsInstance(story, str)
        self.assertTrue(story[-1] in ".!?…")

    def test_empty_input(self):
        self.assertTrue(self.brain.reply(""))
        self.assertTrue(self.brain.reply("   "))


class TestMarkov(unittest.TestCase):
    def test_empty_chain(self):
        chain = MarkovChain()
        self.assertIsNone(chain.generate())

    def test_generate(self):
        chain = MarkovChain()
        chain.train("Кот спит на окне. Кот видит сон. Окно открыто.")
        text = chain.generate()
        self.assertIsInstance(text, str)
        self.assertTrue(text[-1] in ".!?…")


class TestRobustness(unittest.TestCase):
    """Бот обязан отвечать на любой мусор и никогда не падать."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.brain = make_brain(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_fuzz_inputs(self):
        rng = random.Random(42)
        alphabet = string.printable + "абвгдеёжзиклмнопрстуфхцчшщъыьэюя😀🤖"
        samples = ["", " ", "\n", "/".join(["/"] * 50), "слово " * 500,
                   "«»«»«»", "𝕡𝕣𝕚𝕧𝕖𝕥", "-1", "0/0", "9**9**9",
                   "привет\0мир", "\\", "%s %s" % ("x", "y")]
        for _ in range(300):
            samples.append("".join(rng.choice(alphabet) for _ in range(rng.randint(0, 80))))
        for sample in samples:
            answer = self.brain.reply(sample)
            self.assertIsInstance(answer, str)
            self.assertTrue(len(answer) > 0)
            self.brain._pending_question = None  # сбрасываем режим обучения


if __name__ == "__main__":
    unittest.main(verbosity=2)
