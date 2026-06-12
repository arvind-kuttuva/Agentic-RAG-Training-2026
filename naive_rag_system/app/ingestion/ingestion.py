

from dotenv import load_dotenv
import os
from langchain_community.document_loaders import PyPDFLoader, PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.core.db import get_vector_store
from langchain_core.documents import Document

load_dotenv()
PG_CONNECTION = os.getenv("PG_CONNECTION_STRING")



def add_texts_with_retry(
    vector_store,
    texts,
    metadatas,
    ids,
    max_retries=3,
    retry_delay=2
):
    """
    Retry wrapper for vector_store.add_texts()
    """

    for attempt in range(1, max_retries + 1):

        try:
            vector_store.add_texts(
                texts=texts,
                metadatas=metadatas,
                ids=ids
            )

            # time.sleep(2)
            print(f"Batch inserted successfully")
            return True

        except Exception as e:

            print(
                f"Insert failed "
                f"(Attempt {attempt}/{max_retries})"
            )

            print(f"Error: {str(e)}")

            if attempt < max_retries:

                sleep_time = retry_delay * attempt

                print(
                    f"Retrying in {sleep_time} seconds..."
                )

                time.sleep(sleep_time)

            else:
                print("Max retries exceeded.")
                return False
     

def ingest_pdf(file_path):
   print("Ingestion Started")


   #1. Load PDF
   loader = PyMuPDFLoader(file_path)
   docs = loader.load()
   print("Pages : ", len(docs))



   # 2. Metadata enrichment
   for doc in docs:
       content = doc.page_content

       question_id = extract_question_id(content)
       doc.metadata.update({
           "source": file_path,
           "document_extension": "pdf",
           "page": int(doc.metadata.get("page"))+1,
           "last_updated": os.path.getmtime(file_path)          
       })


   # 3. Chunking
   splitter = RecursiveCharacterTextSplitter(
       chunk_size=1000, # characters
       chunk_overlap=200, # characters
    #    separators=[
    #         "\n## ",
    #         "\n### ",
    #         "\n\n",
    #         "\n",
    #         ". ",
    #         " ",
    #         ""
    #    ]
   )


   chunks = splitter.split_documents(docs)
   print("Total Chunks", len(chunks))


   # 4 and 5
   # generate the embeddings store in vector db
   vector_store = get_vector_store(collection_name="hr_support_desk", pre_delete_collection=True)


   vector_store.add_documents(chunks)

   # FIXME: I am running a  for loop to add documents with ids. but it should ideally work with batch add_documents.
#    for i, chunk in enumerate(chunks):
#         vector_store.add_documents([chunk], ids=[f"{chunk.metadata['source']}_{chunk.metadata['page']}_{i}"])

#    batch_size = 10
#    successful_batches = 0
#    failed_batches = 0
#    import uuid

#    for start in range(0, len(chunks), batch_size):
#         batch_chunks = chunks[start:start + batch_size]
#         # print(f"batch_chunks: {batch_chunks}")

        # batch_ids = [
        #     f"{chunk.metadata['source']}_p{chunk.metadata.get('page','na')}_chunk_{start + i}"
        #     for i, chunk in enumerate(batch_chunks)
        # ]

        # batch_ids = str(uuid.uuid4()) 

        # print("batch ids", batch_ids)
    #     texts = [chunk.page_content for chunk in batch_chunks]
    #     metadatas = [{
    #         **chunk.metadata,
    #         "chunk_index": start + i
    #         }
    #         for i, chunk in enumerate(batch_chunks)
    #     ]

    #     batch_ids = [
    #     f"{chunk.metadata.get('source', 'doc')}"
    #     f"_p{chunk.metadata.get('page', 'na')}"
    #     f"_chunk_{start + i}"
    #     for i, chunk in enumerate(batch_chunks)
    # ]

    #     print(
    #         f"Inserting batch "
    #         f"{start} -> {start + len(batch_chunks)}"
    #     )

    #     print(f"Batch Size: {len(texts)}")
        
        # docs_to_add = [
        #     Document(
        #         page_content=chunk.page_content,
        #         metadata=chunk.metadata
        #     )
        #     for chunk in batch_chunks
        # ]

        # print(f"Inserting batch starting at {start}")
        # print(f"Batch size: {len(texts)}")
        # print(texts)

        # vector_store.add_texts(
        #     texts=texts,
        #     metadatas=metadatas,
        #     ids=batch_ids
        # )
        # time.sleep(3)
        # vector_store.add_documents(
        #     documents=docs_to_add,
        #     ids=batch_ids
        # )

#         success = add_texts_with_retry(
#             vector_store=vector_store,
#             texts=texts,
#             metadatas=metadatas,
#             ids=batch_ids,
#             max_retries=3,
#             retry_delay=2
#         )

#         if success:
#             successful_batches += 1
#         else:
#             failed_batches += 1

#    print("\n====== INGESTION SUMMARY ======")

#    print(f"Successful Batches: {successful_batches}")
#    print(f"Failed Batches: {failed_batches}")

               

   print("======Ingestion Completed Successfully!=======")


if __name__ == "__main__":
   #ingest_pdf("data/HR_Support_Desk_KnowledgeBase.pdf")
#    ingest_pdf("data/Capstone_Project_2_Personalized_Retail_Banking_FAQ.pdf")
    ingest_pdf("data/test.txt")
