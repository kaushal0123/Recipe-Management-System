# import os
# import re
# import subprocess
# import tempfile
# import shutil
# import stat
# from git import Repo
# from typing import Dict, List

# # =====================================================
# # 1. Configuration & Helpers
# # =====================================================

# # Map extensions to languages (used for file detection)
# FILE_LANG_MAP = {
#     "py": "python",
#     "js": "javascript", "jsx": "javascript", "ts": "javascript", "tsx": "javascript",
#     "java": "java",
#     "cpp": "cpp", "cc": "cpp", "cxx": "cpp", "h": "cpp", "hpp": "cpp",
#     "go": "go",
#     "kt": "kotlin",
#     "rs": "rust",
#     "rb": "ruby",
#     "php": "php"
# }

# def on_rm_error(func, path, exc_info):
#     """
#     Error handler for shutil.rmtree.
#     If a file is read-only (common on Windows/Git), it makes it writable and tries to delete again.
#     """
#     if not os.access(path, os.W_OK):
#         os.chmod(path, stat.S_IWRITE)
#         func(path)
#     else:
#         raise

# def get_changed_files_and_languages(diff_text: str) -> Dict[str, List[str]]:
#     """
#     Infers file types/languages and gets paths from the PR diff.
#     Returns a dict: { 'language': [list of file paths] }
#     """
#     file_paths = re.findall(r'\+\+\+ b/(.*)', diff_text)
#     changed_files: Dict[str, List[str]] = {}
    
#     for path in file_paths:
#         ext = path.split('.')[-1].lower()
#         lang = FILE_LANG_MAP.get(ext)
#         if lang:
#             changed_files.setdefault(lang, []).append(path)
#     return changed_files

# # =====================================================
# # 2. Main Analysis Logic (Semgrep + Git Clone)
# # =====================================================

# def run_static_analysis(diff_text: str, owner: str, repo_name: str, pr_number: int) -> str:
#     """
#     Clones the PR, checks out the code, and runs Semgrep on the changed files.
#     """
#     # 1. Identify files to analyze from the diff
#     changed_files_map = get_changed_files_and_languages(diff_text)
    
#     if not changed_files_map:
#         return "⚠ No recognizable programming language files found in PR diff to analyze."

#     # Flatten list of files to analyze (Semgrep handles multiple languages automatically)
#     all_changed_files = [f for files in changed_files_map.values() for f in files]
    
#     # 2. Create Temp Directory
#     temp_dir = tempfile.mkdtemp()
#     print(f"  Created temp directory for Semgrep: {temp_dir}")
    
#     repo_url = f"https://github.com/{owner}/{repo_name}.git"
#     results: List[str] = []
#     results.append(f"=== 🔍 Targeted Static Analysis using Semgrep ({len(all_changed_files)} files) ===")

#     try:
#         # 3. Clone and Checkout PR
#         print(f"  Cloning {owner}/{repo_name}...")
#         repo = Repo.clone_from(repo_url, temp_dir)
        
#         print(f"  Fetching PR #{pr_number}...")
#         pr_branch_name = f"pr-{pr_number}"
#         repo.remotes.origin.fetch(f"pull/{pr_number}/head:{pr_branch_name}")
        
#         print(f"  Checking out PR branch...")
#         repo.git.checkout(pr_branch_name)

#         # 4. Run Semgrep
#         # We run it INSIDE temp_dir so it finds the actual files on disk
#         print("  Running Semgrep...")
        
#         # --config auto: Uses Semgrep's recommended rules registry
#         # --quiet: suppress progress bars
#         # --error: ensure non-zero exit code on findings (optional, but good for checking)
#         cmd = ["semgrep", "--config", "auto", "--quiet"] + all_changed_files

#         process = subprocess.run(
#             cmd,
#             cwd=temp_dir, # <--- CRITICAL: Run command inside the cloned repo
#             capture_output=True,
#             text=True,
#             check=False,
#             timeout=120
#         )

#         output = process.stdout.strip()
#         error_output = process.stderr.strip()

#         # 5. Format Output
#         if output:
#             results.append(f"| 🧠 Semgrep Issues Found:\n\n{output}\n")
#         elif process.returncode == 0 and not error_output:
#             results.append("| 🧠 Semgrep: No issues found (Clean code!).")
#         else:
#             # If there is stderr output or a crash
#             results.append(f"| 🧠 Semgrep Output/Error:\n{output if output else error_output}")

#     except FileNotFoundError:
#         results.append("| ❌ Error: 'semgrep' command not found. Please run: pip install semgrep")
#     except subprocess.TimeoutExpired:
#         results.append("| ❌ Error: Semgrep timed out after 120s.")
#     except Exception as e:
#         results.append(f"| ❌ Unexpected Error: {e}")
        
#     finally:
#         # 6. Cleanup
#         print(f"  Cleaning up {temp_dir}...")
#         if os.path.exists(temp_dir):
#             try:
#                 shutil.rmtree(temp_dir, onerror=on_rm_error)
#                 print("  Cleanup successful.")
#             except Exception as e:
#                 print(f"  Cleanup warning: {e}")

#     return "\n\n".join(results)




# change in code
import os
import re
import subprocess
import tempfile
import shutil
import stat
from git import Repo
from typing import Dict, List
import sys   # >>> ADDED (for shared repo clone path)

# =====================================================
# 1. Configuration & Helpers
# =====================================================

FILE_LANG_MAP = {
    "py": "python",
    "js": "javascript", "jsx": "javascript", "ts": "javascript", "tsx": "javascript",
    "java": "java",
    "cpp": "cpp", "cc": "cpp", "cxx": "cpp", "h": "cpp", "hpp": "cpp",
    "go": "go",
    "kt": "kotlin",
    "rs": "rust",
    "rb": "ruby",
    "php": "php"
}

def on_rm_error(func, path, exc_info):
    if not os.access(path, os.W_OK):
        os.chmod(path, stat.S_IWRITE)
        func(path)
    else:
        raise

def get_changed_files_and_languages(diff_text: str) -> Dict[str, List[str]]:
    file_paths = re.findall(r'\+\+\+ b/(.*)', diff_text)
    changed_files: Dict[str, List[str]] = {}
    
    for path in file_paths:
        ext = path.split('.')[-1].lower()
        lang = FILE_LANG_MAP.get(ext)
        if lang:
            changed_files.setdefault(lang, []).append(path)
    return changed_files

# =====================================================
# 2. Main Updated Logic: No Clone → Reuse repo
# =====================================================

def run_static_analysis(diff_text: str, owner: str, repo_name: str, pr_number: int) -> str:
    """
    UPDATED: If repo path is passed via CLI → use it.
    Only clone when NOT provided.
    """

    # >>> ADDED: try reading repo path from argument if provided
    repo_override_path = None
    if len(sys.argv) > 1:
        repo_override_path = sys.argv[1]  # shared clone path
        print(f"🔄 Using pre-cloned repository: {repo_override_path}")
    else:
        print("⚠ No repo path passed. Falling back to cloning inside static analyser.")

    changed_files_map = get_changed_files_and_languages(diff_text)
    
    if not changed_files_map:
        return "⚠ No recognizable programming language files found in PR diff to analyze."

    all_changed_files = [f for files in changed_files_map.values() for f in files]

    # =====================================================
    # CLONE / REUSE REPO
    # =====================================================

    if repo_override_path and os.path.exists(repo_override_path):
        temp_dir = repo_override_path
        print(f"👉 Reusing existing repo: {temp_dir}")
        remove_after = False   # do not delete
    else:
        # >>> COMMENTED ORIGINAL
        # temp_dir = tempfile.mkdtemp()

        # >>> ADDED
        temp_dir = tempfile.mkdtemp()
        print(f"📥 Cloning {owner}/{repo_name} into temp: {temp_dir}")
        remove_after = True

        repo_url = f"https://github.com/{owner}/{repo_name}.git"
        try:
            repo = Repo.clone_from(repo_url, temp_dir)
        except Exception as e:
            return f"❌ FAILED to clone repo: {e}"

    results: List[str] = []
    results.append(f"=== 🔍 Targeted Static Analysis using Semgrep ({len(all_changed_files)} files) ===")

    try:
        repo = Repo(temp_dir)

        # >>> COMMENTED ORIGINAL
        # repo.remotes.origin.fetch(f"pull/{pr_number}/head:{pr_branch_name}")

        # >>> ADDED
        print("Fetching PR branch...")
        pr_branch_name = f"pr-{pr_number}"
        try:
            repo.remotes.origin.fetch(f"pull/{pr_number}/head:{pr_branch_name}")
        except Exception as e:
            return f"❌ Unable to fetch PR branch: {e}"

        repo.git.checkout(pr_branch_name)

        print("Running Semgrep...")

        cmd = ["semgrep", "--config", "auto"] + all_changed_files

        process = subprocess.run(
            cmd,
            cwd=temp_dir,
            capture_output=True,
            text=True,
            check=False,
            timeout=120
        )

        output = process.stdout.strip()
        error_output = process.stderr.strip()

        if output:
            results.append(f"| 🧠 Semgrep Issues Found:\n\n{output}\n")
        elif process.returncode == 0 and not error_output:
            results.append("| 🧠 Semgrep: No issues found.")
        else:
            results.append(f"| 🧠 Semgrep Output/Error:\n{output if output else error_output}")

    except Exception as e:
        results.append(f"❌ Unexpected Error: {e}")

    finally:
        # Only delete if we cloned it internally
        if remove_after:
            print(f"🧹 Cleaning up: {temp_dir}")
            shutil.rmtree(temp_dir, onerror=on_rm_error)

    return "\n\n".join(results)
