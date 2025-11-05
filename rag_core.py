import os
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_pinecone import PineconeVectorStore      # <-- NEW
from langchain_core.retrievers import BaseRetriever
from config import PINECONE_INDEX_NAME              # <-- NEW

# --- Configuration ---
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# --- Cached Globals ---
_embeddings = None
_vector_store = None
_retriever = None

def _get_embeddings():
    """Loads and caches the embedding model."""
    global _embeddings
    if _embeddings is None:
        print("Loading embedding model...")
        _embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
    return _embeddings

def _get_vector_store():
    """Loads and caches the Pinecone vector store."""
    global _vector_store
    if _vector_store is None:
        print(f"Connecting to Pinecone index: '{PINECONE_INDEX_NAME}'...")
        embeddings = _get_embeddings()
        _vector_store = PineconeVectorStore.from_existing_index(
            index_name=PINECONE_INDEX_NAME,
            embedding=embeddings
        )
    return _vector_store

def get_retriever(k_value: int = 4) -> BaseRetriever:
    """
    Initializes and returns a cached vector store retriever.
    """
    global _retriever
    if _retriever is None:
        vector_store = _get_vector_store()
        _retriever = vector_store.as_retriever(search_kwargs={"k": k_value})
        print("Retriever initialized from Pinecone.")
    return _retriever

if __name__ == "__main__":
    # A simple test to check if the retriever works
    try:
        retriever = get_retriever()
        print("\nRetriever test:")
        test_query = "python type hints"
        docs = retriever.invoke(test_query)
        print(f"Query: '{test_query}'")
        print(f"Found {len(docs)} relevant chunks:")
        for i, doc in enumerate(docs):
            print(f"--- Doc {i+1} (Source: {doc.metadata.get('source', 'N/A')}) ---")
            print(doc.page_content[:200] + "...")
    except Exception as e:
        print(f"\nTest failed: {e}")
