"""All reading and writing of the JSON "database" lives here.

Files (in backend/data/):
    products.json, shopping_list.json, shopping_history.json,
    recommendation_rules.json
Missing or corrupt files are recreated with sensible defaults.
"""
import json
import os
import tempfile
import threading
import uuid
from datetime import datetime
from pathlib import Path

from .text_utils import format_number, name_key

DATA_DIR = Path(__file__).resolve().parent / "data"

CATEGORIES = [
    "Dairy", "Fruits", "Vegetables", "Bakery", "Snacks",
    "Beverages", "Groceries", "Personal Care", "Household", "Other",
]

DEFAULTS = {
    "products.json": [],
    "shopping_list.json": [],
    "shopping_history.json": [],
    "recommendation_rules.json": {},
}

_lock = threading.RLock()


# ---------------------------------------------------------------- file basics
def ensure_data_files():
    """Create the data folder and any missing JSON file."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for filename, default in DEFAULTS.items():
        path = DATA_DIR / filename
        if not path.exists():
            _write(path, default)


def _write(path: Path, data):
    """Write atomically so a crash can't leave half a file behind."""
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp:
            json.dump(data, tmp, indent=2, ensure_ascii=False)
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.remove(tmp_name)


def load_json(filename: str):
    with _lock:
        ensure_data_files()
        path = DATA_DIR / filename
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            default = json.loads(json.dumps(DEFAULTS[filename]))
            _write(path, default)      # reset a corrupt file
            return default


def save_json(filename: str, data):
    with _lock:
        ensure_data_files()
        _write(DATA_DIR / filename, data)


# ------------------------------------------------------------------- catalog
def get_products() -> list:
    return load_json("products.json")


def get_product(product_id: str):
    for product in get_products():
        if product["id"] == product_id:
            return product
    return None


def get_rules() -> dict:
    return load_json("recommendation_rules.json")


# ------------------------------------------------------------- shopping list
def get_shopping_list() -> list:
    return load_json("shopping_list.json")


def _new_id() -> str:
    return uuid.uuid4().hex[:10]


def add_to_list(name, quantity=1, unit=None, category="Other", product_id=None):
    """Add an item, or increase the quantity if it is already on the list.

    Returns (item, created) where created is False when we merged.
    """
    with _lock:
        items = get_shopping_list()
        key = name_key(name)
        for item in items:
            if not item["purchased"] and name_key(item["name"]) == key:
                item["quantity"] = format_number(item["quantity"] + quantity)
                if unit and not item.get("unit"):
                    item["unit"] = unit
                save_json("shopping_list.json", items)
                return item, False
        item = {
            "id": _new_id(),
            "name": name,
            "quantity": format_number(quantity),
            "unit": unit or None,
            "category": category if category in CATEGORIES else "Other",
            "purchased": False,
            "product_id": product_id,
        }
        items.append(item)
        save_json("shopping_list.json", items)
        return item, True


def get_list_item(item_id):
    for item in get_shopping_list():
        if item["id"] == item_id:
            return item
    return None


def remove_from_list(item_id):
    """Remove and return the item, or None if it does not exist."""
    with _lock:
        items = get_shopping_list()
        for index, item in enumerate(items):
            if item["id"] == item_id:
                removed = items.pop(index)
                save_json("shopping_list.json", items)
                return removed
        return None


def update_list_item(item_id, quantity=None, unit=None):
    """Change quantity and/or unit. Returns the updated item or None."""
    with _lock:
        items = get_shopping_list()
        for item in items:
            if item["id"] == item_id:
                if quantity is not None:
                    item["quantity"] = format_number(quantity)
                if unit is not None:
                    item["unit"] = unit.strip() or None
                save_json("shopping_list.json", items)
                return item
        return None


def mark_purchased(item_id):
    """Flag the item as purchased and record it in the history file.

    Returns the item, or None if not found. Raises ValueError if it was
    already purchased.
    """
    with _lock:
        items = get_shopping_list()
        for item in items:
            if item["id"] == item_id:
                if item["purchased"]:
                    raise ValueError("already purchased")
                item["purchased"] = True
                save_json("shopping_list.json", items)
                add_history_entry(item)
                return item
        return None


def clear_purchased() -> int:
    with _lock:
        items = get_shopping_list()
        remaining = [i for i in items if not i["purchased"]]
        save_json("shopping_list.json", remaining)
        return len(items) - len(remaining)


# ------------------------------------------------------------------- history
def get_history() -> list:
    return load_json("shopping_history.json")


def add_history_entry(item: dict):
    with _lock:
        history = get_history()
        history.append({
            "id": _new_id(),
            "name": item["name"],
            "product_id": item.get("product_id"),
            "category": item.get("category", "Other"),
            "quantity": item.get("quantity", 1),
            "unit": item.get("unit"),
            "purchased_at": datetime.now().isoformat(timespec="seconds"),
        })
        save_json("shopping_history.json", history)
