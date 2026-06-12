from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.services.products_service import *
from app.schemas import ProductCreate, ProductResponse

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

# @router.get("/")
# def read_products():
#    return get_products()

@router.get("/", response_model=List[ProductResponse])
def read_products(db: Session = Depends(get_db)):
    return get_products(db)


@router.get("/{product_id}")
def read_product(product_id: int,db: Session = Depends(get_db)):
   return get_product_by_id(product_id, db)


# @router.post("/")
# def create_products(product: Product):
#     return add_product(product)

@router.post("/", response_model=ProductResponse)
def create_products(product: ProductCreate, db: Session = Depends(get_db)):
    return add_product(product, db)    

# @router.put("/{product_id}")
# def update_product(product_id:int, product: Product):
#     return product_update(product_id, product)

@router.put("/{product_id}", response_model=ProductResponse)
def update_product(product_id:int, product: ProductCreate, db: Session = Depends(get_db)):
    return product_update(product_id, product, db)
    

# @router.delete("/{product_id}")
# def delete_product(product_id: int):
#     return delete_product_by_id(product_id)

@router.delete("/{product_id}")
def delete_product(product_id: int, db: Session = Depends(get_db)):
    return delete_product_by_id(product_id, db)