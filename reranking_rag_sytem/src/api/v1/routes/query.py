from http.client import HTTPException
import os
from fastapi import APIRouter, UploadFile, File
from fastapi.responses import StreamingResponse
from src.api.v1.services.query_service import query_documents, query_documents_stream
from src.api.v1.schema.query_schema import QueryRequest,QueryResponse
from src.core.guardrails import GuardrailViolation


router = APIRouter()




@router.post("/query")
# def query_endpoint(request: QueryRequest):
#    docs = query_documents(request.query)
#    return docs
def query_endpoint(request: QueryRequest):
   try:
      return query_documents(request.query)
   except GuardrailViolation as violation:
      # An input guardrail blocked the request - return a 400 with the reason
      raise HTTPException(
         status_code=400,
         detail={"guardrail": violation.guard, "message": violation.message}
      )
   


@router.post("/query/stream")
async def stream_query_endpoint(request: QueryRequest):
   # Endpoint that returns an SSE stream of the agents response
   try:
      generator = await query_documents_stream(request.query)
      return StreamingResponse(
      generator,
      media_type="text/event-stream"
   )
   except GuardrailViolation as violation:
      # An input guardrail blocked the request - return a 400 with the reason
      raise HTTPException(
         status_code=400,
         detail={"guardrail": violation.guard, "message": violation.message}
      )
   