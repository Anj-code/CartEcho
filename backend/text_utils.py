"""Tiny text helpers shared by the whole backend (no third-party imports)."""
import re

_WORD_CHARS = re.compile(r"[^a-z0-9\u0900-\u097f]+")


def singular(word: str) -> str:
    """Very small 'plural -> singular' rule so 'apples' matches 'apple'."""
    w = word.lower()
    if len(w) > 3:
        if w.endswith(("atoes", "angoes")):      # tomatoes, potatoes, mangoes
            return w[:-2]
        if w.endswith(("ss", "us", "is")):        # glass, hummus, tennis
            return w
        if w.endswith("s"):
            return w[:-1]
    return w


def tokens(text) -> list:
    """Lowercase, drop punctuation, split into words and singularize them."""
    if not text:
        return []
    cleaned = _WORD_CHARS.sub(" ", str(text).lower().replace("'", ""))
    return [singular(w) for w in cleaned.split()]


def name_key(text) -> str:
    """Order-independent key used to decide if two names are the same thing."""
    return " ".join(sorted(tokens(text)))


def format_number(value):
    """3.0 -> 3, 2.5 -> 2.5 (keeps JSON and messages tidy)."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return value
    return int(number) if number.is_integer() else round(number, 2)
