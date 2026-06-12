import os
from dotenv import load_dotenv
from langchain_postgres import PGVector
# from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_openai import OpenAIEmbeddings


load_dotenv()


PG_CONNECTION = os.getenv("PG_CONNECTION_STRING")


def get_embeddings():
#    return GoogleGenerativeAIEmbeddings(
#        model=os.getenv("GOOGLE_EMBEDDING_MODEL"),
#        api_key=os.getenv("GEMINI_API_KEY"),
#        output_dimensionality=1536
#    )
   return OpenAIEmbeddings(
       model=os.getenv("OPENAI_EMBEDDING_MODEL")       
   )

def get_vector_store(collection_name: str = "hr_support_desk", pre_delete_collection: bool = False):
   return PGVector(
       collection_name=collection_name,
       connection=PG_CONNECTION,
       embeddings=get_embeddings(),
       use_jsonb=True,
       pre_delete_collection=pre_delete_collection        
   )
