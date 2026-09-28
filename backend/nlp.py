"""Rule-based natural language parser for shopping commands.

No AI service and no machine learning: just word lists and regular expressions.

    parse_command("Add 2 bottles of water")
    -> {"intent": "ADD", "item": "water", "quantity": 2, "unit": "bottles"}

Pipeline (each step is a small function below):
    1. _clean          lowercase, fix Hindi spellings, strip punctuation
    2. _extract_price  "under 100", "between 50 and 150" ...
    3. _apply_phrases  "take off" -> "remove", "show me" -> "find" ...
    4. numbers/translate  "two" -> 2, Hindi nouns -> English nouns
    5. _detect_intent  ADD / REMOVE / UPDATE / SEARCH
    6. _extract_brand, _extract_quantity, _extract_item
"""
import re
import unicodedata

from .text_utils import singular, tokens as _catalog_tokens  # noqa: F401 (tokens kept for tests)


# ----------------------------------------------------------- Hindi helpers
def _hi(text: str) -> str:
    """Normalize Devanagari so different spellings compare equal.

    Speech engines spell the same word in several ways (with/without the
    nukta dot, chandrabindu vs anusvara). We remove those differences.
    """
    text = unicodedata.normalize("NFC", text)
    return text.replace("\u093c", "").replace("\u0901", "\u0902")


def _words(*items) -> set:
    return {_hi(w) for w in items}


_DEVANAGARI = re.compile(r"[\u0900-\u097f]")
_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")


def detect_language(text: str) -> str:
    return "hi" if _DEVANAGARI.search(text or "") else "en"


# ------------------------------------------------------------ intent words
UPDATE_WORDS = _words(
    "change", "update", "modify", "edit", "set", "adjust",
    "बदलो", "बदल", "बदलना", "बदलिए", "बदलें", "अपडेट", "मात्रा",
    "badlo", "badal",
)
REMOVE_WORDS = _words(
    "remove", "delete", "cancel", "discard", "erase",
    "हटाओ", "हटा", "हटाना", "हटाइए", "हटाएं", "निकालो", "निकाल", "निकालना",
    "निकालिए", "मिटाओ", "मिटा", "डिलीट", "रिमूव",
    "hatao", "hata", "nikalo", "mita",
)
SEARCH_WORDS = _words(
    "find", "search", "locate", "browse",
    "खोजो", "खोज", "खोजें", "खोजिए", "खोजना", "ढूंढो", "ढूंढ", "ढूंढना",
    "ढूंढिए", "दिखाओ", "दिखा", "दिखाइए", "दिखाना", "सर्च",
    "khojo", "khoj", "dhundo", "dikhao",
)
ADD_WORDS = _words(
    "add", "buy", "need", "want", "get", "purchase", "order", "put", "include",
    "pick", "grab",
    "जोड़ो", "जोड़", "जोड़ना", "जोड़िए", "जोड़ें", "ऐड", "एड",
    "खरीदो", "खरीदना", "खरीद", "खरीदें", "खरीदिए",
    "लाओ", "लाना", "ला", "लेना", "ले", "लो", "चाहिए", "चाहिये", "चाहता",
    "चाहती", "चाहते", "डालो", "डाल",
    "jodo", "jod", "kharido", "kharid", "chahiye", "lao", "lena", "dalo",
)
# Order matters: "I need to remove milk" contains 'need' (ADD) but means REMOVE.
INTENT_ORDER = [("UPDATE", UPDATE_WORDS), ("REMOVE", REMOVE_WORDS),
                ("SEARCH", SEARCH_WORDS), ("ADD", ADD_WORDS)]

FILLER_WORDS = _words(
    # English
    "a", "an", "the", "some", "any", "of", "my", "me", "i", "we", "us", "please",
    "kindly", "can", "could", "would", "will", "you", "to", "from", "in", "on",
    "into", "for", "list", "shopping", "cart", "basket", "wishlist", "product",
    "products", "item", "items", "quantity", "qty", "amount", "number", "more",
    "another", "also", "just", "like", "id", "is", "are", "it", "and", "with",
    "as", "at", "by", "now", "up",
    # Hindi
    "दो", "दीजिए", "दीजिये", "करो", "कीजिए", "कीजिये", "कर", "करना", "दें", "दे",
    "है", "हैं", "हूं", "मुझे", "मैं", "हमें", "मेरी", "मेरे", "मेरा", "में",
    "से", "को", "का", "की", "के", "लिस्ट", "सूची", "शॉपिंग", "कार्ट", "टोकरी",
    "कृपया", "प्लीज", "जरा", "अब", "भी", "और", "पर", "तक", "सामान", "चीज", "चीजें",
    "wala", "ko", "ka", "ki", "mein", "mujhe",
)

# ---------------------------------------------------------------- numbers
EN_NUMBERS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20, "half": 0.5,
}
HI_NUMBERS = {_hi(k): v for k, v in {
    "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पांच": 5, "पाँच": 5, "छह": 6, "छे": 6,
    "सात": 7, "आठ": 8, "नौ": 9, "दस": 10,
}.items()}
# "दो" also means "give" (जोड़ दो). It is a number only when not after a verb.
HI_VERB_STEMS = _words("जोड़", "हटा", "निकाल", "खोज", "ढूंढ", "बदल", "कर", "ले",
                       "खरीद", "डाल", "दिखा", "मिटा", "लगा")

# ------------------------------------------------------------------ units
UNIT_CANON = {
    "kg": "kg", "kgs": "kg", "kilo": "kg", "kilos": "kg", "kilogram": "kg",
    "kilograms": "kg",
    "g": "g", "gm": "g", "gms": "g", "gram": "g", "grams": "g",
    "ml": "ml", "millilitre": "ml", "millilitres": "ml", "milliliter": "ml",
    "milliliters": "ml",
    "l": "litre", "ltr": "litre", "litre": "litre", "litres": "litre",
    "liter": "litre", "liters": "litre",
    "bottle": "bottle", "bottles": "bottles", "packet": "packet",
    "packets": "packets", "pack": "pack", "packs": "packs", "box": "box",
    "boxes": "boxes", "can": "can", "cans": "cans", "bag": "bag", "bags": "bags",
    "dozen": "dozen", "piece": "piece", "pieces": "pieces", "pcs": "pieces",
    "pc": "piece", "loaf": "loaf", "loaves": "loaves", "bunch": "bunch",
    "bunches": "bunches", "carton": "carton", "cartons": "cartons",
    "tube": "tube", "tubes": "tubes", "jar": "jar", "jars": "jars",
}
# Units allowed to stand alone ("a bottle of water"). 'can' and 'g' are excluded
# because 'can' is also a normal word ("can you add milk").
UNIT_ONLY_OK = {"bottle", "bottles", "packet", "packets", "pack", "packs", "box",
                "boxes", "dozen", "loaf", "loaves", "bunch", "bunches", "carton",
                "cartons", "piece", "pieces", "bag", "bags", "jar", "jars",
                "tube", "tubes"}
SIZE_UNITS = {"kg", "g", "ml", "litre"}
HI_UNITS = {_hi(k): v for k, v in {
    "बोतल": "bottle", "बोतलें": "bottle", "पैकेट": "packet", "पैक": "pack",
    "किलो": "kg", "ग्राम": "g", "लीटर": "litre", "दर्जन": "dozen",
    "डिब्बा": "box", "डिब्बे": "box", "पीस": "piece", "नग": "piece",
    "किलोग्राम": "kg",
}.items()}
PLURALIZE = {"bottle": "bottles", "packet": "packets", "pack": "packs",
             "box": "boxes", "piece": "pieces", "litre": "litres"}

# ------------------------------------------------ Hindi -> English product words
HI_PHRASES = {_hi(k): v for k, v in {
    "कोका कोला": "coca cola", "डबल रोटी": "bread", "नींबू पानी": "lemonade",
    "टमाटर सॉस": "tomato sauce", "टमाटर सॉस": "tomato sauce",
    "माउंटेन ड्यू": "mountain dew", "टूथ पेस्ट": "toothpaste",
    "बर्गर बन": "burger buns", "बर्गर बन्स": "burger buns",
    "करेला": "bitter gourd", "लॉन्ड्री डिटर्जेंट": "laundry detergent",
    "डिश सोप": "dish soap", "फ्लोर क्लीनर": "floor cleaner",
    "मदर डेयरी": "mother dairy",
}.items()}
HI_WORDS = {_hi(k): v for k, v in {
    "दूध": "milk", "ब्रेड": "bread", "मक्खन": "butter", "बटर": "butter",
    "चीज": "cheese", "चीज़": "cheese", "पनीर": "paneer", "सेब": "apple",
    "केला": "banana", "केले": "banana", "आम": "mango", "संतरा": "orange",
    "संतरे": "orange", "अंगूर": "grapes", "भिंडी": "ladyfinger",
    "गाजर": "carrot", "आलू": "potato", "टमाटर": "tomato", "कटहल": "jackfruit",
    "चावल": "rice", "चीनी": "sugar", "शक्कर": "sugar", "नमक": "salt",
    "चाय": "tea", "कॉफी": "coffee", "कॉफ़ी": "coffee", "पानी": "water",
    "पास्ता": "pasta", "बिस्किट": "biscuits", "बिस्कुट": "biscuits",
    "जैम": "jam", "मैगी": "maggie", "नूडल्स": "noodles", "टूथपेस्ट": "toothpaste",
    "साबुन": "soap", "ओरियो": "oreo", "लेज": "lays", "कुरकुरे": "kurkure",
    "पेप्सी": "pepsi", "स्प्राइट": "sprite", "फैंटा": "fanta", "कोक": "coke",
    "अमूल": "amul", "कोलगेट": "colgate", "पेप्सोडेंट": "pepsodent",
    "सेंसोडाइन": "sensodyne", "लेमोनेड": "lemonade", "कोला": "cola",
    "जूस": "juice", "अंडे": "eggs", "अंडा": "eggs",
    "doodh": "milk", "chai": "tea", "paani": "water", "seb": "apple",
    "kela": "banana", "chawal": "rice", "cheeni": "sugar", "namak": "salt",
}.items()}

# --------------------------------------------------------- price patterns
_CUR = r"(?:(?:rs|inr|rupees?|रुपये|रुपए|रुपया|रूपये)(?=\s|$))?"
_NUM = r"(\d+(?:\.\d+)?)"
_BETWEEN = rf"\b(?:between|from)\s+{_CUR}\s*{_NUM}\s*{_CUR}\s*(?:and|to)\s*{_CUR}\s*{_NUM}\s*{_CUR}"
_MAX_EN = (rf"\b(?:under|below|less than|lower than|cheaper than|upto|up to|within|at most|"
           rf"not more than|no more than|maximum|max|budget of|budget)\s+{_CUR}\s*{_NUM}\s*{_CUR}")
_MIN_EN = (rf"\b(?:above|over|more than|greater than|at least|minimum|min|starting from|"
           rf"costing more than)\s+{_CUR}\s*{_NUM}\s*{_CUR}")
_BETWEEN_HI = rf"{_NUM}\s*{_CUR}\s*(?:और|से)\s*{_CUR}\s*{_NUM}\s*{_CUR}\s*(?:के\s+बीच|तक)"
_MAX_HI = rf"{_NUM}\s*{_CUR}\s*(?:से\s+कम|के\s+अंदर|के\s+नीचे|से\s+नीचे|तक)"
_MIN_HI = rf"{_NUM}\s*{_CUR}\s*(?:से\s+ज्यादा|से\s+अधिक|से\s+ऊपर|से\s+जादा)"


def _num(text):
    value = float(text)
    return int(value) if value.is_integer() else value


def _extract_price(text: str):
    """Return ({"min_price":..,"max_price":..}, text_without_price_words)."""
    prices = {}
    for pattern, kind in ((_BETWEEN, "between"), (_BETWEEN_HI, "between"),
                          (_MAX_EN, "max"), (_MAX_HI, "max"),
                          (_MIN_EN, "min"), (_MIN_HI, "min")):
        match = re.search(pattern, text)
        if not match:
            continue
        if kind == "between":
            low, high = sorted((_num(match.group(1)), _num(match.group(2))))
            prices.setdefault("min_price", low)
            prices.setdefault("max_price", high)
        elif kind == "max":
            prices.setdefault("max_price", _num(match.group(1)))
        else:
            prices.setdefault("min_price", _num(match.group(1)))
        text = text[:match.start()] + " " + text[match.end():]
    return prices, text


# ------------------------------------------------------------ text cleanup
def _clean(text: str) -> str:
    text = _hi(text.lower()).translate(_DIGITS)
    text = text.replace("₹", " rs ").replace("'", "").replace("’", "")
    text = re.sub(r"[-_/]", " ", text)
    text = re.sub(r"[।॥]", " ", text)
    text = re.sub(r"[^\w\s.\u0900-\u097f]", " ", text)
    text = re.sub(r"(?<!\d)\.|\.(?!\d)", " ", text)
    return re.sub(r"\s+", " ", text).strip()


_EN_PHRASES = [
    (r"\btake (?:it |them )?(?:off|out|away)\b", "remove"),
    (r"\bget rid of\b", "remove"),
    (r"\b(?:show me|look for|look up|looking for|search for|find me|check for)\b", "find"),
    (r"\b(?:i would|id|we would) like(?: to)?\b", "want"),
    (r"\bget me\b", "get"),
]


def _apply_phrases(text: str) -> str:
    for pattern, replacement in _EN_PHRASES:
        text = re.sub(pattern, replacement, text)
    padded = f" {text} "
    for phrase in sorted(HI_PHRASES, key=len, reverse=True):
        padded = padded.replace(f" {phrase} ", f" {HI_PHRASES[phrase]} ")
    return padded.strip()


def _convert_numbers(toks: list) -> list:
    out = []
    for i, tok in enumerate(toks):
        if tok in EN_NUMBERS:
            out.append(str(EN_NUMBERS[tok]))
        elif tok in HI_NUMBERS:
            is_helper_verb = tok == _hi("दो") and (i == len(toks) - 1 or toks[i - 1] in HI_VERB_STEMS)
            out.append(tok if is_helper_verb else str(HI_NUMBERS[tok]))
        else:
            out.append(tok)
    return out


def _translate(toks: list) -> list:
    out = []
    for tok in toks:
        if tok in HI_UNITS:
            out.append(HI_UNITS[tok])
        else:
            out.append(HI_WORDS.get(tok, tok))
    return out


def _detect_intent(toks: list):
    for intent, words in INTENT_ORDER:
        if any(tok in words for tok in toks):
            return intent
    return None


def _extract_brand(toks: list, known_brands: list):
    """Find a known brand (longest first) and remove it from the tokens."""
    singular_toks = [singular(t) for t in toks]
    for brand in sorted(known_brands, key=lambda b: -len(b.split())):
        brand_toks = [singular(t) for t in _clean(brand).split()]
        if not brand_toks:
            continue
        size = len(brand_toks)
        for start in range(len(toks) - size + 1):
            if singular_toks[start:start + size] == brand_toks:
                return brand, toks[:start] + toks[start + size:]
    return None, toks


_NUMBER = re.compile(r"^\d+(?:\.\d+)?$")


def _extract_quantity(toks: list, intent: str):
    """Return (quantity, unit, size, remaining_tokens)."""
    # 1) a number followed by a unit: "2 bottles", "500 ml"
    for i in range(len(toks) - 1):
        if _NUMBER.match(toks[i]) and toks[i + 1] in UNIT_CANON:
            number, unit = _num(toks[i]), UNIT_CANON[toks[i + 1]]
            rest = toks[:i] + toks[i + 2:]
            if intent == "SEARCH":
                return None, None, (f"{number} {unit}" if unit in SIZE_UNITS else None), rest
            return number, unit, None, rest
    # 2) a plain number: "5 oranges", "to 3"
    for i, tok in enumerate(toks):
        if _NUMBER.match(tok):
            rest = toks[:i] + toks[i + 1:]
            return (None if intent == "SEARCH" else _num(tok)), None, None, rest
    # 3) a unit with no number: "a bottle of water", "a dozen eggs"
    if intent != "SEARCH":
        for i, tok in enumerate(toks):
            if tok in UNIT_ONLY_OK:
                return 1, UNIT_CANON[tok], None, toks[:i] + toks[i + 1:]
    return None, None, None, toks


def _extract_item(toks: list) -> str:
    intent_words = UPDATE_WORDS | REMOVE_WORDS | SEARCH_WORDS | ADD_WORDS
    kept = [t for t in toks
            if t not in FILLER_WORDS and t not in intent_words and not _NUMBER.match(t)]
    return " ".join(kept).strip()


# ----------------------------------------------------------------- public
def parse_command(text: str, known_brands=None) -> dict:
    """Turn a sentence into {"intent", "item", "quantity", "unit", "brand", ...}.

    Only the fields that were found are included. Unknown sentences return
    {"intent": "UNKNOWN"}.
    """
    original = text or ""
    cleaned = _clean(original)
    prices, cleaned = _extract_price(cleaned)
    cleaned = _apply_phrases(cleaned)
    toks = _translate(_convert_numbers(cleaned.split()))

    intent = _detect_intent(toks)
    if intent is None:
        return {"intent": "UNKNOWN"}

    brand, toks = _extract_brand(toks, known_brands or [])
    quantity, unit, size, toks = _extract_quantity(toks, intent)
    item = _extract_item(toks)

    if brand and not item and intent != "SEARCH":
        item, brand = brand.lower(), None      # e.g. "add Kurkure": the brand IS the item

    if unit and quantity and quantity > 1 and detect_language(original) == "hi":
        unit = PLURALIZE.get(unit, unit)       # Hindi says "2 बोतल", English says "2 bottles"

    result = {"intent": intent}
    if item:
        result["item"] = item
    if quantity is not None:
        result["quantity"] = quantity
    if unit:
        result["unit"] = unit
    if brand:
        result["brand"] = brand
    if size:
        result["size"] = size
    result.update(prices)
    return result
