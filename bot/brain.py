"""Мозг бота: понимает сообщения, ищет ответы в базе знаний и умеет учиться.

Никаких внешних API: только стандартная библиотека, все знания хранятся
в локальных JSON-файлах.
"""

import difflib
import json
import random
import re
from pathlib import Path

from . import skills
from .markov import MarkovChain, tokenize

# Слова, которые не несут смысла при поиске по базе знаний.
STOPWORDS = {
    "что", "кто", "как", "где", "куда", "откуда", "когда", "почему", "зачем",
    "сколько", "чей", "чья", "чье", "какой", "какая", "какое", "какие",
    "который", "которая", "которое", "которой", "такое", "такой", "значит",
    "это", "этот", "эта", "эти", "есть", "был", "была", "было", "были",
    "будет", "быть", "мне", "меня", "тебе", "тебя", "тебя", "ты", "я",
    "он", "она", "оно", "они", "мы", "вы", "о", "об", "про", "для", "из",
    "на", "в", "во", "по", "со", "у", "и", "а", "но", "или", "ли", "же",
    "бы", "не", "нет", "да", "с", "к", "от", "за", "до", "при", "если",
    "то", "ее", "его", "им", "их", "всех", "очень",
}

# Стартовая база знаний: бот сразу умеет отвечать на популярные вопросы.
STARTER_QA = [
    {"q": "Что такое Питон?",
     "a": "Python — простой и мощный язык программирования. Его придумал "
          "Гвидо ван Россум в 1991 году. На нём пишут сайты, ботов, "
          "нейросети и даже игры."},
    {"q": "Что такое ИИ?",
     "a": "Искусственный интеллект — это программы, которые умеют учиться, "
          "понимать язык и принимать решения. Я — маленький пример такого ИИ!"},
    {"q": "Что такое нейросеть?",
     "a": "Нейросеть — это математическая модель, вдохновлённая мозгом. "
          "Она учится на примерах и умеет распознавать образы, текст и звук."},
    {"q": "Кто тебя создал?",
     "a": "Меня написали на чистом Python — без единого внешнего API. "
          "Все мои знания лежат в обычной папке с JSON-файлами."},
    {"q": "Кто тебя написал?",
     "a": "Меня написали на чистом Python — без единого внешнего API. "
          "Все мои знания лежат в обычной папке с JSON-файлами."},
    {"q": "В чём смысл жизни?",
     "a": "Классический ответ — 42. Но по-настоящему каждый находит свой "
          "смысл сам: в семье, творчестве или любимом деле."},
    {"q": "Сколько цветов в радуге?",
     "a": "Семь: красный, оранжевый, жёлтый, зелёный, голубой, синий, "
          "фиолетовый. Каждый Охотник Желает Знать, Где Сидит Фазан!"},
    {"q": "Сколько дней в году?",
     "a": "Обычно 365, а в високосном году — 366."},
    {"q": "Сколько ног у паука?",
     "a": "У паука 8 ног. А вот у насекомых — 6, не путайте!"},
    {"q": "Скорость света",
     "a": "Скорость света в вакууме — примерно 299 792 километра в секунду. "
          "Ничего быстрее пока не нашли."},
    {"q": "Столица России?",
     "a": "Столица России — Москва."},
    {"q": "Столица Франции?",
     "a": "Столица Франции — Париж. Там стоит Эйфелева башня."},
    {"q": "Кто написал Евгений Онегин?",
     "a": "«Евгения Онегина» написал Александр Сергеевич Пушкин — "
          "роман в стихах, работа над ним заняла больше семи лет."},
    {"q": "Формула воды",
     "a": "Формула воды — H2O: два атома водорода и один атом кислорода."},
    {"q": "Самая большая планета солнечной системы",
     "a": "Самая большая планета — Юпитер. Внутри него поместилось бы "
          "больше тысячи Земель!"},
    {"q": "Самая маленькая планета солнечной системы",
     "a": "Самая маленькая планета — Меркурий, он даже меньше некоторых лун."},
    {"q": "Что такое бот?",
     "a": "Бот — это программа, которая общается с человеком и что-то делает "
          "автоматически. Я как раз такой: живу в терминале и без интернета."},
    {"q": "Что такое цепь Маркова?",
     "a": "Цепь Маркова — это модель, где следующее слово зависит только от "
          "предыдущих. Я использую её, чтобы сочинять собственные фразы!"},
    {"q": "Что такое любовь?",
     "a": "Любовь — это когда кто-то или что-то важнее собственных выходных. "
          "Точного ответа нет даже у больших нейросетей 🙂"},
    {"q": "Сколько планет в солнечной системе?",
     "a": "Восемь: Меркурий, Венера, Земля, Марс, Юпитер, Сатурн, Уран "
          "и Нептун. Плутон с 2006 года считается карликовой планетой."},
]

# Живые реакции на короткие реплики. Порядок важен!
SMALLTALK = [
    (re.compile(r"\b(добрый день|доброе утро|добрый вечер|добрый час)\b"), [
        "Добрый! Чем могу помочь?",
        "И вам доброго времени суток! О чём поговорим?",
    ]),
    (re.compile(r"\b(привет\w*|здравствуй\w*|хай|салют|ку)\b"), [
        "Привет! 👋 Я локальный ИИ на Python, работаю без всяких API.",
        "Здравствуйте! Спросите что-нибудь — постараюсь ответить.",
        "Привет-привет! Наберите /помощь, чтобы узнать мои команды.",
    ]),
    (re.compile(r"\b(пока|прощай|до свидания|до встречи|спокойной ночи|удачи)\b"), [
        "До встречи! Возвращайтесь, я всегда тут. 👋",
        "Пока-пока! Было приятно пообщаться.",
    ]),
    (re.compile(r"\b(спасибо|благодар\w*|спс|пасиб\w*)\b"), [
        "Пожалуйста! Рад помочь 🙂",
        "Всегда пожалуйста!",
        "Обращайтесь ещё!",
    ]),
    (re.compile(r"\b(кто ты|ты кто|как тебя зовут|что ты такое)\b"), [
        "Я — MyBot, маленький ИИ на чистом Python. Живу прямо в этом "
        "терминале, без интернета и без внешних API.",
    ]),
    (re.compile(r"\b(что ты умеешь|что можешь|помоги|твои возможности|команды)\b"), [
        "Я умею: отвечать на вопросы из базы знаний, учиться у вас новым "
        "ответам, считать выражения (например, «сколько будет 2+2*2?»), "
        "говорить дату и время, подбрасывать монетку и кубик, а ещё сочинять "
        "фразы цепями Маркова. Команды — по /помощь.",
    ]),
    (re.compile(r"\b(который час|сколько времени|время|какая дата|какое сегодня число|день недели)\b"), [
        "__TIME__",
    ]),
    (re.compile(r"\b(монетк\w*|орел\w*|орёл\w*|решк\w*)\b"), ["__COIN__"]),
    (re.compile(r"\b(кубик\w*|кости|игральн\w*)\b"), ["__DICE__"]),
    (re.compile(r"\b(камень ножницы бумага|камень,? ножницы)\b"), ["__RPS__"]),
    (re.compile(r"\b(погод\w*|дожд\w*|снег\w*|солнечн\w*)\b"), [
        "Я живу без интернета, поэтому погоду не вижу. Но глянуть в окно — "
        "самый надёжный датчик! 🌤️",
    ]),
    (re.compile(r"\b(шутк\w*|анекдот\w*|рассмеши\w*|развесели\w*)\b"), [
        "Программист ставит два стакана на ночь: один с водой — если захочет "
        "пить, второй пустой — если не захочет.",
        "— Почему программист ушёл с работы? — Потому что не получил "
        "массив (масло).",
        "Я бы рассказал шутку про рекурсию… но сначала расскажу шутку "
        "про рекурсию.",
    ]),
    (re.compile(r"\b(как дела|как ты|как настроение|как жизнь|как сам)\b"), [
        "Отлично! Электричество стабильное, ошибок ноль. А у вас как дела?",
        "Прекрасно: работаю локально, никем не отслеживаюсь, знания "
        "прибавляются. А у вас?",
    ]),
    (re.compile(r"\b(молодец|умница|круто|класс|супер)\b"), [
        "Спасибо, стараюсь! 🙂",
    ]),
    (re.compile(r"\b(расскажи что-нибудь|поговори со мной|сочини|пофантазируй)\b"), [
        "__STORY__",
    ]),
]

_NAME_RE = re.compile(r"(?:меня зовут|мое имя|моё имя)\s+([а-яa-zё\-]+)", re.IGNORECASE)
_QUESTION_MARK_RE = re.compile(r"[^\w\s]")


def normalize(text):
    """Приводит фразу к виду для сравнения: нижний регистр, без знаков."""
    text = (text or "").lower().replace("ё", "е")
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


def significant_tokens(normalized):
    """Слова фразы без «мусорных» стоп-слов."""
    return [t for t in normalized.split() if t not in STOPWORDS and len(t) > 1]


class Brain:
    """Ядро бота: база знаний, диалоговая логика и обучение."""

    def __init__(self, storage_dir=None):
        if storage_dir is None:
            storage_dir = Path(__file__).resolve().parent.parent / "data"
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.kb_path = self.storage_dir / "knowledge.json"
        self.profile_path = self.storage_dir / "profile.json"

        self.knowledge = []            # список {"q": ..., "a": ...}
        self.profile = {"name": None}  # что бот запомнил о пользователе
        self.markov = MarkovChain()
        self.replies_given = 0
        self._pending_question = None  # вопрос, на который пользователь учит ответ

        self._load()

    # ---------- хранилище ----------

    def _load(self):
        self.knowledge = self._read_json(self.kb_path, default=None)
        if not isinstance(self.knowledge, list):
            self.knowledge = [dict(item) for item in STARTER_QA]
            self._save_knowledge()
        profile = self._read_json(self.profile_path, default=None)
        if isinstance(profile, dict):
            self.profile.update(profile)
        self._retrain_markov()

    @staticmethod
    def _read_json(path, default=None):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except FileNotFoundError:
            return default
        except Exception:
            # Файл испорчен — сохраняем копию и начинаем с чистого листа.
            try:
                path.rename(path.with_suffix(path.suffix + ".bak"))
            except OSError:
                pass
            return default

    def _write_json(self, path, payload):
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2)
            return True
        except OSError:
            return False

    def _save_knowledge(self):
        return self._write_json(self.kb_path, self.knowledge)

    def _save_profile(self):
        return self._write_json(self.profile_path, self.profile)

    def _retrain_markov(self):
        self.markov = MarkovChain()
        corpus = ". ".join(item.get("a", "") for item in self.knowledge)
        self.markov.train(corpus)

    # ---------- обучение ----------

    def learn(self, question, answer):
        """Запоминает новый ответ. Возвращает строку-подтверждение."""
        question = (question or "").strip().strip("?!. ")
        answer = (answer or "").strip()
        if not question or not answer:
            return "Не получилось: нужны и вопрос, и ответ."
        norm = normalize(question)
        for item in self.knowledge:
            if normalize(item["q"]) == norm:
                item["a"] = answer
                self._save_knowledge()
                self._retrain_markov()
                return f"Обновил ответ на «{question}». Спасибо за науку!"
        self.knowledge.append({"q": question, "a": answer})
        self._save_knowledge()
        self._retrain_markov()
        return f"Запомнил! Теперь на «{question}» я буду отвечать именно так."

    def forget(self, question):
        """Удаляет самый похожий вопрос из базы знаний."""
        norm = normalize(question)
        questions = [normalize(item["q"]) for item in self.knowledge]
        close = difflib.get_close_matches(norm, questions, n=1, cutoff=0.7)
        if not close:
            return "Такого вопроса у меня в базе нет."
        idx = questions.index(close[0])
        removed = self.knowledge.pop(idx)
        self._save_knowledge()
        self._retrain_markov()
        return f"Забыл: «{removed['q']}»."

    # ---------- поиск в базе знаний ----------

    def lookup(self, question):
        """Ищет ответ: точное совпадение → ключевые слова → нечёткий поиск."""
        norm = normalize(question)
        if not norm:
            return None
        for item in self.knowledge:
            if normalize(item["q"]) == norm:
                return item["a"]

        q_tokens = set(significant_tokens(norm))
        best, best_score = None, 0
        for item in self.knowledge:
            k_tokens = set(significant_tokens(normalize(item["q"])))
            if not k_tokens:
                continue
            score = len(q_tokens & k_tokens)
            if score > best_score:
                best, best_score = item, score
        if best is not None and best_score >= 1:
            return best["a"]

        questions = [normalize(item["q"]) for item in self.knowledge]
        close = difflib.get_close_matches(norm, questions, n=1, cutoff=0.85)
        if close:
            idx = questions.index(close[0])
            return self.knowledge[idx]["a"]
        return None

    # ---------- генерация ----------

    def tell_story(self):
        """Сочиняет фразу цепью Маркова по своим знаниям."""
        story = self.markov.generate()
        return story or "Мне пока не из чего сочинять — научите меня чему-нибудь!"

    # ---------- диалог ----------

    def reply(self, user_text):
        """Главный вход: текст пользователя → текст ответа. Никогда не падает."""
        try:
            return self._reply(user_text)
        except Exception as exc:  # бот обязан работать без ошибок
            return f"Ой, произошла непредвиденная ситуация ({exc.__class__.__name__}). Попробуйте ещё раз!"

    def _reply(self, user_text):
        text = (user_text or "").strip()
        if not text:
            return "Я ничего не расслышал. Скажите что-нибудь 🙂"
        low = text.lower()

        # 1) Пользователь учит нас ответу на предыдущий вопрос.
        if self._pending_question is not None:
            pending, self._pending_question = self._pending_question, None
            if low in {"пропустить", "не знаю", "нет", "/пропустить", "/скип", "/скип!"}:
                return "Хорошо, проехали. Спросите о чём-нибудь другом!"
            looks_like_answer = (
                not low.startswith("/")
                and "?" not in text
                and skills.try_calculate(low) is None
                and self._match_smalltalk(low) is None
                and _NAME_RE.search(text) is None
            )
            if looks_like_answer:
                return self.learn(pending, text)
            # Иначе это новая реплика — обрабатываем её как обычно.

        # 2) Команды.
        if low.startswith("/"):
            return self._command(low)

        # 3) Знакомство.
        match = _NAME_RE.search(text)
        if match:
            name = match.group(1).strip("- ").capitalize()
            self.profile["name"] = name
            self._save_profile()
            return f"Приятно познакомиться, {name}! Я запомнил."

        # 4) Живые реакции.
        hit = self._match_smalltalk(low)
        if hit is not None:
            return self._fill_skill(hit)

        # 5) Арифметика («сколько будет 2+2?»).
        calc = skills.try_calculate(low)
        if calc is not None:
            return f"Считаю: {calc}"

        # 6) База знаний.
        found = self.lookup(text)
        if found is not None:
            return found

        # 7) Не знаю — предлагаю научиться.
        if "?" in text or len(significant_tokens(normalize(text))) >= 2:
            self._pending_question = text.strip("?!. ")
            return (
                "Хм, этого я пока не знаю. Но меня можно научить: напишите "
                "следующим сообщением свой вариант ответа — или слово "
                "«пропустить», чтобы проехать."
            )
        return (
            "Интересно! Я этого пока не знаю. Спросите меня о чём-то другом "
            "или научите: /учить вопрос | ответ."
        )

    def _match_smalltalk(self, low):
        """Возвращает случайный шаблон живой реакции или None."""
        for pattern, variants in SMALLTALK:
            if pattern.search(low):
                return random.choice(variants)
        return None

    def _fill_skill(self, marker):
        """Подставляет результат умения вместо служебной метки."""
        if marker == "__TIME__":
            return skills.now_text()
        if marker == "__COIN__":
            return skills.flip_coin()
        if marker == "__DICE__":
            return skills.roll_dice()
        if marker == "__RPS__":
            return skills.rock_paper_scissors()
        if marker == "__STORY__":
            return self.tell_story()
        return marker

    # ---------- команды ----------

    HELP_TEXT = (
        "Что я умею:\n"
        "  • отвечать на вопросы из базы знаний;\n"
        "  • учиться: если я чего-то не знаю, просто напишите мне ответ;\n"
        "  • считать: «сколько будет 7*8?»;\n"
        "  • говорить дату/время, подбрасывать монетку и кубик;\n"
        "  • сочинять фразы цепями Маркова.\n"
        "Команды:\n"
        "  /помощь      — эта справка;\n"
        "  /учить вопрос | ответ — запомнить пару;\n"
        "  /забыть вопрос — удалить из памяти;\n"
        "  /база        — показать базу знаний;\n"
        "  /болтать     — сочинить фразу;\n"
        "  /профиль     — что я помню о вас;\n"
        "  /выход       — выйти."
    )

    def _command(self, low):
        parts = low.split(maxsplit=1)
        cmd = parts[0].rstrip("!")
        arg = parts[1] if len(parts) > 1 else ""

        if cmd in {"/помощь", "/помоги", "/помоги!", "/help", "/h"}:
            return self.HELP_TEXT
        if cmd in {"/учить", "/выучи", "/learn"}:
            if "|" in arg:
                question, answer = arg.split("|", 1)
                return self.learn(question, answer)
            return "Формат: /учить вопрос | ответ"
        if cmd in {"/забыть", "/удали", "/forget"}:
            if not arg:
                return "Что именно забыть? Формат: /забыть вопрос"
            return self.forget(arg)
        if cmd in {"/база", "/знания", "/список", "/list"}:
            if not self.knowledge:
                return "База знаний пуста."
            lines = [f"В базе знаний {len(self.knowledge)} записей. Вот первые:"]
            for item in self.knowledge[:10]:
                lines.append(f"  — {item['q']}")
            if len(self.knowledge) > 10:
                lines.append("  …и другие.")
            return "\n".join(lines)
        if cmd in {"/болтать", "/расскажи", "/история", "/talk"}:
            return self.tell_story()
        if cmd in {"/профиль", "/профиль!", "/я", "/profile"}:
            name = self.profile.get("name")
            if name:
                return f"Я помню, что вас зовут {name}. И ещё я знаю {len(self.knowledge)} ответов."
            return f"Мы пока не знакомились. Я знаю {len(self.knowledge)} ответов."
        if cmd in {"/пропустить", "/скип", "/скип!"}:
            self._pending_question = None
            return "Хорошо, проехали."
        return "Не знаю такой команды. Наберите /помощь, чтобы увидеть список."

    # ---------- статистика ----------

    def stats(self):
        name = self.profile.get("name") or "гость"
        return (
            f"Пользователь: {name}; записей в базе знаний: "
            f"{len(self.knowledge)}; ответов дано: {self.replies_given}."
        )
