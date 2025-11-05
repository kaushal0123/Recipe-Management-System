# benchmark.py
# Benchmark runner: runs all prompts on a PR, evaluates, and saves reports

import time
import csv
from datetime import datetime
from core import fetch_pr_diff, run_prompt, save_text_to_file
from prompts import get_prompts
from evaluation import heuristic_metrics, meta_evaluate, combine_final_score, heuristics_to_score
from config import OWNER, REPO, GITHUB_TOKEN

def benchmark_all_prompts(pr_number: int, post_to_github: bool = False):
    prompts = get_prompts()
    diff = fetch_pr_diff(OWNER, REPO, pr_number, GITHUB_TOKEN)
    print(f"Fetched diff ({len(diff)} chars). Running {len(prompts)} prompts...")

    results = []
    for name, prompt in prompts.items():
        print(f"-> Running prompt: {name}")
        start = time.time()
        try:
            # --- MODIFIED: run_prompt now returns review, static_output, and context ---
            review, static_output, context = run_prompt(prompt, diff)
            # -------------------------------------------------------------------------
        except Exception as e:
            review = f"ERROR: prompt invoke failed: {e}"
            static_output = "N/A" # Default for failed run
            context = "N/A" # Default for failed run
        elapsed = time.time() - start

        heur = heuristic_metrics(review)
        
        # --- MODIFIED: meta_evaluate now also takes context ---
        meta_parsed, meta_raw = meta_evaluate(diff, review, static_output=static_output, context=context) 
        # ------------------------------------------------------
        
        final_score, meta_score, heur_score = combine_final_score(meta_parsed, heur), None, heuristics_to_score(heur)
        meta_score = None if (not isinstance(meta_parsed, dict) or "error" in meta_parsed) else meta_parsed

        results.append({
            "prompt": name,
            "review": review,
            "time_s": round(elapsed, 2),
            "heur_score": heur_score,
            "meta_score": meta_score if meta_score else "N/A",
            "final_score": final_score,
            "meta_raw": meta_raw if meta_raw else "",
            "static_output": static_output, # Store static output for debugging
            "retrieved_context": context # NEW: Store context for debugging
        })
        time.sleep(0.2) # (UNCHANGED)

    # Sort results by final_score (UNCHANGED)
    results_sorted = sorted(results, key=lambda r: (r["final_score"] if isinstance(r["final_score"], (int, float)) else 0))

    # Save CSV (UNCHANGED)
    csv_file = f"review_reports_all_prompts_PR{pr_number}.csv"
    with open(csv_file, "w", newline="", encoding="utf-8") as cf:
        writer = csv.writer(cf)
        writer.writerow(["prompt", "time_s", "heur_score", "meta_score", "final_score"])
        for r in results_sorted:
            writer.writerow([r["prompt"], r["time_s"], r["heur_score"], r["meta_score"], r["final_score"]])

    # Save Markdown summary (UNCHANGED)
    md_file = f"review_reports_all_prompts_PR{pr_number}.md"
    md_lines = [f"# Prompt Comparison Report — PR {pr_number}\nGenerated: {datetime.now().isoformat()}\n"]
    md_lines.append("| Prompt | Time (s) | Heur. Score | Meta Score | Final Score |")
    md_lines.append("|---|---:|---:|---:|---:|")
    for r in results_sorted:
        md_lines.append(f"| {r['prompt']} | {r['time_s']} | {r['heur_score']} | {r['meta_score']} | {r['final_score']} |")
    save_text_to_file(md_file, "\n".join(md_lines))

    # Save individual reviews (MODIFIED)
    for r in results:
        safe_name = r["prompt"].replace("/", "_")
        fname = f"review_{safe_name}_PR{pr_number}.md"
        # Include static analysis AND context in the individual review file
        content = (
            f"# Review by prompt: {r['prompt']}\n\n{r['review']}\n\n"
            f"---\n## Static Analysis Output:\n{r['static_output']}\n\n"
            f"---\n## Retrieved Context:\n{r['retrieved_context']}\n\n"
            f"---\n## Meta Raw:\n{r['meta_raw']}"
        )
        save_text_to_file(fname, content)

    print(f"\nSaved summary to {md_file} and CSV to {csv_file}")
    return results_sorted
