from fastapi import FastAPI
from src.api.v1.routes.routes import router

app = FastAPI() #starts web server

app.include_router(router) #plug in api routes defined in routes.py. The routes can be defined here in main.py also but it makes it


#uv add fastapi uvicorn python-dotenv docling langchain-postgres langchain-openai langgraph langchain python-multipart
# uv run uvicorn src.main:app --reload
# uv run streamlit run src\api\v1\ui\upload_ui.py