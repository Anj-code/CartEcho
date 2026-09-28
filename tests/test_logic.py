"""Run with:  python -m unittest discover -s tests -v

These tests cover the NLP parser, catalog search, substitutes, recommendations
and the command executor. They use a temporary copy of backend/data so your
real JSON files are never touched.
"""
import shutil
import tempfile
import unittest
from pathlib import Path

from backend import catalog, commands, data_manager, nlp, recommendations, substitutes

BRANDS = ["Amul", "Colgate", "Mother Dairy", "Coca-Cola", "Kurkure"]
REAL_DATA = Path(data_manager.DATA_DIR)


class NlpTests(unittest.TestCase):
    def parse(self, text):
        return nlp.parse_command(text, BRANDS)

    def test_add_variations(self):
        for text in ["Add bananas", "I need bananas", "I want to buy bananas",
                     "Buy bananas", "Please add bananas to my shopping list"]:
            self.assertEqual(self.parse(text), {"intent": "ADD", "item": "bananas"}, text)

    def test_quantity_and_unit(self):
        self.assertEqual(self.parse("Add 2 bottles of water"),
                         {"intent": "ADD", "item": "water", "quantity": 2, "unit": "bottles"})
        self.assertEqual(self.parse("Add 5 oranges"),
                         {"intent": "ADD", "item": "oranges", "quantity": 5})
        self.assertEqual(self.parse("add two apples")["quantity"], 2)

    def test_remove_and_update(self):
        self.assertEqual(self.parse("Remove milk"), {"intent": "REMOVE", "item": "milk"})
        self.assertEqual(self.parse("take off milk"), {"intent": "REMOVE", "item": "milk"})
        self.assertEqual(self.parse("Change milk quantity to 3"),
                         {"intent": "UPDATE", "item": "milk", "quantity": 3})

    def test_search_filters(self):
        self.assertEqual(self.parse("Find toothpaste under 100"),
                         {"intent": "SEARCH", "item": "toothpaste", "max_price": 100})
        self.assertEqual(self.parse("Find products between 50 and 150"),
                         {"intent": "SEARCH", "min_price": 50, "max_price": 150})
        self.assertEqual(self.parse("Find Amul products"), {"intent": "SEARCH", "brand": "Amul"})
        self.assertEqual(self.parse("Find Colgate toothpaste"),
                         {"intent": "SEARCH", "item": "toothpaste", "brand": "Colgate"})

    def test_intent_priority(self):
        self.assertEqual(self.parse("I need to remove milk")["intent"], "REMOVE")

    def test_unknown(self):
        self.assertEqual(self.parse("hello there"), {"intent": "UNKNOWN"})

    def test_hindi(self):
        self.assertEqual(self.parse("दूध जोड़ो"), {"intent": "ADD", "item": "milk"})
        self.assertEqual(self.parse("दूध हटाओ"), {"intent": "REMOVE", "item": "milk"})
        self.assertEqual(self.parse("मुझे सेब चाहिए"), {"intent": "ADD", "item": "apple"})
        self.assertEqual(self.parse("दूध खोजो"), {"intent": "SEARCH", "item": "milk"})
        self.assertEqual(self.parse("2 बोतल पानी जोड़ो"),
                         {"intent": "ADD", "item": "water", "quantity": 2, "unit": "bottles"})
        self.assertEqual(self.parse("सेब जोड़ दो"), {"intent": "ADD", "item": "apple"})
        self.assertEqual(self.parse("टूथपेस्ट 100 रुपये से कम खोजो")["max_price"], 100)


class DataTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        shutil.copytree(REAL_DATA, self.tmp, dirs_exist_ok=True)
        data_manager.DATA_DIR = Path(self.tmp)

    def tearDown(self):
        data_manager.DATA_DIR = REAL_DATA
        shutil.rmtree(self.tmp, ignore_errors=True)


class CatalogTests(DataTestCase):
    def test_search_by_price_and_brand(self):
        names = [p["name"] for p in catalog.search_products("toothpaste", max_price=100)]
        self.assertEqual(sorted(names), ["Colgate Toothpaste", "Pepsodent Toothpaste"])
        self.assertTrue(all(p["brand"] == "Amul" for p in catalog.search_products(brand="Amul")))

    def test_plural_and_tags(self):
        self.assertEqual([p["id"] for p in catalog.search_products("organic apples")], ["organic-apple"])
        self.assertIn("apple", [p["id"] for p in catalog.search_products("apples")])

    def test_resolve_item(self):
        self.assertEqual(catalog.resolve_item("water")["category"], "Beverages")
        self.assertFalse(catalog.resolve_item("milk")["specific"])
        self.assertEqual(catalog.resolve_item("milk", brand="Amul")["product"]["id"], "amul-milk")
        self.assertEqual(catalog.resolve_item("tomato sauce")["product"]["id"], "tomato-sauce")
        self.assertEqual(catalog.resolve_item("zzz")["category"], "Other")


class SubstituteTests(DataTestCase):
    def test_amul_milk(self):
        info = substitutes.get_substitutes("amul-milk")
        self.assertFalse(info["available"])
        ids = [s["id"] for s in info["substitutes"]]
        self.assertEqual(ids[:3], ["mother-dairy-milk", "almond-milk", "soy-milk"])

    def test_preference(self):
        ids = [s["id"] for s in substitutes.get_substitutes("amul-milk", "dairy-free")["substitutes"]]
        self.assertEqual(sorted(ids), ["almond-milk", "soy-milk"])
        self.assertIsNone(substitutes.get_substitutes("nope"))


class RecommendationTests(DataTestCase):
    def test_sample_data(self):
        recs = recommendations.get_recommendations()["recommendations"]
        names = [r["name"] for r in recs]
        self.assertEqual(len(names), len(set(names)))              # no duplicates
        self.assertIn("Tomato Sauce", names)                       # pasta in history
        self.assertIn("Bread", names)                              # milk on the list
        self.assertTrue(all(r["reason"] for r in recs))
        toothpaste = [r for r in recs if "Toothpaste" in r["name"]]
        self.assertTrue(toothpaste and toothpaste[0]["brand"] != "Colgate")

    def test_skips_items_on_list(self):
        commands.add_item(name="bread")
        names = [r["name"] for r in recommendations.get_recommendations()["recommendations"]]
        self.assertNotIn("Bread", names)


class CommandTests(DataTestCase):
    def test_add_remove_update_flow(self):
        r = commands.execute_command("Add 2 bottles of water")
        self.assertTrue(r["success"])
        self.assertEqual(r["message"], "Added 2 bottles of water to your shopping list.")
        self.assertEqual(sum(1 for i in data_manager.get_shopping_list() if i["name"] == "Water"), 1)
        r = commands.execute_command("Change milk quantity to 3")
        self.assertTrue(r["success"])
        self.assertEqual(_qty("Milk"), 3)
        r = commands.execute_command("Remove milk")
        self.assertTrue(r["success"])
        self.assertIsNone(next((i for i in data_manager.get_shopping_list() if i["name"] == "Milk"), None))
        self.assertFalse(commands.execute_command("Remove unicorn")["success"])

    def test_category_and_merge(self):
        commands.execute_command("add bananas")
        commands.execute_command("add 2 bananas")
        bananas = [i for i in data_manager.get_shopping_list() if "anana" in i["name"]]
        self.assertEqual(len(bananas), 1)
        self.assertEqual(bananas[0]["quantity"], 3)
        self.assertEqual(bananas[0]["category"], "Fruits")

    def test_unavailable_product(self):
        r = commands.execute_command("add Amul milk")
        self.assertFalse(r["success"])
        self.assertIn("unavailable", r["message"])
        self.assertEqual(r["substitutes"][0]["id"], "mother-dairy-milk")

    def test_search_command(self):
        r = commands.execute_command("Find toothpaste under 100")
        self.assertTrue(r["success"])
        self.assertEqual(r["count"], 2)
        r = commands.execute_command("Find Amul milk")
        self.assertEqual(r["products"][0]["name"], "Amul Milk")
        self.assertTrue(r["products"][0]["substitutes"])

    def test_unknown_command(self):
        r = commands.execute_command("blah blah")
        self.assertFalse(r["success"])
        self.assertFalse(r["understood"])
        self.assertIn("didn't understand", r["message"])

    def test_purchase_writes_history(self):
        before = len(data_manager.get_history())
        commands.purchase_item("sample-milk")
        self.assertEqual(len(data_manager.get_history()), before + 1)
        with self.assertRaises(commands.ShoppingError):
            commands.purchase_item("sample-milk")

    def test_hindi_command(self):
        r = commands.execute_command("केला जोड़ो")
        self.assertTrue(r["success"])
        self.assertEqual(r["language"], "hi")

    def test_missing_files_are_recreated(self):
        (Path(self.tmp) / "shopping_list.json").unlink()
        self.assertEqual(data_manager.get_shopping_list(), [])


def _qty(name):
    return next(i["quantity"] for i in data_manager.get_shopping_list() if i["name"] == name)


if __name__ == "__main__":
    unittest.main()
