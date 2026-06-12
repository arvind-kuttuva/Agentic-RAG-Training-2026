from fastapi import FastAPI
from app.api.v1.routes.routes import router

app = FastAPI() #starts web server

app.include_router(router) #plug in api routes defined in routes.py. The routes can be defined here in main.py also but it makes it messy

# def main():
#     print("Hello from naive-rag-system!")


# if __name__ == "__main__":
#     main()
