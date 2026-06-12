from pydantic import BaseModel

class ProductCreate(BaseModel):
    id: int
    name: str
    price: int

class ProductResponse(ProductCreate):
    id: int
    name: str
    price: int

    class Config:
        orm_mode = True