
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from app.db import models
from app.db.database import SessionLocal, engine
from app.routes.products_routes import router as products_router

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

@app.get("/")
def root():
    return "the app is running"

@app.get("/api/v1/hello")
def read_root():
        return {"Hello":"world"}

app.include_router(products_router)
