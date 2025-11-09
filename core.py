# core.py
# GitHub helpers, LLM init, prompt runner, file I/O

import requests
import re
import subprocess 
from langchain_core.output_parsers import StrOutputParser
from langchain_groq import ChatGroq
from typing import Optional, Tuple
from config import GITHUB_TOKEN, GROQ_API_KEY
from static_analysis import run_static_analysis 
from utils import safe_truncate 
# --- NEW RAG IMPORT ---
from rag_core import get_retriever
# ----------------------

# ------------------------------
# GitHub helpers (UNCHANGED)
# ------------------------------

import os

import os

def fetch_pr_diff(owner: str, repo: str, pr_number: int, token: Optional[str] = None) -> str:
    token = token or GITHUB_TOKEN
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
    headers = {"Authorization": f"token {token}"}
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        raise RuntimeError(f"GitHub API Error fetching PR: {resp.status_code} {resp.text}")
    pr_data = resp.json()
    diff_url = pr_data.get("diff_url")
    if not diff_url:
        raise RuntimeError("No diff_url found in PR data.")
    diff_resp = requests.get(diff_url, headers=headers)
    if diff_resp.status_code != 200:
        raise RuntimeError(f"Failed to fetch diff: {diff_resp.status_code} {diff_resp.text}")
    return diff_resp.text

def post_review_comment(owner: str, repo: str, pr_number: int, review_body: str, token: Optional[str] = None) -> dict:
    token = token or GITHUB_TOKEN
    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}
    payload = {"body": review_body}
    resp = requests.post(url, headers=headers, json=payload)
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Failed to post comment: {resp.status_code} {resp.text}")
    return resp.json()

# ------------------------------
# LLM initialization & parser (UNCHANGED)
# ------------------------------
llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0.25,
    api_key=GROQ_API_KEY,
)

# simple parser that returns string output (used for prompt outputs)
default_parser = StrOutputParser()

# ------------------------------
# Prompt runner (MODIFIED FOR RAG)
# ------------------------------
def run_prompt(prompt, diff: str, llm_instance=llm, parser=default_parser, diff_truncate: int = 4000, static_output_truncate: int = 4000) -> Tuple[str, str, str]:
    """
    Run a ChatPromptTemplate (langchain) against the llm+parser.
    Also runs static analysis and RAG, including both in the prompt context.
    
    Returns:
        (review_text, static_analysis_output, retrieved_context)
    """
    # 1. Run Static Analysis
    static_output = run_static_analysis(diff)
    
    # 2. Truncate inputs for the LLM
    truncated_diff = safe_truncate(diff, diff_truncate)
    truncated_static = safe_truncate(static_output, static_output_truncate)
    
    # --- 3. NEW RAG STEP ---
    print("Running RAG retrieval...")
    retriever = get_retriever()
    # Create a query for the retriever based on the diff and static analysis
    retrieval_query = f"How to review this code? Diff: {truncated_diff}\nStatic Analysis: {truncated_static}"
    retrieved_docs = retriever.invoke(retrieval_query)
    retrieved_context = "\n---\n".join([doc.page_content for doc in retrieved_docs])
    truncated_context = safe_truncate(retrieved_context, 2000) # Truncate context
    # -----------------------
    
    # 4. Invoke LLM Chain
    chain = prompt | llm_instance | parser
    
    # --- MODIFIED: Pass 'context' into the prompt variables ---
    review = chain.invoke({
        "diff": truncated_diff, 
        "static": truncated_static,
        "context": truncated_context 
    })

    return review, static_output, retrieved_context # Return all 3 for evaluation

# ------------------------------
# Utilities: file I/O (UNCHANGED)
# ------------------------------
def save_text_to_file(path: str, text: str):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
