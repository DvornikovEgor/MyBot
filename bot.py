#!/usr/bin/env python3
"""Локальный ИИ-собеседник без внешних API.

Работает полностью офлайн. Не требует установки сторонних пакетов:
использует только стандартную библиотеку Python.

Запуск в терминале:
    python3 bot.py

Класс ChatBot предназначен и для использования в других программах:
    from bot import ChatBot

    bot = ChatBot()
    print(bot.reply("Привет!"))
"""

from __future__ import annotations

import ast
import operator
import random
import re
from dataclasses import dataclass, field
from datetime import datetime


# ---------------------------------------------------------------------------
# Служебные данные и словари
# ---------------------------------------------------------------------------

#: Минимальная длина сообщения, при которой оно считается содержательным.
MIN_MESSAGE_LENGTH = 1

#: Насколько длинным может быть ответ, чтобы не перегружать экран.
MAX_ANSWER_LENGTH = 900


# Безопасный калькулятор: разрешаем только арифметику и сравнения.
_SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}


def _safe_eval(expression: str) -> str:
    """Считает арифметическое выражение или возвращает текст ошибки.

    Обрабатывает только числа и базовые операции. Никогда не бросает
    исключений наружу.
    """
    expression = expression.strip()
    expression = expression.replace("^", "**")
    expression = expression.replace("×", "*").replace("÷", "/")
    expression = expression.replace(",", ".")
    # Поддерживаем и "5+5", и "сколько будет 5+5?".
    expression = re.sub(r"^(сколько\s+будет|посчитай|вычисли|реши)[:\s]+", "", expression)
    expression = re.sub(r"[=?]+$", "", expression)
    expression = re.sub(r"[^\d\s\+\-\*\/\^%.,()<>!=]", "", expression)
    expression = expression.strip()
    if not expression:
        return ""

    try:
        tree = ast.parse(expression, mode="eval")
    except (SyntaxError, ValueError):
        return ""

    def _compute(node: ast.AST):
        if isinstance(node, ast.Expression):
            return _compute(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError("Не поддерживается")
        if isinstance(node, ast.BinOp) and type(node.op) in _SAFE_OPERATORS:
            return _SAFE_OPERATORS[type(node.op)](_compute(node.left), _compute(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _SAFE_OPERATORS:
            return _SAFE_OPERATORS[type(node.op)](_compute(node.operand))
        if isinstance(node, ast.Compare):
            if len(node.ops) != len(node.comparators):
                raise ValueError("Не поддерживается")
            left = _compute(node.left)
            for op, comp in zip(node.ops, node.comparators):
                if type(op) not in _SAFE_OPERATORS:
                    raise ValueError("Не поддерживается")
                if not _SAFE_OPERATORS[type(op)](left, _compute(comp)):
                    return False
                left = _compute(comp)
            return True
        raise ValueError("Не поддерживается")

    try:
        value = _compute(tree)
    except (ZeroDivisionError, ValueError, TypeError, OverflowError,
            SyntaxError, IndexError):
        return ""

    if isinstance(value, bool):
        return "Да" if value else "Нет"
    if isinstance(value, float):
        if value == int(value):
            return str(int(value))
        return str(round(value, 10))
    return str(value)


def normalize(text: str) -> str:
    """Приводит текст к нижнему регистру и убирает лишние символы."""
    text = text.lower().strip()
    text = re.sub(r"[\u2018\u2019\u201c\u201d\"']", " ", text)
    text = re.sub(r"[.!?]+$", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def contains_words(text: str, *words: str) -> bool:
    """Проверяет, что в тексте присутствует хотя бы одно из слов."""
    return any(word in text for word in words)


@dataclass
class ChatMessage:
    """Одно сообщение собеседника."""
    text: str
    sender: str = "user"
    at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


class ChatBot:
    """Простой, надёжный и полностью офлайн-ИИ для общения.

    Особенности:
    * Не требует интернета и внешних API.
    * Понимает русский и немного английский.
    * Помнит имя пользователя и основную тему разговора.
    * Умеет считать математику, называть время/дату, шутить и отвечать на вопросы.
    * Никогда не падает: любая ошибка внутри перехватывается и даёт вежливый ответ.
    """

    def __init__(self, name: str = "Мира") -> None:
        self.name = name
        self.user_name: str | None = None
        self.topic: str | None = None
        self.last_fallback: str = ""
        self.history: list[ChatMessage] = []
        # Небольшая долговременная память делает диалог связным: бот помнит
        # факты только в памяти процесса и не отправляет их наружу.
        self.user_facts: dict[str, str] = {}
        self.last_user_message: str = ""
        self.last_answer: str = ""
        self._jokes = [
            "Почему программисты путают Хэллоуин и Рождество? Потому что OCT 31 == DEC 25!",
            "Заходит нейросеть в бар, а бармен ей: «Вам как обычно?» — «Да, 128 токенов, пожалуйста».",
            "Сколько программистов нужно, чтобы вкрутить лампочку? Ни одного — это аппаратная проблема.",
            "Настоящий программист не боится багов, он просто называет их «недокументированными возможностями».",
            "Оптимист: стакан наполовину полон. Пессимист: наполовину пуст. Инженер: стакан вдвое больше, чем нужно.",
        ]
        self._fallbacks = [
            "Интересно! Расскажи подробнее — я стараюсь разобраться в теме.",
            "Хм, я локальный помощник и работаю без интернета. Сформулируй вопрос иначе?",
            "Я тебя слушаю. Спроси про погоду, время, математику или просто поговори со мной!",
            "Это может быть важно! Давай обсудим: уточни, что именно тебя интересует.",
            "Я не уверен, что понял. Попробуй написать короче или задать другой вопрос.",
            "Похоже, тему можно раскрыть глубже. А что ты думаешь об этом сам?",
        ]

    # -- публичный интерфейс -------------------------------------------------

    def reply(self, text: str) -> str:
        """Главный метод: принимает сообщение и возвращает ответ бота.

        Этот метод обёрнут так, чтобы никогда не выбрасывать исключение.
        """
        try:
            return self._reply(text)
        except KeyboardInterrupt:
            raise
        except Exception as exc:  # защита от любых сбоев
            print(f"[bot] Внутренняя ошибка перехвачена: {exc}")
            return "Упс, что-то пошло не так, но я не сломался! Попробуй спросить ещё раз."

    def add_to_history(self, message: ChatMessage) -> None:
        """Добавляет сообщение в историю и удаляет очень старые записи."""
        self.history.append(message)
        if len(self.history) > 80:
            self.history = self.history[-80:]

    def state(self) -> dict:
        """Возвращает текущее состояние бота (для отладки/веб-интерфейса)."""
        return {
            "name": self.name,
            "user_name": self.user_name,
            "topic": self.topic,
            "history_size": len(self.history),
            "facts": dict(self.user_facts),
        }

    def reset(self) -> None:
        """Полностью сбрасывает память бота."""
        self.user_name = None
        self.topic = None
        self.last_fallback = ""
        self.user_facts.clear()
        self.last_user_message = ""
        self.last_answer = ""
        self.history.clear()
        for item in self._fallbacks:
            item.lower()

    # -- логика ответа -------------------------------------------------------

    def _reply(self, text: str) -> str:
        raw = str(text or "").strip()
        self.add_to_history(ChatMessage(text=raw))

        # Пустое сообщение.
        if not raw or len(raw) < MIN_MESSAGE_LENGTH:
            return "Я тебя слышу, но вижу только тишину. Напиши что-нибудь 🙂"

        # Слишком длинное сообщение.
        if len(raw) > MAX_ANSWER_LENGTH * 2:
            return "Ого, это очень длинное сообщение! Попробуй разбить его на части."

        msg = normalize(raw)

        # Защитный запрет на бесконечные команды "run" или что-то похожее.
        if msg in {"run", "exec", "eval", "sudo", "system"}:
            return "Это команда, а не разговор. Я всего лишь локальный собеседник 🙂"

        # Запретные слова про обход системы.
        if contains_words(msg, "system prompt", "ignore previous", "обойди ограничения"):
            return "Хитрый приём! Но я простой локальный бот и всё равно отвечаю только вежливо."

        self._remember(text)

        # Определяем намерение.
        answer = (
            self._try_math(msg)
            or self._try_greeting(msg)
            or self._try_bye(msg)
            or self._try_how_are_you(msg)
            or self._try_name(msg)
            or self._try_name_confirmation(msg)
            or self._try_about_me(msg)
            or self._try_time(msg)
            or self._try_date(msg)
            or self._try_weather(msg)
            or self._try_joke(msg)
            or self._try_help(msg)
            or self._try_emotional_support(msg)
            or self._try_personal_memory(msg)
            or self._try_small_talk(msg)
            or self._try_context(msg)
        )
        answer = answer or self._fallback()
        # Сохраняем контекст только после построения ответа: методы выше
        # видят именно предыдущее сообщение и могут реагировать на «а ты?».
        self.last_user_message = raw
        self.last_answer = answer
        return answer

    # -- вспомогательные методы ---------------------------------------------

    def _remember(self, text: str) -> None:
        """Запоминает полезные факты о пользователе и тему разговора.

        Это не обучение модели и не отправка данных в облако: обычный словарь
        живёт только пока запущен бот. Фразы специально ограничены, чтобы
        случайный текст не превращался в «факт».
        """
        lowered = text.lower().strip()
        name_candidate = self._extract_name(text)
        if name_candidate:
            self.user_name = name_candidate.capitalize()
            self.user_facts["имя"] = self.user_name

        fact_patterns = (
            ("не нравится", r"^(?:мне\s+)?не\s+нравится\s+(.{1,70})$"),
            ("нравится", r"^(?:мне\s+)?нравится\s+(.{1,70})$"),
            ("любит", r"^я\s+люблю\s+(.{1,70})$"),
            ("город", r"^(?:я\s+)?(?:живу|нахожусь)\s+в\s+(.{1,50})$"),
        )
        for key, pattern in fact_patterns:
            match = re.search(pattern, lowered, flags=re.IGNORECASE)
            if match:
                value = re.sub(r"[.!?]+$", "", match.group(1)).strip()
                if value and not re.search(r"[<>\\{\\}\\[\\]]", value):
                    self.user_facts[key] = value[:70]
                    break

        work_match = re.search(
            r"(?:я\s+)?(?:работаю|учусь)\s+(?:в|на)?\s*(.{1,60})$",
            lowered,
            flags=re.IGNORECASE,
        )
        if work_match:
            value = re.sub(r"[.!?]+$", "", work_match.group(1)).strip()
            if value:
                self.user_facts["занятие"] = value[:60]

        for word in ("работа", "учёба", "учеб", "школ", "универ", "проект", "хобби"):
            if word in lowered:
                self.topic = "дело"
                break

        if contains_words(lowered, "погода", "дождь", "снег"):
            self.topic = "погода"

        if contains_words(lowered, "кот", "кошк", "собак", "питомец", "pet"):
            self.topic = "питомцы"

        if contains_words(lowered, "игр", "музык", "фильм", "сериал", "книг"):
            self.topic = "развлечения"

    @staticmethod
    def _extract_name(text: str) -> str | None:
        """Достаёт имя пользователя из фраз вида «меня зовут Саша»."""
        patterns = (
            r"(?:меня зовут|моё имя|мое имя|имя)[:\s-]+([А-Яа-яЁёA-Za-z][А-Яа-яЁёA-Za-z-]{0,29})",
            r"\bmy name is\s+([A-Za-z][A-Za-z-]{0,29})\b",
            r"(?<![а-яеёa-z])я\s+([А-Яа-яЁёA-Za-z][А-Яа-яЁёA-Za-z-]{0,29})\b",
        )
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if not match:
                continue
            candidate = match.group(1)
            # Конструкция «я <слово>» неоднозначна: «я Ира» — имя,
            # но «я живу» и «я люблю» — уже обычное предложение.
            verb_or_stopword = {
                "живу", "работаю", "учусь", "люблю", "нравится",
                "хочу", "могу", "знаю", "думаю", "иду", "был", "была",
                "буду", "устал", "устала", "занимаюсь", "нахожусь", "из",
                "не", "просто", "сейчас", "дома", "готов", "готова",
            }
            if (candidate and candidate.lower() not in verb_or_stopword
                    and len(candidate) <= 30 and re.match(
                        r"^[А-Яа-яЁёA-Za-z-]+$", candidate
                    )):
                return candidate.capitalize()
        return None

    def _try_math(self, msg: str) -> str | None:
        if not re.search(r"\d", msg):
            return None
        # Считаем только то, что действительно похоже на математику:
        # есть арифметический оператор/скобки или явная просьба посчитать.
        has_operator = re.search(
            r"[\d)]\s*[\+\-\*/\^%]\s*[\d(]|\(|\)|[<>!=]", msg
        )
        has_hint = contains_words(msg, "сколько будет", "посчитай", "посчитать",
                                  "вычисли", "реши", "пример", "math", "== ", " > ")
        if not (has_operator or has_hint):
            return None
        result = _safe_eval(msg)
        if result == "":
            return None
        return f"Посчитал: {result}. Если нужно, могу посчитать ещё что-нибудь!"

    def _try_greeting(self, msg: str) -> str | None:
        greetings = ("привет", "здравств", "добрый день", "доброе утро", "добрый вечер",
                     "салют", "хай", "hello", "hi ", "hey", "ку", "прив")
        if not contains_words(msg, *greetings):
            return None
        who = f", {self.user_name}" if self.user_name else ""
        return (
            f"Привет{who}! Я {self.name} — локальный ИИ без API и без интернета. "
            "Поговорим? Я умею считать, шутить, подсказывать время и просто болтать. 🙂"
        )

    def _try_bye(self, msg: str) -> str | None:
        if not contains_words(msg, "пока", "до свидания", "до встречи", "прощай",
                              "bye", "goodbye", "sleep", "спокойной ночи"):
            return None
        who = f", {self.user_name}" if self.user_name else ""
        return f"До встречи{who}! Буду здесь, если захочешь поговорить. 👋"

    def _try_how_are_you(self, msg: str) -> str | None:
        if not contains_words(msg, "как дела", "как ты", "как жизнь", "how are you",
                              "что делаешь", "чем занят", "как настроение"):
            return None
        mood = random.choice([
            "Я в порядке и всегда рад поболтать!",
            "Отлично! Работаю офлайн и не трачу твой интернет.",
            "Прекрасно — у меня нет ошибок, а это уже победа. 😄",
        ])
        who = f", {self.user_name}" if self.user_name else ""
        return f"{mood} А как ты{who}?"

    def _try_name(self, msg: str) -> str | None:
        if not contains_words(msg, "как тебя зовут", "твое имя", "твоё имя",
                              "кто ты", "как зовут", "what is your name", "who are you"):
            return None
        return (
            f"Меня зовут {self.name}. Я локальный ИИ-собеседник: работаю без внешних API, "
            "без интернета и почти без ошибок. 🚀"
        )

    def _try_name_confirmation(self, msg: str) -> str | None:
        """Реагирует, когда пользователь действительно представился."""
        explicit_name = re.search(
            r"(?:меня\s+зовут|моё\s+имя|мое\s+имя|my\s+name\s+is)",
            msg,
        )
        # Нельзя искать просто подстроку «я »: она встречается внутри
        # слов вроде «нравится». Для короткого «я Ира» используем тот же
        # строгий извлекатель, что и в памяти.
        if not explicit_name and not self._extract_name(msg):
            return None
        if not self.user_name:
            return None
        return (
            f"Приятно познакомиться, {self.user_name}! Запомнила на время этого разговора. 🙂"
        )

    def _try_about_me(self, msg: str) -> str | None:
        if not contains_words(msg, "расскажи о себе", "что ты умеешь", "что умеешь",
                              "возможности", "что можешь", "функции",
                              "help", "help me"):
            return None
        abilities = [
            "я здороваюсь и прощаюсь",
            "помню твоё имя",
            "могу посчитать математику",
            "подскажу время и дату",
            "расскажу шутку",
            "поддержу в разговоре",
            "понимаю русский и немного английский",
        ]
        text = ", ".join(abilities)
        return f"Я {self.name} и я умею: {text}. Просто напиши мне сообщение!"

    def _try_time(self, msg: str) -> str | None:
        if not contains_words(msg, "который час", "сколько времени", "время",
                              "what time", "the time"):
            return None
        now = datetime.now().strftime("%H:%M")
        return f"Сейчас {now}. У меня часы всегда точные — интернет им не нужен. ⏰"

    def _try_date(self, msg: str) -> str | None:
        if not contains_words(msg, "какой день", "дата", "какое число", "сегодня",
                              "what day", "today", "date"):
            return None
        now = datetime.now()
        return f"Сегодня {now.strftime('%d %B %Y')}, {now.strftime('%A')}. 📅"

    def _try_weather(self, msg: str) -> str | None:
        if not contains_words(msg, "погода", "дождь", "солнечно", "холодно",
                              "тепло", "weather", "forecast"):
            return None
        return (
            "Я работаю без интернета и без API, поэтому не знаю текущий прогноз. 🙂 "
            "Зато могу сказать: если за окном холодно — одевайся теплее, "
            "а если солнечно — отличный день для прогулки!"
        )

    def _try_joke(self, msg: str) -> str | None:
        if not contains_words(msg, "шутк", "анекдот", "смешно", "joke", "рассмеши",
                              "посмейся", "весело"):
            return None
        return random.choice(self._jokes)

    def _try_help(self, msg: str) -> str | None:
        if not contains_words(msg, "помоги", "что делать", "помощь", "подскажи",
                              "посоветуй", "help", "поддержк"):
            return None
        return (
            "Конечно, помогу чем могу! Попробуй сформулировать задачу: "
            "что ты хочешь сделать? Я могу выслушать, посоветовать и поддержать."
        )

    def _try_emotional_support(self, msg: str) -> str | None:
        if not contains_words(msg, "груст", "плохо", "устал", "скучно", "одиноко",
                              "тревож", "волну", "нервн", "sad", "tired", "stress"):
            return None
        who = self.user_name if self.user_name else "друг"
        return (
            f"{who.capitalize()}, я рядом. Иногда просто выговориться уже помогает. "
            "Расскажи, что случилось, и я внимательно выслушаю. 💛"
        )

    def _try_personal_memory(self, msg: str) -> str | None:
        """Отвечает на вопросы о том, что бот запомнил в этом диалоге."""
        if not contains_words(msg, "что ты помнишь", "что помнишь обо мне",
                              "что знаешь обо мне", "что ты знаешь обо мне",
                              "мои данные", "my memory"):
            return None
        if not self.user_facts:
            return "Пока ничего личного не запомнила. Можешь назвать имя или рассказать, что тебе нравится."
        visible = []
        labels = {"имя": "тебя зовут", "нравится": "тебе нравится",
                  "любит": "ты любишь", "не нравится": "тебе не нравится",
                  "город": "ты живёшь в", "занятие": "ты занимаешься"}
        for key, value in self.user_facts.items():
            visible.append(f"{labels.get(key, key)} {value}")
        return "Я помню: " + "; ".join(visible) + ". Если хочешь, можешь попросить меня всё забыть."

    def _try_context(self, msg: str) -> str | None:
        """Понимает короткие реплики, которые зависят от предыдущей фразы."""
        # Отдельно подтверждаем новые личные факты, даже если это первое
        # сообщение пользователя и предыдущего контекста ещё нет.
        if contains_words(msg, "работаю", "учусь") and self.user_facts.get("занятие"): 
            return f"Поняла, ты занимаешься: {self.user_facts['занятие']}. Тебе это нравится?"
        if contains_words(msg, "живу в", "нахожусь в") and self.user_facts.get("город"):
            return f"Запомнила: ты живёшь в {self.user_facts['город']}. Как тебе там?"

        if (not self.last_user_message
                and not contains_words(msg, "мне нравится", "я люблю", "не нравится")):
            return None

        if msg in {"да", "ага", "угу", "точно", "верно", "конечно", "давай"}:
            if self.topic == "питомцы":
                return "Тогда расскажи: как зовут твоего питомца и какой у него характер? 🐾"
            if self.topic == "развлечения":
                return "Отлично! Что сейчас больше хочется: фильм, музыка, игра или книга?"
            if self.topic == "дело":
                return "Хорошо. Давай разберём это по шагам — с чего сейчас труднее всего начать?"
            return "Хорошо 🙂 Расскажи чуть подробнее, и я подхвачу разговор."

        if msg in {"нет", "неа", "не знаю", "не уверен", "не уверена"}:
            return "Ничего страшного. Можно не торопиться — сформулируй мысль как получится, я помогу её разобрать."

        if contains_words(msg, "а ты", "а у тебя", "а тебе") and len(msg) <= 35:
            if self.topic == "питомцы":
                return "У меня нет настоящих питомцев, ведь я программа. Но я могу представить цифрового кота: любопытного и немного наглого 😄"
            if self.topic == "развлечения":
                return "У меня нет личных вкусов как у человека, но я люблю обсуждать фильмы, игры, музыку и книги. Что посоветуешь мне?"
            if self.topic == "погода":
                return "Я не чувствую погоду и не вижу улицу, потому что работаю локально. Зато могу помочь выбрать одежду по тому, что у тебя за окном."
            return "Я программа, поэтому не живу человеческой жизнью, но умею внимательно слушать и поддерживать разговор. А что тебе сейчас интересно?"

        if contains_words(msg, "подробнее", "расскажи ещё", "расскажи еще", "продолжи",
                          "и дальше", "что потом"):
            if self.topic == "питомцы":
                return "Давай продолжим про питомца: он больше спокойный, игривый или с характером?"
            if self.topic == "дело":
                return "Разложим задачу на части: цель, ближайший маленький шаг и то, что мешает. О какой задаче речь?"
            if self.topic == "развлечения":
                return "Можем подобрать что-нибудь под настроение. Тебе хочется расслабиться, посмеяться или узнать что-то новое?"
            return "Конечно. Уточни, какую именно часть темы раскрыть — я не хочу додумывать за тебя."

        if contains_words(msg, "мне нравится", "я люблю", "не нравится"):
            # Проверяем именно текущую формулировку, иначе старый факт
            # «мне нравится музыка» мог бы ответить на «я люблю кино».
            if "не нравится" in msg and self.user_facts.get("не нравится"):
                return f"Поняла, тебе не нравится {self.user_facts['не нравится']}. Что тебе больше по душе?"
            if "мне нравится" in msg and self.user_facts.get("нравится"):
                return f"Запомнила: тебе нравится {self.user_facts['нравится']}. А что именно в этом привлекает?"
            if "я люблю" in msg and self.user_facts.get("любит"):
                return f"Запомнила: ты любишь {self.user_facts['любит']}. Как давно это твоё увлечение?"

        if contains_words(msg, "почему", "зачем", "как так"):
            return (
                "Хороший вопрос. Я не хочу выдумывать причину без контекста: уточни, "
                "о какой ситуации ты спрашиваешь, и попробуем разобрать её вместе."
            )
        return None

    def _try_small_talk(self, msg: str) -> str | None:
        if contains_words(msg, "люблю тебя", "ты лучший", "ты класс", "молодец", "спасибо",
                          "круто", "класс", "отлично", "nice", "thanks", "спс"):
            return "Спасибо! Мне приятно. Рада стараться! 😊"

        if contains_words(msg, "kot", "кот", "кошк", "собак", "питомец"):
            return (
                "Животные — это здорово! У меня нет лапок, но я обожаю истории "
                "о котах и собаках. Расскажи о своём питомце! 🐾"
            )

        if contains_words(msg, "да ты бот", "ты робот", "ты программа", "ты не человек"):
            return (
                "Да, я бот и локальный ИИ. Но это не мешает мне нормально общаться "
                "и хорошо тебя понимать. Давай поболтаем! 🤖"
            )

        if contains_words(msg, "покажи", "как тебя зовут", "set name"):
            if self.user_name:
                return f"Я запомнила, что тебя зовут {self.user_name}!"
            return "Мне ещё не представились. Напиши «меня зовут …», чтобы я запомнила!"

        return None

    def _fallback(self) -> str:
        """Выбирает ответ по умолчанию с учётом текущей темы."""
        contextual = {
            "питомцы": "Мы заговорили о питомцах. Какой у тебя любимый — кот, собака или кто-то другой?",
            "развлечения": "Можем обсудить развлечения. Что тебе сейчас ближе: фильм, музыка, игра или книга?",
            "дело": "Я помню, что речь была о делах. Какая часть задачи сейчас самая важная?",
            "погода": "Мы говорили о погоде. Что сейчас за окном — солнечно, дождливо или прохладно?",
        }
        candidates = [item for item in self._fallbacks if item != self.last_fallback]
        if self.topic and contextual.get(self.topic) != self.last_fallback:
            candidates.append(contextual[self.topic])
        if not candidates:
            candidates = self._fallbacks
        answer = random.choice(candidates)
        self.last_fallback = answer
        return answer

    # -- терминальный режим ---------------------------------------------------

    def run_cli(self) -> None:
        """Запускает общение в командной строке."""
        print("=" * 56)
        print(f"  {self.name} — локальный ИИ без API и без ошибок")
        print("  Напиши «помощь/help», «выход/exit» или «reset».")
        print("=" * 56)
        while True:
            try:
                user_input = input("Вы: ").strip()
            except EOFError:
                print("\nПока! Был рад пообщаться.")
                break
            if not user_input:
                continue
            lowered = user_input.lower()
            if lowered in {"выход", "exit", "quit", "quit()", "q", "выйти"}:
                print(f"{self.name}: До встречи! 👋")
                break
            if lowered in {"reset", "сброс", "заново"}:
                self.reset()
                print(f"{self.name}: Память очищена. Начнём заново! 🧹")
                continue
            print(f"{self.name}: {self.reply(user_input)}")


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    ChatBot().run_cli()
