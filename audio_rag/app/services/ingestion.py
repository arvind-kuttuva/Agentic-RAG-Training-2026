from dotenv import load_dotenv
import os
from langchain_community.document_loaders import PyPDFLoader, PyMuPDFLoader, TextLoader, PythonLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.db.db import get_vector_store
from langchain_core.documents import Document
import google.genai as genai
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from mutagen.mp3 import MP3
from mutagen.id3 import ID3
from langchain_core.documents import Document

load_dotenv()
PG_CONNECTION = os.getenv("PG_CONNECTION_STRING")

# genai.configure(api_key=os.getenv("GEMINI_API_KEY"))


def extract_mp3_metadata(file_path: str) -> dict:
    try:
        audio = MP3(file_path, ID3=ID3)

        metadata = {
            "title": str(audio.get("TIT2", "")),
            "artist": str(audio.get("TPE1", "")),
            "album": str(audio.get("TALB", "")),
            "genre": str(audio.get("TCON", "")),
            "year": str(audio.get("TDRC", "")),
            "duration": int(audio.info.length),
            "type": "audio",
            "source": file_path
        }

        # Clean empty values
        return {k: v for k, v in metadata.items() if v}

    except Exception as e:
        print(f"Metadata extraction failed: {e}")
        return {
            "type": "audio",
            "source": file_path
        }


def transcribe_audio(file_path: str) -> str:
    # model = genai.GenerativeModel(os.getenv("GOOGLE_MODEL"))
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    with open(file_path, "rb") as f:
        audio_bytes = f.read()

    response = client.models.generate_content(
        model=os.getenv("GOOGLE_MODEL"),
        contents = {        
            "role": "user",
            "parts": [
                {"text": "Transcribe this audio accurately.Return only the text."},
                {
                    "inline_data": {
                        "mime_type": "audio/mpeg",
                        "data": audio_bytes
                    }
                }
            ]
        }                
    )

    return response.text

def create_docs_from_audio(text: str, file_path: str):
    return [
        Document(
            page_content=text,
            metadata={
                "source": file_path,
                "type": "audio"
            }
        )
    ]

 


def create_docs_from_audio(text: str, file_path: str):
    metadata = extract_mp3_metadata(file_path)

    # ✅ Enrich text for better embedding
    enriched_text = f"""
    Title: {metadata.get("title", "")}
    Artist: {metadata.get("artist", "")}
    Album: {metadata.get("album", "")}
    Genre: {metadata.get("genre", "")}

    Transcript:
    {text}
    """

    return [
        Document(
            page_content=enriched_text,  # ✅ use enriched content
            metadata=metadata        	# ✅ store metadata
        )
    ]
   

def chunk_docs(docs):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50
    )
    return splitter.split_documents(docs)

def get_embeddings():
    return GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-2",
        api_key=os.getenv("GEMINI_API_KEY"),
        output_dimensionality=768
    )


def ingest_audio(file_path: str):
    print("Step 1: Transcribing audio...")
    text = transcribe_audio(file_path)

    print("Step 2: Creating documents...")
    docs = create_docs_from_audio(text, file_path)

    print("Step 3: Chunking...")
    chunked_docs = chunk_docs(docs)

    print("Step 4: Store in vector DB...")
    vector_store = get_vector_store(
        collection_name=os.getenv("PG_COLLECTION_NAME"),   
        pre_delete_collection=False
    )

    vector_store.add_documents(chunked_docs)

    print("Audio ingestion complete!")




    print("======Ingestion Completed Successfully!=======")


if __name__ == "__main__":
   #ingest_pdf("data/HR_Support_Desk_KnowledgeBase.pdf")
#    ingest_pdf("data/Capstone_Project_2_Personalized_Retail_Banking_FAQ.pdf")
    ingest_pdf("data/test.txt")
