from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from services.products_service import *

class Product(BaseModel):
    id: Optional[int] = None
    name: str
    price: float
    category: str
    description: Optional[str] = None

router = APIRouter(
    prefix = "/api/v1/products",
    tags = ["products"]
)

@router.get("/")
def read_products():
   return get_products()


@router.get("/{product_id}")
def read_product(product_id: int):
   return get_product_by_id(product_id)


@router.post("/")
def create_products(product: Product):
    return add_product(product)


@router.put("/{product_id}")
def update_product(product_id:int, product: Product):
    return product_update(product_id, product)
    

@router.delete("/{product_id}")
def delete_product(product_id: int):
    return delete_product_by_id(product_id)