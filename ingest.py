import os
import shutil
import stat
from git import Repo
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_core.documents import Document # <-- NEW: Import for creating default doc
from langchain_text_splitters import (
    RecursiveCharacterTextSplitter,
)
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone, ServerlessSpec
from config import PINECONE_API_KEY, PINECONE_INDEX_NAME, OWNER, REPO

# --- Configuration (MODIFIED) ---
# KNOWLEDGE_BASE_DIR is now used for local standards check
KNOWLEDGE_BASE_DIR = "knowledge_base" 
DEFAULT_STANDARDS_FILE = os.path.join(KNOWLEDGE_BASE_DIR, "coding_standards.md")

GITHUB_REPO_URL = f"https://github.com/{OWNER}/{REPO}.git"
LOCAL_REPO_PATH = "temp_client_repo"  # Temporary folder to clone into
GLOB_PATTERN = "**/*" # To load all files in the cloned repo

EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIMENSION = 384 # Dimension for 'all-MiniLM-L6-v2'


# --- Default Standards Content (NEW) ---
DEFAULT_STANDARDS_CONTENT = """
# Our Engineering Coding Standards

## Python
- All functions must have type hints.
- Use `black` for formatting.
- All public functions must have a docstring explaining args, returns, and raises.
- Avoid global variables. Pass state explicitly.

## General
- PRs should be small and focused.
- Always include unit tests for new logic.
- Do not commit secrets. Use .env files.
"""
# ----------------------------------------


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
    Clones repo, loads all files, adds standard docs, splits, embeds, and uploads.
    """
    
    all_documents = [] # This will hold all documents (standards + repo)

    # --- 1a. Load Standards (Local or Default) (NEW LOGIC) ---
    print("--- 1a. Loading Coding Standards Context ---")
    if os.path.exists(DEFAULT_STANDARDS_FILE):
        try:
            print(f"Found local standards file: {DEFAULT_STANDARDS_FILE}. Loading it.")
            standards_loader = TextLoader(DEFAULT_STANDARDS_FILE)
            all_documents.extend(standards_loader.load())
        except Exception as e:
            print(f"WARNING: Could not load local standards file. Using default. Error: {e}")
            all_documents.append(Document(page_content=DEFAULT_STANDARDS_CONTENT, metadata={"source": "DEFAULT_CODING_STANDARDS"}))
    else:
        print("Local standards file not found. Using default internal standards.")
        all_documents.append(Document(page_content=DEFAULT_STANDARDS_CONTENT, metadata={"source": "DEFAULT_CODING_STANDARDS"}))


    # --- 1b. Clone the Repo ---
    print(f"\n--- 1b. Cloning Repository Context ---")
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
        # We proceed even if cloning fails, as we have the default standards loaded
    

    # --- 2. Load and Combine ALL Repo Files (MODIFIED SOURCE) ---
    # Only load repo files if the clone was successful and the folder exists
    if os.path.exists(LOCAL_REPO_PATH):
        print(f"\n--- 2. Loading All Repo Files ({GLOB_PATTERN}) ---")
        try:
            repo_loader = DirectoryLoader(
                # Source path is the cloned repo
                LOCAL_REPO_PATH, 
                glob=GLOB_PATTERN,
                loader_cls=TextLoader,
                loader_kwargs={"autodetect_encoding": True}, 
                show_progress=True,
                use_multithreading=True,
                silent_errors=True, # Skips binary files gracefully
            )
            # Load documents from the repo and extend the list
            all_documents.extend(repo_loader.load())
            # Note: The logging message changed to reflect the combination
            print(f"Loaded a total of {len(all_documents)} documents (Standards + Repo files).") 
        except Exception as e:
            print(f"Error during repository file loading phase: {e}")

    # --- 3. Split Documents ---
    if not all_documents:
        print("\nNo documents were loaded from any source. Exiting.")
        if os.path.exists(LOCAL_REPO_PATH):
            shutil.rmtree(LOCAL_REPO_PATH, onerror=on_rm_error) # Clean up
        return
        
    print("Splitting documents into chunks...")
    
    generic_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=100
    )
    all_texts = generic_splitter.split_documents(all_documents)
    print(f"Split documents into {len(all_texts)} chunks.")
    print(f"\nTotal chunks to upload: {len(all_texts)}")


    # --- 4. Load Embedding Model (UNCHANGED) ---
    print(f"\n--- 4. Uploading to Pinecone ---")
    print(f"Loading embedding model: {EMBEDDING_MODEL}...")
    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)

    # --- 5. Connect to Pinecone and Check Index (UNCHANGED) ---
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

    # --- 6. Upload to Pinecone (UNCHANGED) ---
    print(f"Uploading {len(all_texts)} chunks to Pinecone index...")
    PineconeVectorStore.from_documents(
        all_texts,
        embeddings,
        index_name=PINECONE_INDEX_NAME,
    )

    print("\nIngestion complete!")
    
    # --- 7. Clean up ---
    if os.path.exists(LOCAL_REPO_PATH):
        print(f"Deleting temporary repo folder: {LOCAL_REPO_PATH}")
        shutil.rmtree(LOCAL_REPO_PATH, onerror=on_rm_error)
    print("Done.")


if __name__ == "__main__":
    # The check now ensures all necessary ENV vars are set
    if not all([OWNER, REPO, PINECONE_API_KEY, PINECONE_INDEX_NAME]):
        print("Error: Missing required variables in .env file.")
        print("Please set OWNER, REPO, PINECONE_API_KEY, and PINECONE_INDEX_NAME")
    else:
        # Note: We do NOT check for KNOWLEDGE_BASE_DIR here, as the script handles
        # its absence gracefully by using the DEFAULT_STANDARDS_CONTENT.
        ingest_data()
