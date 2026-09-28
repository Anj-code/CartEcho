# Voice Command Shopping Assistant

A beginner-friendly practice project: talk to a shopping list in **English or Hindi**.
Plain HTML/CSS/JavaScript in the browser, **Python + FastAPI** on the server, **JSON files** for storage.
No database, no AI service, no machine learning: the language understanding and the
recommendations are simple, readable rules.

live - https://cartecho.onrender.com

## Quick start (VS Code)

1. Install **Python 3.9+** and open this folder in VS Code.
2. Open a terminal (`Ctrl+` `` ` ``) and create a virtual environment:

   ```bash
   python -m venv .venv
   # Windows PowerShell:  .venv\Scripts\Activate.ps1
   # Windows cmd:         .venv\Scripts\activate.bat
   # macOS / Linux:       source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. Start the server from the project root:

   ```bash
   python -m uvicorn backend.main:app --reload
   ```
4. Open **http://localhost:8000** in **Chrome or Edge**. FastAPI also serves the frontend, so there is nothing else to run.
   Interactive API docs are at http://localhost:8000/docs.

Sample data is included, so the list, search, recommendations and substitutes all work immediately.

Run the tests (no server needed):

```bash
python -m unittest discover -s tests -v
```

## Browser support for voice

Voice uses the browser's built-in **Web Speech API (`SpeechRecognition`)**.

| Browser | Voice input |
|---|---|
| Chrome, Edge (desktop and Android) | Works. Needs internet, because the browser sends audio to its own speech service. |
| Safari | Partial and version dependent. |
| Firefox | Not supported. |

* The page must be served from `localhost` or `https` for the microphone to be allowed. Use http://localhost:8000 rather than double-clicking `index.html`.
* If the microphone is blocked you'll see "Microphone permission is required for voice commands." Allow it from the padlock icon in the address bar.
* Unsupported browser? The mic button is disabled with a message, but everything else still works: use the **typed command box**, the **example chips**, or the normal buttons.
* Hindi recognition quality depends on the browser and your accent. Pick **हिन्दी (Hindi)** in the language box first; it switches the recognition language to `hi-IN`.

## What you can say

| Intent | English examples |
|---|---|
| **ADD** | "Add milk", "I need apples", "I want to buy bananas", "Buy 2 bottles of water", "Get 5 oranges", "Please add bananas to my shopping list" |
| **REMOVE** | "Remove milk", "Delete milk", "Take off milk" |
| **UPDATE** | "Change milk quantity to 3", "Update milk to 2 bottles", "Set apples to 6" |
| **SEARCH** | "Find apples", "Find organic apples", "Find Colgate toothpaste", "Find Amul products", "Find toothpaste under 100", "Find toothpaste below 100", "Find products between 50 and 150", "Show me Amul milk" |

The parser pulls out: **intent, item, quantity, unit, brand, min/max price, size**. Example:

```json
{"intent": "ADD", "item": "water", "quantity": 2, "unit": "bottles"}
```

### Hindi command patterns

Hindi puts the verb at the end. Both Devanagari and a few Latin (romanised) spellings work.

| Meaning | Words recognised | Example |
|---|---|---|
| Add | जोड़ो, जोड़ दो, डालो, ऐड करो | दूध जोड़ो, सेब जोड़ दो |
| Buy | खरीदो, खरीदना है, लाओ, लेना है | केला खरीदना है |
| Need / want | चाहिए, चाहता हूं | मुझे सेब चाहिए |
| Remove | हटाओ, हटा दो, निकालो, मिटाओ | दूध हटाओ |
| Update | बदलो, अपडेट, मात्रा ... करो | दूध की मात्रा 3 करो |
| Find / search | खोजो, ढूंढो, दिखाओ | दूध खोजो, अमूल दूध खोजो |
| Quantity + unit | बोतल, पैकेट, किलो, ग्राम, लीटर, दर्जन | 2 बोतल पानी जोड़ो, 2 किलो आलू जोड़ो |
| Price | से कम, के अंदर (under), से ज्यादा (over), ... के बीच (between) | टूथपेस्ट 100 रुपये से कम खोजो |

Hindi product words (दूध, सेब, केला, आम, संतरा, अंगूर, भिंडी, करेला, गाजर, आलू, टमाटर, कटहल, ब्रेड, मक्खन, चावल, चीनी, नमक, चाय, कॉफी, पानी, टूथपेस्ट ...) are translated to English catalog names by a small dictionary in `backend/nlp.py` (`HI_WORDS`). Romanised: `doodh jodo`, `seb chahiye`, `doodh hatao`, `doodh khojo`.

To teach it a new word, add one line to `HI_WORDS`. To add a new verb, add it to `ADD_WORDS`, `REMOVE_WORDS`, and so on.

## How it works

```
Microphone -> browser SpeechRecognition -> text
   -> POST /command {"text": "..."}
        nlp.py           text -> {intent, item, quantity, ...}
        commands.py      does the action (add/remove/update/search)
        catalog.py       finds products, decides category
        data_manager.py  reads/writes the JSON files
   <- {"success": true, "message": "Added ...", ...}
```

### Project layout

```
voice-shopping-assistant/
├── backend/
│   ├── main.py             FastAPI routes only (thin)
│   ├── models.py           Pydantic request models (validation)
│   ├── nlp.py              rule-based command parser (English + Hindi)
│   ├── commands.py         actions behind both /command and the buttons
│   ├── catalog.py          product search + item resolution
│   ├── recommendations.py  rule-based recommendations
│   ├── substitutes.py      alternatives for unavailable products
│   ├── data_manager.py     JSON read/write (pathlib, auto-creates files)
│   ├── text_utils.py       tiny helpers (plural -> singular, ...)
│   └── data/               products.json, shopping_list.json,
│                           shopping_history.json, recommendation_rules.json
├── frontend/
│   ├── index.html
│   ├── css/style.css
│   └── js/  app.js  voice.js  shopping-list.js  search.js  recommendations.js
├── tests/test_logic.py
├── requirements.txt  README.md  .gitignore
```

### Rule-based recommendations (no ML)

`recommendation_rules.json` maps an item to things that go with it:

```json
{ "milk": [ {"product": "bread", "reason": "Often bought together with milk"} ] }
```

`recommendations.py` then:

1. collects **trigger items**: everything in `shopping_history.json` (newest first) plus items currently on the list,
2. matches each trigger against the rule keys ("Amul Milk" matches the `milk` rule),
3. skips rules whose product is **already on your list**,
4. finds a real, **available** product in `products.json`,
5. removes duplicates and returns each product with its **reason**.

Click **Mark purchased** on a list item and it is appended to `shopping_history.json`, which changes future recommendations. The `toothpaste` rule has `"prefer_other_brand": true`, so after buying Colgate it suggests another brand.

### Substitutes

Amul Milk and Kurkure are unavailable in the sample data. Search "Find Amul milk" or say "add Kurkure" to see alternatives. `substitutes.py` uses (1) `substitute_ids` from `products.json`, (2) other available products of the same type, and it accepts a preference: `GET /substitutes/amul-milk?preference=dairy-free` (also `vegan`, `organic`, `plant-based`, `cheaper`).

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | the web app |
| GET | `/products`, `/products/{id}` | catalog (`?category=`, `?brand=`, `?q=`) |
| GET | `/shopping-list` | current list |
| POST | `/command` | `{"text": "Add 2 bottles of water"}` |
| POST | `/shopping-list/add` | `{"name": "rice", "quantity": 2}` or `{"product_id": "rice"}` |
| POST | `/shopping-list/remove` | `{"item_id": "..."}` |
| POST | `/shopping-list/update` | `{"item_id": "...", "quantity": 3, "unit": "bottles"}` |
| POST | `/shopping-list/clear-purchased` | remove purchased items |
| POST | `/search` | `{"query": "toothpaste", "brand": null, "min_price": 0, "max_price": 100}` |
| POST | `/recommend` | recommendations (optional `{"limit": 8}`) |
| POST | `/purchase` | `{"item_id": "..."}` -> marks purchased, writes history |
| GET | `/history` | purchase history |
| GET | `/substitutes/{product_id}` | alternatives (`?preference=`) |

Status codes: `201` created, `400` bad input, `404` not found, `409` conflict (unavailable product, already purchased), `422` validation error.
`/command` always answers `200` with `"success": true/false`, because "I didn't understand" is a normal outcome for speech.

## Data

All state is in `backend/data/*.json`. Missing or corrupt files are recreated automatically. To reset the sample data, delete `shopping_list.json` and `shopping_history.json` (you'll get empty ones), or restore them from a copy of this project.

## Known limits (good next exercises)

* One item per sentence: "add milk and bread" is not split into two items.
* Number words work up to twenty ("add two apples"); bigger spoken numbers should be said as digits.
* Search matches words, not spelling mistakes. A fuzzy matcher (`difflib`) would be a nice upgrade.
* No users or login: there is one shared list.
* Ideas to try: more Hindi words, a "clear list" command, category grouping in the list, more recommendation rules.
