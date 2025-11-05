# utils.py

import os
from typing import List

def safe_truncate(text: str, max_len: int = 4000) -> str:
    """
    Truncates text to a max length, ensuring it breaks cleanly at a newline
    and adds an ellipsis for clarity.
    """
    if len(text) <= max_len:
        return text
    truncated = text[:max_len]
    last_newline = truncated.rfind('\n')
    if last_newline != -1:
        return truncated[:last_newline] + "\n\n... (Output truncated)"
    return truncated + " ... (Output truncated)"

def chunk_text(text: str, max_chars: int = 3500) -> List[str]:
    """
    Splits text (like a PR diff) into chunks based on lines, ensuring each
    chunk does not exceed max_chars.
    """
    lines = text.splitlines()
    chunks, current = [], []
    length = 0

    for line in lines:
        # +1 for the newline character
        if length + len(line) + 1 > max_chars: 
            chunks.append("\n".join(current))
            current, length = [], 0
        current.append(line)
        length += len(line) + 1
        
    if current:
        chunks.append("\n".join(current))
        
    return chunks
