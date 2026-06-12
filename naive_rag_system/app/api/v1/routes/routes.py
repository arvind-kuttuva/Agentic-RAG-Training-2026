from fastapi import APIRouter, UploadFile, File, HTTPException
import shutil
import os

from pydantic import BaseModel
from langchain.messages import HumanMessage, AIMessage

from app.ingestion.ingestion import ingest_pdf
from app.retrieval.retrieval_openai import query_documents, wealth_assistant

router = APIRouter(
    prefix = "/api/v1"
) #groups all api's and attaches it to the app/webserver in main.py

UPLOAD_DIR = "uploaded_files" # same as ./uploaded_files
os.makedirs(UPLOAD_DIR, exist_ok=True) #create the folder if it did not exist


@router.post("/upload") #defines a http post api
async def upload_file(file: UploadFile = File(...)): #when api/endpoint is called execute this fn. async for better i/o
#File(..) same as multipart/form data post request
    try:
        file_path = os.path.join(UPLOAD_DIR, file.filename)

        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code = 400,
                detail = "upload only pdf files"
            )

        # Save uploaded file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer) #file.file is the original file. Copy it to buffer and then save it to file_path

        # Call service
        result = ingest_pdf(file_path)

        return {
            "status": "success",
            "filename": file.filename,
            "detail": result
        }

    except Exception as e:
        raise HTTPException(status_code = 500, detail = str(e))

# Request schema
class ChatRequest(BaseModel):
    query: str


@router.post("/chat")
def chat_endpoint(request: ChatRequest):
    try:       
        results = wealth_assistant(request.query)
        
        # print(f"back to routes {results}")
        return {"results": results}
        
    except Exception as e:
        return {"response": f"Error: {str(e)}"}