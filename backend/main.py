"""FastAPI application: HTTP endpoints only. The real work is in the other files.

Run from the project root:
    python -m uvicorn backend.main:app --reload
Then open http://localhost:8000
"""
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import catalog, commands, data_manager, recommendations, substitutes
from .commands import ShoppingError
from .models import (AddItemRequest, CommandRequest, ItemIdRequest,
                     RecommendRequest, SearchRequest, UpdateItemRequest)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    data_manager.ensure_data_files()      # create missing JSON files on startup
    yield


app = FastAPI(title="Voice Command Shopping Assistant", version="1.0.0", lifespan=lifespan)

# Allow the frontend to call the API even if it is opened from another port/file.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(ShoppingError)
async def shopping_error_handler(request, error: ShoppingError):
    """Turn ShoppingError into a JSON error with the right HTTP status."""
    return JSONResponse(status_code=error.status_code,
                        content={"detail": error.message, **error.extra})


# ------------------------------------------------------------------ pages
@app.get("/", include_in_schema=False)
def home():
    index = FRONTEND_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"name": app.title, "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "ok", "name": app.title}


# --------------------------------------------------------------- products
@app.get("/products")
def list_products(category: Optional[str] = None, brand: Optional[str] = None,
                  q: Optional[str] = None):
    if q or brand:
        products = catalog.search_products(q or "", brand=brand)
    else:
        products = data_manager.get_products()
    if category:
        products = [p for p in products if p["category"].lower() == category.lower()]
    return products


@app.get("/products/{product_id}")
def get_product(product_id: str):
    product = data_manager.get_product(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail=f"Product '{product_id}' not found.")
    return product


# ---------------------------------------------------------- shopping list
@app.get("/shopping-list")
def get_shopping_list():
    return data_manager.get_shopping_list()


@app.post("/shopping-list/add", status_code=201)
def add_to_shopping_list(request: AddItemRequest):
    if not request.name and not request.product_id:
        raise HTTPException(status_code=422, detail="Send either 'name' or 'product_id'.")
    return commands.add_item(request.name, request.quantity, request.unit,
                             product_id=request.product_id)


@app.post("/shopping-list/remove")
def remove_from_shopping_list(request: ItemIdRequest):
    return commands.remove_item_by_id(request.item_id)


@app.post("/shopping-list/update")
def update_shopping_list_item(request: UpdateItemRequest):
    return commands.update_item(request.item_id, request.quantity, request.unit)


@app.post("/shopping-list/clear-purchased")
def clear_purchased():
    return {"removed": data_manager.clear_purchased()}


# --------------------------------------------------------------- commands
@app.post("/command")
def command(request: CommandRequest):
    """Natural language in, action out. Always answers 200 with a `success` flag."""
    return commands.execute_command(request.text)


# ------------------------------------------------- search / recommendations
@app.post("/search")
def search_products(request: SearchRequest):
    return commands.search(request.query, request.brand, request.min_price,
                           request.max_price, request.size)


@app.post("/recommend")
def recommend(request: Optional[RecommendRequest] = None):
    limit = request.limit if request else 8
    return recommendations.get_recommendations(limit)


@app.post("/purchase")
def purchase(request: ItemIdRequest):
    return commands.purchase_item(request.item_id)


@app.get("/history")
def history():
    return data_manager.get_history()


@app.get("/substitutes/{product_id}")
def get_substitutes(product_id: str, preference: Optional[str] = Query(
        None, description="dairy-free, vegan, organic, plant-based or cheaper")):
    result = substitutes.get_substitutes(product_id, preference)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Product '{product_id}' not found.")
    return result


# Static files for the frontend (css/ and js/ folders).
if FRONTEND_DIR.exists():
    app.mount("/css", StaticFiles(directory=FRONTEND_DIR / "css"), name="css")
    app.mount("/js", StaticFiles(directory=FRONTEND_DIR / "js"), name="js")
