import os
import shutil
import stat
from git import Repo
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_core.documents import Document # <-- NEW: Needed for creating documents manually
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone, ServerlessSpec
from config import PINECONE_API_KEY, PINECONE_INDEX_NAME, OWNER, REPO

# --- Configuration ---
# Local folder for standards (optional, but checked first)
KNOWLEDGE_BASE_DIR = "knowledge_base" 
DEFAULT_STANDARDS_FILE = os.path.join(KNOWLEDGE_BASE_DIR, "coding_standards.md")

GITHUB_REPO_URL = f"https://github.com/{OWNER}/{REPO}.git"
LOCAL_REPO_PATH = "temp_client_repo"  # Temporary folder to clone into

GLOB_PATTERN = "**/*" # To load all files in the cloned repo

EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIMENSION = 384  # Dimension for 'all-MiniLM-L6-v2'


# --- Default Standards Content ---
# This is the fallback if the local file does not exist
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

    # --- 1. Load Standards (Local or Default) ---
    print("--- 1. Loading Coding Standards Context ---")
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


    # --- 2. Clone the Repo ---
    print(f"\n--- 2. Cloning Repository Context ---")
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
        # If cloning fails, we still proceed with the standards we loaded
        # return # No return needed here, as we already have the default standards loaded
    
    # --- 3. Load and Combine ALL Repo Files ---
    if os.path.exists(LOCAL_REPO_PATH):
        print(f"\n--- 3. Loading All Repo Files ({GLOB_PATTERN}) ---")
        try:
            repo_loader = DirectoryLoader(
                LOCAL_REPO_PATH, 
                glob=GLOB_PATTERN,
                loader_cls=TextLoader,
                loader_kwargs={"autodetect_encoding": True},
                show_progress=True,
                use_multithreading=True,
                silent_errors=True, # Skips binary files gracefully
            )
            # Extend the documents list with the documents from the cloned repo
            all_documents.extend(repo_loader.load())
            print(f"Loaded {len(all_documents) - 1} repo files (excluding standards).") # Subtract the 1 standards doc
        except Exception as e:
            print(f"Error during repository file loading phase: {e}")

    # --- 4. Split Documents ---
    if not all_documents:
        print("\nNo documents were loaded. Exiting.")
        if os.path.exists(LOCAL_REPO_PATH):
            shutil.rmtree(LOCAL_REPO_PATH, onerror=on_rm_error) # Clean up
        return
        
    print(f"\nTotal documents to process: {len(all_documents)}")
    print("Splitting documents into chunks...")
    
    generic_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=100
    )
    all_texts = generic_splitter.split_documents(all_documents)
    print(f"Split documents into {len(all_texts)} chunks.")


    # --- 5. Load Embedding Model ---
    print(f"\n--- 5. Uploading to Pinecone ---")
    print(f"Loading embedding model: {EMBEDDING_MODEL}...")
    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)

    # --- 6. Connect to Pinecone and Check Index ---
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

    # --- 7. Upload to Pinecone ---
    print(f"Uploading {len(all_texts)} chunks to Pinecone index...")
    PineconeVectorStore.from_documents(
        all_texts,
        embeddings,
        index_name=PINECONE_INDEX_NAME,
    )

    print("\nIngestion complete!")
    
    # --- 8. Clean up ---
    if os.path.exists(LOCAL_REPO_PATH):
        print(f"Deleting temporary repo folder: {LOCAL_REPO_PATH}")
        shutil.rmtree(LOCAL_REPO_PATH, onerror=on_rm_error)
    print("Done.")


if __name__ == "__main__":
    if not all([OWNER, REPO, PINECONE_API_KEY, PINECONE_INDEX_NAME]):
        print("Error: Missing required variables in .env file.")
        print("Please set OWNER, REPO, PINECONE_API_KEY, and PINECONE_INDEX_NAME")
    else:
        ingest_data()