"""Suggest alternatives when a product is unavailable (rule based)."""
from . import data_manager
from .text_utils import tokens

# Preference words -> the product tag that satisfies them.
PREFERENCE_TAGS = {
    "dairy-free": "dairy-free",
    "vegan": "vegan",
    "organic": "organic",
    "plant-based": "plant-based",
}


def _short(product: dict) -> dict:
    return {
        "id": product["id"], "name": product["name"], "brand": product.get("brand"),
        "category": product.get("category"), "price": product.get("price"),
        "size": product.get("size"), "available": product.get("available", True),
    }


def get_substitutes(product_id: str, preference=None, limit: int = 5):
    """Return {"product", "available", "preference", "substitutes"} or None if unknown.

    Order of ideas:
      1. the substitute_ids written in products.json
      2. other available products with the same generic type (e.g. other milks)
      3. only if nothing closer exists: other available products from the same category
    preference: "dairy-free", "vegan", "organic", "plant-based" or "cheaper".
    """
    product = data_manager.get_product(product_id)
    if product is None:
        return None

    catalog = data_manager.get_products()
    by_id = {p["id"]: p for p in catalog}

    candidates, seen = [], {product["id"]}

    def take(items):
        for candidate in items:
            if candidate["id"] not in seen and candidate.get("available", True):
                seen.add(candidate["id"])
                candidates.append(candidate)

    take(by_id[s] for s in product.get("substitute_ids", []) if s in by_id)
    generic = set(tokens(product.get("generic")))
    take(p for p in catalog if generic and set(tokens(p.get("generic"))) == generic)
    if not candidates:                     # last resort: anything else in the category
        take(p for p in catalog if p.get("category") == product.get("category"))

    pref = (preference or "").strip().lower() or None
    if pref == "cheaper":
        candidates = [c for c in candidates if c.get("price", 0) < product.get("price", 0)]
        candidates.sort(key=lambda c: c.get("price", 0))
    elif pref in PREFERENCE_TAGS:
        tag = PREFERENCE_TAGS[pref]
        candidates = [c for c in candidates if tag in c.get("tags", [])]

    return {
        "product": _short(product),
        "available": product.get("available", True),
        "preference": pref,
        "substitutes": [_short(c) for c in candidates[:limit]],
    }
