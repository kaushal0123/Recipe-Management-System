import os
import re
import subprocess
from typing import Dict, List

# =====================================================
# 1. Static Analysis Configuration (Simplified)
# =====================================================

# We’ll keep this map since your diff parsing might rely on it,
# but we’ll only use it for file detection (not tool selection)
FILE_LANG_MAP = {
    "py": "python",
    "js": "javascript", "jsx": "javascript", "ts": "javascript", "tsx": "javascript",
    "java": "java",
    "cpp": "cpp", "cc": "cpp", "cxx": "cpp", "h": "cpp", "hpp": "cpp",
    "go": "go",
    "kt": "kotlin",
    "rs": "rust"
}

# =====================================================
# 2. Helper: Detect changed files by language (same as before)
# =====================================================

def get_changed_files_and_languages(diff_text: str) -> Dict[str, List[str]]:
    """
    Infers file types/languages and gets paths from the PR diff.
    Returns a dict: { 'language': [list of file paths] }
    """
    file_paths = re.findall(r'\+\+\+ b/(.*)', diff_text)
    changed_files: Dict[str, List[str]] = {}
    
    for path in file_paths:
        ext = path.split('.')[-1].lower()
        lang = FILE_LANG_MAP.get(ext)
        if lang:
            changed_files.setdefault(lang, []).append(path)

    return changed_files

# =====================================================
# 3. Run Semgrep Analysis
# =====================================================

def run_static_analysis(diff_text: str) -> str:
    """
    Runs Semgrep static analysis on ONLY the changed files and compiles results.
    Returns a single string containing all analyzer outputs.
    """
    changed_files_map = get_changed_files_and_languages(diff_text)

    if not changed_files_map:
        return "⚠ No recognizable programming language files found in PR diff to analyze."

    # Flatten all file paths across all languages
    all_changed_files = [f for files in changed_files_map.values() for f in files]
    
    results: List[str] = []
    results.append(f"=== 🔍 Targeted Static Analysis using Semgrep ({len(all_changed_files)} files changed) ===")

    # Construct Semgrep command
    # --config auto lets Semgrep detect language and apply built-in rules
    full_cmd = ["semgrep", "--config", "auto", "--error"] + all_changed_files

    try:
        process = subprocess.run(
            full_cmd,
            capture_output=True,
            text=True,
            check=False,  # don't raise exceptions for exit codes
            timeout=120
        )

        output = process.stdout.strip()
        error_output = process.stderr.strip()

        if output:
            results.append(f"| 🧠 Semgrep Output:\n\n{output}\n")
        elif error_output:
            results.append(f"| 🧠 Semgrep Output:\n\n{error_output}\n")
        else:
            results.append("| 🧠 Semgrep: No issues found.")

    except FileNotFoundError:
        results.append("| 🧠 Semgrep: ❌ Command not found. Please install Semgrep (pip install semgrep).")
    except subprocess.TimeoutExpired:
        results.append("| 🧠 Semgrep: ❌ Execution timed out after 120 seconds.")
    except Exception as e:
        results.append(f"| 🧠 Semgrep: ❌ Error running analysis: {e}")

    return "\n\n".join(results)
