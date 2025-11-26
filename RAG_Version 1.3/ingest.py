# import os
# import shutil
# import stat
# from git import Repo
# from langchain_community.document_loaders import DirectoryLoader, TextLoader
# from langchain_text_splitters import (
#     RecursiveCharacterTextSplitter,
# )
# from langchain_huggingface import HuggingFaceEmbeddings
# from langchain_pinecone import PineconeVectorStore
# from pinecone import Pinecone, ServerlessSpec
# from config import PINECONE_API_KEY, PINECONE_INDEX_NAME, OWNER, REPO

# # --- Configuration ---
# GITHUB_REPO_URL = f"https://github.com/{OWNER}/{REPO}.git"
# LOCAL_REPO_PATH = "temp_client_repo"  # Temporary folder to clone into

# # Load all file types
# GLOB_PATTERN = "**/*"  

# EMBEDDING_MODEL = "all-MiniLM-L6-v2"
# EMBEDDING_DIMENSION = 384  # Dimension for 'all-MiniLM-L6-v2'


# # --- Helper function to handle read-only file errors on Windows ---
# def on_rm_error(func, path, exc_info):
#     """
#     Error handler for shutil.rmtree.
#     If a file is read-only, it makes it writable and tries to delete again.
#     """
#     if not os.access(path, os.W_OK):
#         os.chmod(path, stat.S_IWRITE)
#         func(path)
#     else:
#         raise
# # ---------------------------------------------------------------------


# def ingest_data():
#     """
#     Clones repo, loads all files, splits, embeds, and uploads.
#     """
    
#     # --- 1. Clone the Repo ---
#     print(f"Cloning repository {GITHUB_REPO_URL} to {LOCAL_REPO_PATH}...")
#     if os.path.exists(LOCAL_REPO_PATH):
#         print("Deleting old temporary repo folder...")
#         shutil.rmtree(LOCAL_REPO_PATH, onerror=on_rm_error)
        
#     try:
#         Repo.clone_from(GITHUB_REPO_URL, LOCAL_REPO_PATH)
#         print("Repo cloned successfully.")
#     except Exception as e:
#         print(f"FAILED to clone repo: {e}")
#         print("Please ensure OWNER and REPO are correct in your .env file.")
#         return

#     all_texts = [] # This will hold all chunks

#     # --- 2. Load and Split ALL Repo Files ---
#     print(f"\n--- Loading All Repo Files ({GLOB_PATTERN}) ---")
#     try:
#         loader = DirectoryLoader(
#             LOCAL_REPO_PATH,
#             glob=GLOB_PATTERN,
#             loader_cls=TextLoader,
#             loader_kwargs={"autodetect_encoding": True},
#             show_progress=True,
#             use_multithreading=True,
#             silent_errors=True, # Skips binary files like images
#         )
#         documents = loader.load()
        
#         if documents:
#             print(f"Loaded {len(documents)} text-based files.")
#             print("Splitting all documents...")
            
#             generic_splitter = RecursiveCharacterTextSplitter(
#                 chunk_size=1000,
#                 chunk_overlap=100
#             )
#             all_texts = generic_splitter.split_documents(documents)
#             print(f"Split documents into {len(all_texts)} chunks.")
#         else:
#             print("No text files were successfully loaded.")
            
#     except Exception as e:
#         print(f"Error during file loading phase: {e}")


#     # --- 3. Check if we have anything to upload ---
#     if not all_texts:
#         print("\nNo documents were loaded from the repository. Exiting.")
#         shutil.rmtree(LOCAL_REPO_PATH, onerror=on_rm_error) # Clean up
#         return
        
#     print(f"\nTotal chunks to upload: {len(all_texts)}")

#     # --- 4. Load Embedding Model ---
#     print(f"Loading embedding model: {EMBEDDING_MODEL}...")
#     embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)

#     # --- 5. Connect to Pinecone and Check Index ---
#     print("Initializing Pinecone client...")
#     pc = Pinecone(api_key=PINECONE_API_KEY)

#     if PINECONE_INDEX_NAME not in pc.list_indexes().names():
#         print(f"Index '{PINECONE_INDEX_NAME}' not found. Creating new index...")
#         pc.create_index(
#             name=PINECONE_INDEX_NAME,
#             dimension=EMBEDDING_DIMENSION,
#             metric="cosine",
#             spec=ServerlessSpec(cloud="aws", region="us-east-1"),
#         )
#         print("Index created.")
#     else:
#         print(f"Found existing index '{PINECONE_INDEX_NAME}'.")

#     # --- 6. Upload to Pinecone ---
#     print(f"Uploading {len(all_texts)} chunks to Pinecone index...")
#     PineconeVectorStore.from_documents(
#         all_texts,
#         embeddings,
#         index_name=PINECONE_INDEX_NAME,
#     )

#     print("\nIngestion complete!")
    
#     # --- 7. Clean up ---
#     print(f"Deleting temporary repo folder: {LOCAL_REPO_PATH}")
#     shutil.rmtree(LOCAL_REPO_PATH, onerror=on_rm_error)
#     print("Done.")


# if __name__ == "__main__":
#     if not all([OWNER, REPO, PINECONE_API_KEY, PINECONE_INDEX_NAME]):
#         print("Error: Missing required variables in .env file.")
#         print("Please set OWNER, REPO, PINECONE_API_KEY, and PINECONE_INDEX_NAME")
#     else:
#         ingest_data()




# change in code
import os
import shutil
import stat
import sys   # >>> ADDED
from git import Repo
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import (
    RecursiveCharacterTextSplitter,
)
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone, ServerlessSpec
from config import PINECONE_API_KEY, PINECONE_INDEX_NAME, OWNER, REPO

# ============================================================
#  Configuration
# ============================================================

GITHUB_REPO_URL = f"https://github.com/{OWNER}/{REPO}.git"

# >>> COMMENTED ORIGINAL
# LOCAL_REPO_PATH = "temp_client_repo"  # Temporary folder to clone into

# >>> ADDED: Shared repo path from GitHub Workflow
SHARED_REPO_PATH = None
if len(sys.argv) > 1:
    SHARED_REPO_PATH = sys.argv[1]
    print(f"🔄 Shared repo path detected: {SHARED_REPO_PATH}")

GLOB_PATTERN = "**/*"

EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIMENSION = 384


# ============================================================
#  Helper: Handle Read-only Files
# ============================================================

def on_rm_error(func, path, exc_info):
    if not os.access(path, os.W_OK):
        os.chmod(path, stat.S_IWRITE)
        func(path)
    else:
        raise


# ============================================================
#  Main Ingestion Logic
# ============================================================

def ingest_data():
    """
    UPDATED:
    - If shared repo path is provided → reuse it
    - Otherwise clone repo
    - No temp delete when reusing shared clone
    """

    # ============================================================
    # 1) Decide Repo Path (shared or clone)
    # ============================================================

    if SHARED_REPO_PATH and os.path.exists(SHARED_REPO_PATH):
        repo_path = SHARED_REPO_PATH
        print(f"🔄 Reusing provided repo path: {repo_path}")
        remove_after = False
    else:
        # >>> COMMENTED ORIGINAL
        # repo_path = LOCAL_REPO_PATH

        # >>> ADDED: Create temp clone
        repo_path = "temp_client_repo_ingest"
        remove_after = True

        if os.path.exists(repo_path):
            print("Deleting old temp repo...")
            shutil.rmtree(repo_path, onerror=on_rm_error)

        print(f"📥 Cloning repository {GITHUB_REPO_URL} into {repo_path}...")
        try:
            Repo.clone_from(GITHUB_REPO_URL, repo_path)
            print("Repo cloned successfully.")
        except Exception as e:
            print(f"❌ FAILED to clone repo: {e}")
            return

    # ============================================================
    # 2) Load Files
    # ============================================================

    print(f"\n--- Loading Repo Files ({GLOB_PATTERN}) ---")

    try:
        loader = DirectoryLoader(
            repo_path,
            glob=GLOB_PATTERN,
            loader_cls=TextLoader,
            loader_kwargs={"autodetect_encoding": True},
            show_progress=True,
            use_multithreading=True,
            silent_errors=True,
        )

        documents = loader.load()
        print(f"Loaded {len(documents)} files.")

    except Exception as e:
        print(f"❌ Error during document loading: {e}")
        return

    if not documents:
        print("⚠ No documents found. Exiting.")
        return

    # ============================================================
    # 3) Split into Chunks
    # ============================================================

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=100
    )

    texts = splitter.split_documents(documents)

    print(f"Split into {len(texts)} chunks.")

    # ============================================================
    # 4) Embedding Model
    # ============================================================

    print(f"Loading embedding model: {EMBEDDING_MODEL}...")
    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)

    # ============================================================
    # 5) Pinecone Index Check
    # ============================================================

    print("Initializing Pinecone client...")
    pc = Pinecone(api_key=PINECONE_API_KEY)

    existing = pc.list_indexes().names()

    if PINECONE_INDEX_NAME not in existing:
        print(f"Index '{PINECONE_INDEX_NAME}' not found → Creating new index.")
        pc.create_index(
            name=PINECONE_INDEX_NAME,
            dimension=EMBEDDING_DIMENSION,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
    else:
        print(f"Index '{PINECONE_INDEX_NAME}' exists.")

    # ============================================================
    # 6) Upload to Pinecone
    # ============================================================

    print(f"📤 Uploading {len(texts)} chunks → Pinecone…")

    PineconeVectorStore.from_documents(
        texts,
        embeddings,
        index_name=PINECONE_INDEX_NAME,
    )

    print("\n✅ Ingestion complete!")

    # ============================================================
    # 7) Cleanup
    # ============================================================

    if remove_after:
        print(f"🧹 Removing temp repo folder: {repo_path}")
        shutil.rmtree(repo_path, onerror=on_rm_error)
    else:
        print("♻ Reuse mode active → Repo NOT deleted.")


# ============================================================
#  Main Entry
# ============================================================

if __name__ == "__main__":
    if not all([OWNER, REPO, PINECONE_API_KEY, PINECONE_INDEX_NAME]):
        print("❌ Missing required env vars in .env file.")
        print("Please set OWNER, REPO, PINECONE_API_KEY, PINECONE_INDEX_NAME.")
    else:
        ingest_data()
