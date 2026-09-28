"""Rule-based recommendations. No machine learning - just lookups.

How it works (read top to bottom):
  1. Collect "trigger" items: things the user bought before (shopping_history.json)
     and things currently on the list.
  2. For each trigger, look for a rule in recommendation_rules.json
     (e.g. "milk" -> bread, butter).
  3. Skip rules whose product is already on the shopping list.
  4. Find the real product in products.json (only available ones).
  5. Remove duplicates and return each product with a clear reason.
"""
import re

from . import catalog, data_manager
from .text_utils import tokens


def _pretty_reason(reason: str, rule_key: str) -> str:
    """'Often bought together with milk' -> '... with Milk'."""
    return re.sub(re.escape(rule_key), rule_key.title(), reason, count=1, flags=re.I)


def _triggers() -> list:
    """History (newest first) followed by the pending items on the list."""
    history = sorted(data_manager.get_history(),
                     key=lambda h: h.get("purchased_at", ""), reverse=True)
    triggers = [{"name": h["name"], "product_id": h.get("product_id")} for h in history]
    for item in data_manager.get_shopping_list():
        if not item["purchased"]:
            triggers.append({"name": item["name"], "product_id": item.get("product_id")})
    return triggers


def _pick_product(rule: dict, trigger: dict):
    """Choose one available catalog product for a rule."""
    options = [p for p in catalog.search_products(rule["product"]) if p.get("available", True)]
    if not options:
        return None
    if rule.get("prefer_other_brand"):
        bought = data_manager.get_product(trigger.get("product_id")) if trigger.get("product_id") else None
        if bought:
            for option in options:
                if option.get("brand") != bought.get("brand"):
                    return option
    return options[0]


def get_recommendations(limit: int = 8) -> dict:
    rules = data_manager.get_rules()
    on_list = [set(tokens(i["name"])) for i in data_manager.get_shopping_list()]
    listed_ids = {i.get("product_id") for i in data_manager.get_shopping_list() if i.get("product_id")}

    recommendations, seen_ids = [], set()
    for trigger in _triggers():
        trigger_tokens = set(tokens(trigger["name"]))
        for rule_key, rule_list in rules.items():
            if not set(tokens(rule_key)) <= trigger_tokens:
                continue
            for rule in rule_list:
                target_tokens = set(tokens(rule["product"]))
                if any(target_tokens <= present for present in on_list):
                    continue                      # already on the list
                product = _pick_product(rule, trigger)
                if product is None:
                    continue
                if product["id"] in seen_ids or product["id"] in listed_ids:
                    continue                      # duplicate
                seen_ids.add(product["id"])
                recommendations.append({
                    "product_id": product["id"],
                    "name": product["name"],
                    "brand": product.get("brand"),
                    "category": product.get("category"),
                    "price": product.get("price"),
                    "size": product.get("size"),
                    "reason": _pretty_reason(rule["reason"], rule_key),
                    "based_on": trigger["name"],
                })
                if len(recommendations) >= limit:
                    return {"recommendations": recommendations}
    return {"recommendations": recommendations}
