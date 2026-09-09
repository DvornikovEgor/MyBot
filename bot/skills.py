"""Отдельные умения бота: безопасный калькулятор, дата/время, случайный выбор.

Калькулятор написан через разбор AST (модуль `ast`) — функция `eval` не
используется, поэтому выполнить произвольный код через него невозможно.
"""

import ast
import datetime
import operator
import random
import re

_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}

MAX_POWER = 64  # защита от выражений вида 9**999999999

_MATH_RE = re.compile(r"\d+(?:[.,]\d+)?(?:[\s+\-*/%^().,]*\d+(?:[.,]\d+)?)+")

_DAYS = [
    "понедельник", "вторник", "среда", "четверг",
    "пятница", "суббота", "воскресенье",
]
_MONTHS = [
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
]


def _eval_node(node):
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        raise ValueError("разрешены только числа")
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > MAX_POWER:
            raise ValueError("слишком большая степень")
        return _BIN_OPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_eval_node(node.operand))
    raise ValueError("неподдерживаемое выражение")


def _extend_parens(text, start, end, expr):
    """Добирает скобки вокруг найденного выражения: «(2+3)*4» → «(2+3)*4»."""
    need_open = expr.count(")") - expr.count("(")
    j = start - 1
    while need_open > 0 and j >= 0:
        if text[j] == "(":
            expr = "(" + expr
            need_open -= 1
        elif not text[j].isspace():
            break
        j -= 1
    need_close = expr.count("(") - expr.count(")")
    j = end
    while need_close > 0 and j < len(text):
        if text[j] == ")":
            expr += ")"
            need_close -= 1
        elif not text[j].isspace():
            break
        j += 1
    return expr


def try_calculate(text):
    """Ищет в тексте арифметику и считает её. Возвращает строку или None."""
    text = text or ""
    match = _MATH_RE.search(text)
    if not match:
        return None
    expr = _extend_parens(text, match.start(), match.end(), match.group(0))
    expr = expr.replace("^", "**").replace(",", ".")
    if not any(op in expr for op in "+-*/%"):
        return None
    try:
        tree = ast.parse(expr, mode="eval")
        result = _eval_node(tree)
    except ZeroDivisionError:
        return "Делить на ноль нельзя 🙂"
    except Exception:
        return None
    if isinstance(result, float):
        result = round(result, 6)
        if result.is_integer():
            result = int(result)
    return str(result)


def now_text():
    """Возвращает текущую дату и время красивой фразой."""
    now = datetime.datetime.now()
    day = _DAYS[now.weekday()]
    month = _MONTHS[now.month - 1]
    return (
        f"Сегодня {day}, {now.day} {month} {now.year} года. "
        f"Время — {now:%H:%M}."
    )


def flip_coin():
    return random.choice(["Орёл!", "Решка!"])


def roll_dice(sides=6):
    return f"На кубике выпало {random.randint(1, max(1, sides))}."


def rock_paper_scissors():
    return "Я выбираю: " + random.choice(["камень 🪨", "ножницы ✂️", "бумага 📄"])


def random_number(low=1, high=100):
    try:
        low, high = int(low), int(high)
    except (TypeError, ValueError):
        low, high = 1, 100
    if low > high:
        low, high = high, low
    return f"Моё число: {random.randint(low, high)}."
