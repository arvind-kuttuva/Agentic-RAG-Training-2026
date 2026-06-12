from sqlalchemy.orm import Session
from app.db import models
from app.schemas import ProductCreate

# def get_products():
#      # return "["prod1","prod2","prod3"]"
#     return [
#         {
#             "id":1,
#             "name": "mobile",
#             "price": 89.99
#         },
#         {
#             "id":2,
#             "name": "laptop",
#             "price": 189.99
#         }
#     ]

def get_products(db:Session):
    return db.query(models.Product).all()


#def add_product(product:dict):
    # print("Product received ", product)
    # return product
def add_product(product: ProductCreate, db:Session ):
    db_product = models.Product(
        id = product.id,
        name = product.name,
        price = product.price
    )
    db.add(db_product)
    db.commit()
    db.refresh(db_product)

    return db_product
    

def get_product_by_id(product_id:int, db:Session ):
    return db.query(models.Product).filter(models.Product.id == product_id).first()
    #  return {
    #     "id" : 1,
    #     "name": "mobile",
    #     "price": 99.99
    # }


# def product_update(product_id: int, product:dict):
#     print("updating product with ID:", product_id)
#     print("updateable product data:", product)
#     return {
#         "message": "Product updated successfully",
#         "product_id": product_id,
#         "updated_product": product
#     }
    
def product_update(product_id: int, product: ProductCreate, db:Session):    
    db_product = db.query(models.Product)\
                    .filter(models.Product.id == product_id)\
                    .first()

    if db_product:
        db_product.name = product.name
        db_product.price = product.price  
        db.commit()
        db.refresh(db_product)

    return db_product         

# def delete_product_by_id(product_id: int):
#     return {
#         "message": "Product deleted successfully",
#         "product_id": product_id
#     }

def delete_product_by_id(product_id: int, db:Session):
    db_product = db.query(models.Product)\
                    .filter(models.Product.id == product_id)\
                    .first()

    if db_product:
        db.delete(db_product)  
        db.commit()
        return {"message": "record deleted successfully"}
        

    return {"message": "record not found"}             
