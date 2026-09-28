"""Pydantic models = automatic validation of request bodies."""
from typing import Optional

from pydantic import BaseModel, Field


class CommandRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=300, description='e.g. "Add 2 bottles of water"')


class AddItemRequest(BaseModel):
    """Send either `name` (free text) or `product_id` (from the catalog)."""
    name: Optional[str] = Field(None, max_length=100)
    product_id: Optional[str] = None
    quantity: float = Field(1, gt=0, le=1000)
    unit: Optional[str] = Field(None, max_length=20)


class ItemIdRequest(BaseModel):
    item_id: str = Field(..., min_length=1)


class UpdateItemRequest(BaseModel):
    item_id: str = Field(..., min_length=1)
    quantity: Optional[float] = Field(None, gt=0, le=1000)
    unit: Optional[str] = Field(None, max_length=20)


class SearchRequest(BaseModel):
    query: str = Field("", max_length=100)
    brand: Optional[str] = None
    min_price: Optional[float] = Field(None, ge=0)
    max_price: Optional[float] = Field(None, ge=0)
    size: Optional[str] = None


class RecommendRequest(BaseModel):
    limit: int = Field(8, ge=1, le=20)
