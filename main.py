# main.py
# Fully automated PR review: uses selector to pick best prompt based on past data
# Only requires PR_NUMBER in .env

from selector_runner import run_selector
from config import PR_NUMBER

if _name_ == "_main_":
    # --- MODIFIED: Safely convert PR_NUMBER to an integer ---
    try:
        pr_num = int(PR_NUMBER)
    except (TypeError, ValueError):
        pr_num = 0 # Default to 0 if PR_NUMBER is None or not a number

    if pr_num <= 0:
        print("Error: PR_NUMBER is not set or invalid in .env")
    else:
        print(f"Processing PR #{pr_num} using iterative selector...")
        run_selector([pr_num], post_to_github=True)
        print("Done! Review generated and selector state updated.")
