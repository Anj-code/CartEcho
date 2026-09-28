"""The "brain" that turns requests into actions on the shopping list.

Both the voice/typed /command endpoint and the normal button endpoints use the
functions in this file, so the behaviour is identical everywhere.
"""
from . import catalog, data_manager, nlp, substitutes
from .text_utils import format_number, tokens

EXAMPLE_HINT = 'Try: "Add milk"'


class ShoppingError(Exception):
    """A problem the user can understand. `status_code` is used by REST endpoints."""

    def __init__(self, message, status_code=400, extra=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.extra = extra or {}


# ------------------------------------------------------------- helpers
def _find_list_item(text: str):
    """Find a list item by (partial) name. Exact matches win over partial ones."""
    wanted = set(tokens(text))
    if not wanted:
        return None
    partial = None
    for item in data_manager.get_shopping_list():
        item_tokens = set(tokens(item["name"]))
        if item_tokens == wanted and not item["purchased"]:
            return item
        if wanted <= item_tokens and (partial is None or (partial["purchased"] and not item["purchased"])):
            partial = item
    return partial


def _with_alternatives(product: dict) -> dict:
    """Copy of a catalog product; unavailable ones also carry their substitutes."""
    enriched = dict(product)
    if not product.get("available", True):
        info = substitutes.get_substitutes(product["id"])
        enriched["substitutes"] = info["substitutes"] if info else []
    return enriched


def _added_message(name, quantity, unit) -> str:
    qty = format_number(quantity)
    if unit:
        return f"Added {qty} {unit} of {name.lower()} to your shopping list."
    if quantity != 1:
        return f"Added {qty} {name} to your shopping list."
    return f"Added {name} to your shopping list."


# -------------------------------------------------------- list actions
def add_item(name=None, quantity=1, unit=None, brand=None, product_id=None) -> dict:
    """Add by catalog `product_id` (buttons) or by spoken `name` (voice/typing)."""
    if product_id:
        product = data_manager.get_product(product_id)
        if product is None:
            raise ShoppingError("That product doesn't exist.", 404)
        resolved = {"name": product["name"], "category": product["category"],
                    "product": product, "specific": True}
    elif name and name.strip():
        resolved = catalog.resolve_item(name, brand=brand)
    else:
        raise ShoppingError("Tell me which item to add.", 400)

    product = resolved["product"] if resolved["specific"] else None
    if product and not product.get("available", True):
        info = substitutes.get_substitutes(product["id"])
        raise ShoppingError(
            f"{product['name']} is currently unavailable.", 409,
            {"product": info["product"] if info else None,
             "substitutes": info["substitutes"] if info else []})

    item, created = data_manager.add_to_list(
        resolved["name"], quantity, unit, resolved["category"],
        product["id"] if product else None)
    return {"item": item, "created": created,
            "message": _added_message(resolved["name"], quantity, unit)}


def remove_item_by_id(item_id: str) -> dict:
    removed = data_manager.remove_from_list(item_id)
    if removed is None:
        raise ShoppingError("That item isn't in your shopping list.", 404)
    return {"item": removed, "message": f"Removed {removed['name']} from your shopping list."}


def remove_item_by_name(text: str) -> dict:
    found = _find_list_item(text)
    if found is None:
        raise ShoppingError(f"{text.title()} isn't in your shopping list.", 404)
    return remove_item_by_id(found["id"])


def update_item(item_id: str, quantity=None, unit=None) -> dict:
    if quantity is None and unit is None:
        raise ShoppingError("Nothing to update. Send a quantity or a unit.", 400)
    updated = data_manager.update_list_item(item_id, quantity, unit)
    if updated is None:
        raise ShoppingError("That item isn't in your shopping list.", 404)
    return {"item": updated,
            "message": f"Updated {updated['name']} to {format_number(updated['quantity'])}"
                       f"{(' ' + updated['unit']) if updated.get('unit') else ''}."}


def update_item_by_name(text: str, quantity, unit=None) -> dict:
    found = _find_list_item(text)
    if found is None:
        raise ShoppingError(f"{text.title()} isn't in your shopping list.", 404)
    return update_item(found["id"], quantity, unit)


def purchase_item(item_id: str) -> dict:
    try:
        item = data_manager.mark_purchased(item_id)
    except ValueError:
        raise ShoppingError("That item is already marked as purchased.", 409)
    if item is None:
        raise ShoppingError("That item isn't in your shopping list.", 404)
    return {"item": item, "message": f"Marked {item['name']} as purchased."}


# ------------------------------------------------------------- search
def search(query="", brand=None, min_price=None, max_price=None, size=None) -> dict:
    if min_price is not None and max_price is not None and min_price > max_price:
        raise ShoppingError("Minimum price can't be higher than maximum price.", 400)
    found = catalog.search_products(query, brand, min_price, max_price, size)
    filters = {"query": query or None, "brand": brand, "min_price": min_price,
               "max_price": max_price, "size": size}
    return {"count": len(found), "filters": filters,
            "products": [_with_alternatives(p) for p in found]}


# -------------------------------------------------------- /command
def execute_command(text: str) -> dict:
    """Parse a sentence and do what it says. Always returns a dict with `success`."""
    parsed = nlp.parse_command(text, known_brands=catalog.get_brands())
    intent = parsed["intent"]
    response = {"success": False, "understood": intent != "UNKNOWN", "intent": intent,
                "text": text, "language": nlp.detect_language(text)}
    for key in ("item", "quantity", "unit", "brand", "size", "min_price", "max_price"):
        if key in parsed:
            response[key] = parsed[key]

    if intent == "UNKNOWN":
        response.update(message="I didn't understand that command.", hint=EXAMPLE_HINT)
        return response

    item = parsed.get("item")
    try:
        if intent == "ADD":
            if not item:
                raise ShoppingError("What would you like to add?", 400)
            quantity = parsed.get("quantity", 1)
            result = add_item(name=item, quantity=quantity, unit=parsed.get("unit"),
                              brand=parsed.get("brand"))
            response.update(success=True, quantity=quantity, added_item=result["item"],
                            message=result["message"])

        elif intent == "REMOVE":
            if not item:
                raise ShoppingError("What would you like to remove?", 400)
            result = remove_item_by_name(_with_brand(item, parsed))
            response.update(success=True, removed_item=result["item"], message=result["message"])

        elif intent == "UPDATE":
            if not item or "quantity" not in parsed:
                raise ShoppingError('Tell me the item and new quantity, e.g. "Change milk quantity to 3".', 400)
            result = update_item_by_name(_with_brand(item, parsed), parsed["quantity"], parsed.get("unit"))
            response.update(success=True, updated_item=result["item"], message=result["message"])

        elif intent == "SEARCH":
            if not any(k in parsed for k in ("item", "brand", "min_price", "max_price", "size")):
                raise ShoppingError("What would you like to search for?", 400)
            result = search(item or "", parsed.get("brand"), parsed.get("min_price"),
                            parsed.get("max_price"), parsed.get("size"))
            count = result["count"]
            response.update(
                success=True, count=count, products=result["products"],
                filters=result["filters"],
                message=("Search completed." if count else "Search completed, but nothing matched."))
    except ShoppingError as error:
        response.update(message=error.message, hint=EXAMPLE_HINT if error.status_code == 400 else None,
                        **error.extra)
    return response


def _with_brand(item: str, parsed: dict) -> str:
    """'milk' + brand 'Amul' -> 'amul milk' so we can find 'Amul Milk' on the list."""
    return f"{parsed['brand']} {item}" if parsed.get("brand") else item
