"""Product lookup and search over products.json (no database, no ML)."""
import re

from . import data_manager
from .text_utils import tokens


def _product_tokens(product: dict) -> set:
    """Every word that can be used to find this product."""
    words = set()
    for field in (product["name"], product.get("brand"), product.get("generic"),
                  product.get("category")):
        words.update(tokens(field))
    for extra in product.get("tags", []) + product.get("aliases", []):
        words.update(tokens(extra))
    return words


def _score(query_tokens: list, product: dict, product_tokens: set) -> float:
    """0 = no match. Higher = better match."""
    if not query_tokens:
        return 1.0
    wanted = set(query_tokens)
    if not wanted <= product_tokens:
        return 0.0
    name_tokens = set(tokens(product["name"]))
    score = 1.0
    if wanted == name_tokens:
        score += 10
    elif wanted <= name_tokens:
        score += 4
    if wanted == set(tokens(product.get("generic"))):
        score += 2
    if any(wanted == set(tokens(alias)) for alias in product.get("aliases", [])):
        score += 10
    if product.get("available", True):
        score += 1
    return score - 0.01 * len(name_tokens - wanted)


def _normalize_size(text) -> str:
    return re.sub(r"[^a-z0-9.]", "", str(text or "").lower())


def get_brands() -> list:
    return sorted({p["brand"] for p in data_manager.get_products() if p.get("brand")})


def search_products(query="", brand=None, min_price=None, max_price=None, size=None) -> list:
    """Filter the catalog. Every filter is optional."""
    products = data_manager.get_products()
    query_tokens = tokens(query)

    def run(qtokens):
        found = []
        brand_tokens = set(tokens(brand)) if brand else set()
        wanted_size = _normalize_size(size) if size else ""
        for product in products:
            if brand_tokens and not brand_tokens <= set(tokens(product.get("brand"))):
                continue
            price = product.get("price", 0)
            if min_price is not None and price < min_price:
                continue
            if max_price is not None and price > max_price:
                continue
            if wanted_size and wanted_size not in _normalize_size(product.get("size")):
                continue
            score = _score(qtokens, product, _product_tokens(product))
            if score > 0:
                found.append((score, product))
        found.sort(key=lambda pair: (-pair[0], pair[1].get("price", 0), pair[1]["name"]))
        return [p for _, p in found]

    results = run(query_tokens)
    if not results and len(query_tokens) > 1:
        # Fallback: ignore words that no product knows (e.g. "kids").
        vocabulary = set()
        for product in products:
            vocabulary |= _product_tokens(product)
        known = [t for t in query_tokens if t in vocabulary]
        if known and known != query_tokens:
            results = run(known)
    return results


def resolve_item(item_text: str, brand=None) -> dict:
    """Decide what a spoken/typed item really is.

    Returns {"name", "category", "product" (or None), "specific"}.
    * "amul milk" / "oreo"  -> a specific catalog product
    * "milk", "apples"...    -> a generic list item; category comes from the catalog
    """
    wanted = set(tokens(item_text))
    matches = search_products(item_text, brand=brand)

    def is_exact(product):
        if set(tokens(product["name"])) == wanted:
            return True
        return any(set(tokens(a)) == wanted for a in product.get("aliases", []))

    exact = next((p for p in matches if is_exact(p)), None)
    if exact:
        return {"name": exact["name"], "category": exact["category"],
                "product": exact, "specific": True}
    if brand and matches:
        return {"name": matches[0]["name"], "category": matches[0]["category"],
                "product": matches[0], "specific": True}
    category = matches[0]["category"] if matches else "Other"
    return {"name": (item_text or "").strip().title(), "category": category,
            "product": None, "specific": False}
