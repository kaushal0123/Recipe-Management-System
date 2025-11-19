import os
import re
import subprocess
import tempfile
import shutil
import stat
from git import Repo  
from typing import Dict, List

# Helper function 
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

# Language-to-File-Extension Map (Unchanged)
FILE_LANG_MAP = {
    "py": "python",
    "js": "javascript", "jsx": "javascript", "ts": "javascript", "tsx": "javascript",
    "java": "java",
    "cpp": "cpp", "cc": "cpp", "cxx": "cpp", "h": "cpp", "hpp": "cpp",
    "go": "go",
    "kt": "kotlin",
    "rs": "rust"
}

# Static Analyzer Commands Map (Unchanged)
ANALYZERS = {
    "python": [
        ("🧩 Pylint", ["pylint", "--exit-zero"]),
        ("🎯 Flake8", ["flake8", "--exit-zero"]),
        ("🔒 Bandit", ["bandit", "-r"]),
        ("🧠 Mypy", ["mypy", "--ignore-missing-imports"]),
    ],
    "javascript": [
        ("ESLint", ["eslint", "--max-warnings=0"]),
    ],
    "java": [("Checkstyle", ["checkstyle", "-c", "/google_checks.xml"])],
    "cpp": [("Cppcheck", ["cppcheck", "--enable=all", "--quiet"])],
    "go": [("Staticcheck", ["staticcheck"])],
    "rust": [("Clippy", ["cargo", "clippy", "--", "-D", "warnings"])]
}

def get_changed_files_and_languages(diff_text: str) -> Dict[str, List[str]]:
    """
    Infers file types/languages and gets paths from the PR diff.
    (This function is unchanged)
    """
    file_paths = re.findall(r'\+\+\+ b/(.*)', diff_text)
    changed_files: Dict[str, List[str]] = {}
    for path in file_paths:
        ext = path.split('.')[-1].lower()
        lang = FILE_LANG_MAP.get(ext)
        if lang:
            changed_files.setdefault(lang, []).append(path)
    return changed_files

# --- MODIFIED: This is the new function with the fix ---
def run_static_analysis(
    diff_text: str, 
    owner: str, 
    repo_name: str, 
    pr_number: int
) -> str:
    """
    Checks out the PR's code to a temp directory and runs static analysis.
    """
    changed_files_map = get_changed_files_and_languages(diff_text)
    if not changed_files_map:
        return "⚠️ No recognizable programming language files found in PR diff to analyze."

    # 1. Create a temporary directory
    temp_dir = tempfile.mkdtemp()
    print(f"  Created temp directory for checkout: {temp_dir}")
    
    repo_url = f"https://github.com/{owner}/{repo_name}.git"
    results: List[str] = []

    try:
        # 2. Clone the repo (using logic from ingest.py)
        print(f"  Cloning {owner}/{repo_name} (main branch)...")
        repo = Repo.clone_from(repo_url, temp_dir)
        
        # 3. Fetch the PR's code
        print(f"  Fetching PR #{pr_number} branch...")
        pr_branch_name = f"pr-{pr_number}"
        repo.remotes.origin.fetch(f"pull/{pr_number}/head:{pr_branch_name}")
        
        # 4. Check out the PR's branch
        print(f"  Checking out PR branch...")
        repo.git.checkout(pr_branch_name)

        # 5. Now that files *exist locally*, run analysis
        for lang, files in changed_files_map.items():
            results.append(f"=== 🔍 Targeted Static Analysis for {lang.upper()} ({len(files)} files changed) ===")
            
            analyzer_list = ANALYZERS.get(lang, [])
            if not analyzer_list:
                results.append(f"No analyzer configured for {lang}")
                continue
                
            for name, base_cmd in analyzer_list:
                # We analyze *only* the files changed in the PR
                full_cmd = base_cmd + files
                
                try:
                    # Run the command *inside* the cloned repo
                    process = subprocess.run(
                        full_cmd,
                        cwd=temp_dir, # <-- This is the crucial part
                        capture_output=True,
                        text=True,
                        check=False,
                        timeout=120,
                        encoding='utf-8'
                    )
                    
                    output = process.stdout.strip()
                    error_output = process.stderr.strip()
                    
                    if output or error_output:
                        results.append(f"| {name}:\n```\n{output if output else error_output}\n```")
                    else:
                        results.append(f"| {name}: No issues found.")

                except FileNotFoundError:
                    results.append(f"| {name}: ❌ Command not found. Is the tool installed locally and in PATH?")
                except Exception as e:
                    results.append(f"| {name}: ❌ Error running analyzer: {e}")

    except Exception as e:
        results.append(f"❌ Failed to check out PR code: {e}")
    finally:
        # 6. Clean up (using logic from ingest.py)
        print(f"  Attempting cleanup of: {temp_dir}")
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, onerror=on_rm_error)
            print("  Cleanup successful.")

    return "\n\n".join(results)