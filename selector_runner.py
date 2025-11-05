# selector_runner.py
# Iterative prompt selector runner

from selector import IterativePromptSelector
from selector import process_pr_with_selector

# --- FIX 1: Added 'post_to_github' parameter here ---
def run_selector(pr_numbers, load_previous=True, post_to_github: bool = False):
    selector = IterativePromptSelector()
    if load_previous:
        selector.load_state()

    results = []
    
    # --- FIX 2: This 'for' loop and everything below it MUST be indented ---
    for pr in pr_numbers:
        try:
            res = process_pr_with_selector(selector, pr, post_to_github=post_to_github)
            results.append(res)

            # --- NEW: Print the full review to the terminal ---
            print("\n" + "="*60)
            print(f"🤖 AI REVIEW FOR PR #{pr} (Prompt: {res['chosen_prompt']})")
            print("="*60 + "\n")
            print(res['review']) # This prints the full review text
            print("\n" + "="*60 + "\n")
            # --- END OF NEW BLOCK ---

        except Exception as e:
            print(f"Failed to process PR #{pr}: {e}")
            continue

    print("\nFINAL ITERATIVE SELECTOR REPORT")
    for r in results:
        print(f"PR #{r['pr_number']}: {r['chosen_prompt']} -> Score: {r['score']}")

    selector.save_state()
    return results, selector
