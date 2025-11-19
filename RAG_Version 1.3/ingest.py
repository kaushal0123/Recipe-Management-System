import os
import shutil
import stat
from git import Repo
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import (
    RecursiveCharacterTextSplitter,
)
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone, ServerlessSpec
from config import PINECONE_API_KEY, PINECONE_INDEX_NAME, OWNER, REPO

# --- Configuration ---
GITHUB_REPO_URL = f"https://github.com/{OWNER}/{REPO}.git"
LOCAL_REPO_PATH = "temp_client_repo"  # Temporary folder to clone into

# Load all file types
GLOB_PATTERN = "**/*"  

EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIMENSION = 384  # Dimension for 'all-MiniLM-L6-v2'


# --- Helper function to handle read-only file errors on Windows ---
def on_rm_error(func, path, exc_info):
    """
    Error handler for shutil.rmtree.
    If a file is read-only, it makes it writable and tries to delete again.
    """
    if not os.access(path, os.W_OK):
        os.chmod(path, stat.S_IWRITE)
        func(path)
    else:
        raise
# ---------------------------------------------------------------------


def ingest_data():
    """
    Clones repo, loads all files, splits, embeds, and uploads.
    """
    
    # --- 1. Clone the Repo ---
    print(f"Cloning repository {GITHUB_REPO_URL} to {LOCAL_REPO_PATH}...")
    if os.path.exists(LOCAL_REPO_PATH):
        print("Deleting old temporary repo folder...")
        shutil.rmtree(LOCAL_REPO_PATH, onerror=on_rm_error)
        
    try:
        Repo.clone_from(GITHUB_REPO_URL, LOCAL_REPO_PATH)
        print("Repo cloned successfully.")
    except Exception as e:
        print(f"FAILED to clone repo: {e}")
        print("Please ensure OWNER and REPO are correct in your .env file.")
        return

    all_texts = [] # This will hold all chunks

    # --- 2. Load and Split ALL Repo Files ---
    print(f"\n--- Loading All Repo Files ({GLOB_PATTERN}) ---")
    try:
        loader = DirectoryLoader(
            LOCAL_REPO_PATH,
            glob=GLOB_PATTERN,
            loader_cls=TextLoader,
            loader_kwargs={"autodetect_encoding": True},
            show_progress=True,
            use_multithreading=True,
            silent_errors=True, # Skips binary files like images
        )
        documents = loader.load()
        
        if documents:
            print(f"Loaded {len(documents)} text-based files.")
            print("Splitting all documents...")
            
            generic_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=100
            )
            all_texts = generic_splitter.split_documents(documents)
            print(f"Split documents into {len(all_texts)} chunks.")
        else:
            print("No text files were successfully loaded.")
            
    except Exception as e:
        print(f"Error during file loading phase: {e}")


    # --- 3. Check if we have anything to upload ---
    if not all_texts:
        print("\nNo documents were loaded from the repository. Exiting.")
        shutil.rmtree(LOCAL_REPO_PATH, onerror=on_rm_error) # Clean up
        return
        
    print(f"\nTotal chunks to upload: {len(all_texts)}")

    # --- 4. Load Embedding Model ---
    print(f"Loading embedding model: {EMBEDDING_MODEL}...")
    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)

    # --- 5. Connect to Pinecone and Check Index ---
    print("Initializing Pinecone client...")
    pc = Pinecone(api_key=PINECONE_API_KEY)

    if PINECONE_INDEX_NAME not in pc.list_indexes().names():
        print(f"Index '{PINECONE_INDEX_NAME}' not found. Creating new index...")
        pc.create_index(
            name=PINECONE_INDEX_NAME,
            dimension=EMBEDDING_DIMENSION,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
        print("Index created.")
    else:
        print(f"Found existing index '{PINECONE_INDEX_NAME}'.")

    # --- 6. Upload to Pinecone ---
    print(f"Uploading {len(all_texts)} chunks to Pinecone index...")
    PineconeVectorStore.from_documents(
        all_texts,
        embeddings,
        index_name=PINECONE_INDEX_NAME,
    )

    print("\nIngestion complete!")
    
    # --- 7. Clean up ---
    print(f"Deleting temporary repo folder: {LOCAL_REPO_PATH}")
    shutil.rmtree(LOCAL_REPO_PATH, onerror=on_rm_error)
    print("Done.")


if __name__ == "__main__":
    if not all([OWNER, REPO, PINECONE_API_KEY, PINECONE_INDEX_NAME]):
        print("Error: Missing required variables in .env file.")
        print("Please set OWNER, REPO, PINECONE_API_KEY, and PINECONE_INDEX_NAME")
    else:
        ingest_data()
