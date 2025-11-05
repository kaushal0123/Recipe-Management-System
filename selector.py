# selector.py
# IterativePromptSelector: extract PR features, select prompts, learn from feedback
# Also contains runner helpers that save results.

import json
import re
import time
import numpy as np
from datetime import datetime
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from core import run_prompt, fetch_pr_diff, save_text_to_file , post_review_comment
# --- MODIFIED: Import global score functions, not local ones ---
from evaluation import heuristic_metrics, meta_to_score, heuristics_to_score 
from prompts import get_prompts
from config import OWNER, REPO, PR_NUMBER, GITHUB_TOKEN
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from core import llm 
# --- NEW: Need safe_truncate for evaluator prompt ---
from utils import safe_truncate
# ----------------------------------------------------

# --- MODIFIED: Meta-evaluator prompt template now includes {static} AND {context} ---
evaluator_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are an objective senior software engineer who judges review quality."),
    ("human",
     "You will evaluate a Pull Request review based on the diff, static analysis, and retrieved context provided.\n"
     "Judge if the review properly used the static analysis and context.\n"
     "Produce ONLY a JSON object (no extra commentary).\n\n"
     "Fields (1-10 integers): clarity, usefulness, depth, actionability, positivity.\n"
     "Also include a short `explain` string (1-2 sentences).\n\n"
     "Output JSON (exact format):\n"
     "{{\n"
     '  "clarity": <int 1-10>,\n'
     '  "usefulness": <int 1-10>,\n'
     '  "depth": <int 1-10>,\n'
     '  "actionability": <int 1-10>,\n'
     '  "positivity": <int 1-10>,\n'
     '  "explain": "short explanation"\n'
     "}}\n\n"
     "PR Diff (truncated):\n{diff}\n\n"
     "Static Analysis Results:\n{static}\n\n" # NEW: static analysis results
     "Retrieved Context:\n{context}\n\n" # NEW: RAG context
     "Review to evaluate:\n{review}\n")
])
# --------------------------------------------------------------------

# --- MODIFIED: We need to define the meta_evaluate function locally to use the new prompt
def meta_evaluate(diff: str, review: str, static_output: str, context: str):
    """
    Calls the evaluator LLM chain and returns parsed JSON (dict) and raw output.
    Returns (parsed_dict, raw_text). parsed_dict may contain 'error' key on problems.
    """
    chain = evaluator_prompt | llm | StrOutputParser()
    try:
        # Truncate inputs for the evaluator
        truncated_diff = safe_truncate(diff, 4000)
        truncated_review = safe_truncate(review, 4000)
        truncated_static = safe_truncate(static_output, 2000)
        truncated_context = safe_truncate(context, 2000)

        raw = chain.invoke({
            "diff": truncated_diff, 
            "review": truncated_review,
            "static": truncated_static,
            "context": truncated_context
        })
    except Exception as e:
        return {"error": f"evaluator invoke failed: {e}"}, None

    # parse JSON robustly (UNCHANGED)
    parsed = None
    try:
        parsed = json.loads(raw.strip())
    except Exception:
        m = re.search(r"\{.*\}", raw, flags=re.S)
        if m:
            try:
                parsed = json.loads(m.group(0))
            except Exception:
                parsed = {"error": "could not parse JSON", "raw": raw}
        else:
            parsed = {"error": "no JSON in evaluator output", "raw": raw}
    return parsed, raw
# -------------------------------------------------------------------------------------

class IterativePromptSelector:
    def __init__(self, min_samples_for_training: int = 5):
        self.prompts = get_prompts()
        self.prompt_names = list(self.prompts.keys())
        self.feature_history = [] # list of numpy arrays
        self.prompt_history = [] # list of prompt index ints
        self.score_history = [] # list of floats
        self.model = RandomForestRegressor(n_estimators=50, random_state=42)
        self.scaler = StandardScaler()
        self.is_trained = False
        self.min_samples_for_training = min_samples_for_training

    # -------------------------
    # Feature extraction (UNCHANGED)
    # -------------------------
    def extract_pr_features(self, diff_text: str):
        # ... (Contents of extract_pr_features remain the same) ...
        features = {}
        features['num_lines'] = len(diff_text.splitlines())
        features['num_files'] = len(re.findall(r'^diff --git', diff_text, re.MULTILINE))
        features['additions'] = len(re.findall(r'^\+', diff_text, re.MULTILINE))
        features['deletions'] = len(re.findall(r'^-', diff_text, re.MULTILINE))
        features['net_changes'] = features['additions'] - features['deletions']
        features['has_comments'] = int(bool(re.search(r'#.*|//.*|/\*.*?\*/', diff_text, re.DOTALL)))
        features['has_functions'] = int(bool(re.search(r'\bdef\s+\w+|\bfunction\b|\bfunc\b', diff_text, re.IGNORECASE)))
        features['has_imports'] = int(bool(re.search(r'^\s*import\s|^\s*from\s|#include', diff_text, re.MULTILINE)))
        features['has_test'] = int(bool(re.search(r'\btest\b|\bspec\b|\bunittest\b', diff_text, re.IGNORECASE)))
        features['has_docs'] = int(bool(re.search(r'\breadme\b|\bdoc\b|\bdocumentation\b', diff_text, re.IGNORECASE)))
        features['has_config'] = int(bool(re.search(r'\.json\b|\.yml\b|\.yaml\b|\.xml\b|\.conf\b', diff_text, re.IGNORECASE)))
        features['is_python'] = int(bool(re.search(r'\.py\b', diff_text, re.IGNORECASE)))
        features['is_js'] = int(bool(re.search(r'\.js\b|\.ts\b', diff_text, re.IGNORECASE)))
        features['is_java'] = int(bool(re.search(r'\.java\b', diff_text, re.IGNORECASE)))
        return features
    
    def features_to_vector(self, features: dict):
        order = [
            'num_lines', 'num_files', 'additions', 'deletions', 'net_changes',
            'has_comments', 'has_functions', 'has_imports', 'has_test',
            'has_docs', 'has_config', 'is_python', 'is_js', 'is_java'
        ]
        return np.array([features.get(k, 0) for k in order], dtype=float)

    # -------------------------
    # Selection & generation (UNCHANGED)
    # -------------------------
    def select_best_prompt(self, features_vector: np.ndarray):
        # ... (Contents of select_best_prompt remain the same) ...
        # If not enough data, do round-robin selection
        if not self.is_trained or len(self.feature_history) < self.min_samples_for_training:
            return self.prompt_names[len(self.feature_history) % len(self.prompt_names)]

        try:
            # For each prompt, append prompt index as an extra feature and predict score
            X = np.tile(features_vector, (len(self.prompt_names), 1))
            prompt_indices = np.arange(len(self.prompt_names)).reshape(-1, 1)
            X_with_prompt = np.hstack([X, prompt_indices])
            X_scaled = self.scaler.transform(X_with_prompt)
            preds = self.model.predict(X_scaled)
            best_idx = int(np.argmax(preds))
            return self.prompt_names[best_idx]
        except Exception:
            # fallback
            return self.prompt_names[0]

    def update_model(self, features_vector: np.ndarray, prompt_name: str, score: float):
        # ... (Contents of update_model remain the same) ...
        self.feature_history.append(features_vector)
        prompt_idx = self.prompt_names.index(prompt_name)
        self.prompt_history.append(prompt_idx)
        self.score_history.append(score)

        if len(self.feature_history) >= self.min_samples_for_training:
            try:
                X = np.array(self.feature_history)
                prompt_indices = np.array(self.prompt_history).reshape(-1, 1)
                X_combined = np.hstack([X, prompt_indices])
                y = np.array(self.score_history)
                # Fit scaler and model
                self.scaler.fit(X_combined)
                X_scaled = self.scaler.transform(X_combined)
                self.model.fit(X_scaled, y)
                self.is_trained = True
            except Exception as e:
                print(f"Model training failed: {e}")
                self.is_trained = False

    # -------------------------
    # Generate & evaluate review (MODIFIED)
    # -------------------------
    def generate_review(self, diff_text: str, selected_prompt: str, diff_truncate: int = 4000):
        prompt = self.prompts[selected_prompt]
        start = time.time()
        # --- MODIFIED: run_prompt now returns review, static_output, and context ---
        review, static_output, context = run_prompt(prompt, diff_text, diff_truncate=diff_truncate)
        # -----------------------------------------------------------------
        elapsed = time.time() - start
        return review, static_output, elapsed, context # Return context

    def evaluate_review(self, diff_text: str, review_text: str, static_output: str, context: str):
        # --- MODIFIED: The meta_evaluate call now passes the context (using the locally defined function) ---
        heur = heuristic_metrics(review_text)
        meta_parsed, meta_raw = meta_evaluate(diff_text, review_text, static_output=static_output, context=context)
        # --------------------------------------------------------------------------------------------------

        final_score, meta_score, heur_score = None, None, None
        if isinstance(meta_parsed, dict) and "error" not in meta_parsed:
            meta_score = meta_to_score(meta_parsed)
            heur_score = heuristics_to_score(heur)
            final_score = round(0.7 * meta_score + 0.3 * heur_score, 2)
        else:
            heur_score = heuristics_to_score(heur)
            final_score = round(heur_score, 2)
        return final_score, heur, meta_parsed

    # -------------------------
    # I/O: save results & state (MODIFIED)
    # -------------------------
    def save_results(self, pr_number: int, features: dict, prompt_name: str, review: str, score: float, heur: dict, meta_parsed: dict, static_output: str, context: str):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"iterative_results_pr{pr_number}_{timestamp}.json"
        
        # --- MODIFIED: Add context summary to payload ---
        payload = {
            "timestamp": timestamp,
            "pr_number": pr_number,
            "selected_prompt": prompt_name,
            "review_score": score,
            "features": features,
            "heuristics": heur,
            "meta_evaluation": meta_parsed,
            "static_output_summary": static_output[:100] + "..." if len(static_output) > 100 else static_output,
            "retrieved_context_summary": context[:100] + "..." if len(context) > 100 else context, # NEW
            "training_data_size": len(self.feature_history),
            "model_trained": self.is_trained
        }
        # ------------------------------------------------
        
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        # also save the review text
        review_fname = f"review_pr{pr_number}_{prompt_name.replace('/', '_').replace(' ', '_')}.md"
        # Include static analysis AND context in the individual review file
        content = (
            f"# Review (prompt={prompt_name})\n\n{review}\n\n"
            f"---\n## Static Analysis Output:\n{static_output}\n\n"
            f"---\n## Retrieved Context:\n{context}\n"
        )
        save_text_to_file(review_fname, content)
        
    def save_state(self, filename: str = "selector_state.json"):
        # ... (Contents of save_state remain the same) ...
        state = {
            "feature_history": [f.tolist() for f in self.feature_history],
            "prompt_history": self.prompt_history,
            "score_history": self.score_history,
            "is_trained": self.is_trained,
            "scaler_mean": self.scaler.mean_.tolist() if self.is_trained else None,
            "scaler_scale": self.scaler.scale_.tolist() if self.is_trained else None
        }
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(state, f)

    def load_state(self, filename: str = "selector_state.json"):
        # ... (Contents of load_state remain the same) ...
        try:
            with open(filename, "r", encoding="utf-8") as f:
                state = json.load(f)
            self.feature_history = [np.array(f) for f in state.get("feature_history", [])]
            self.prompt_history = state.get("prompt_history", [])
            self.score_history = state.get("score_history", [])
            self.is_trained = state.get("is_trained", False)
            if self.is_trained and state.get("scaler_mean") is not None:
                self.scaler.mean_ = np.array(state["scaler_mean"])
                self.scaler.scale_ = np.array(state["scaler_scale"])
                self.scaler.n_features_in_ = len(state["scaler_mean"])
                self.scaler.var_ = self.scaler.scale_ ** 2
            print(f"Loaded selector state: {len(self.feature_history)} samples, trained={self.is_trained}")
        except FileNotFoundError:
            print("No selector state found; starting fresh.")
        except Exception as e:
            print(f"Failed to load state: {e}; starting fresh.")
            self.feature_history = []
            self.prompt_history = []
            self.score_history = []
            self.is_trained = False

# -------------------------
# Helper runner: process a PR using selector and persist outputs (MODIFIED)
# -------------------------
# [NEW]
def process_pr_with_selector(selector: IterativePromptSelector, pr_number: int, owner=OWNER, repo=REPO, token=GITHUB_TOKEN, post_to_github: bool = False):
    print(f"Processing PR #{pr_number}...")
    diff_text = fetch_pr_diff(owner, repo, pr_number, token)
    features = selector.extract_pr_features(diff_text)
    features_vector = selector.features_to_vector(features)
    chosen = selector.select_best_prompt(features_vector)
    print(f"Selected prompt: {chosen}")
    
    # --- MODIFIED: get static_output, elapsed, and context ---
    review, static_output, elapsed, context = selector.generate_review(diff_text, chosen)
    # ----------------------------------------------------
    
    print(f"Review generated in {elapsed:.2f}s")
    
    # --- MODIFIED: pass context to evaluate_review ---
    score, heur, meta_parsed = selector.evaluate_review(diff_text, review, static_output, context)
    # -------------------------------------------------------
    
    print(f"Score: {score}/10")
    selector.update_model(features_vector, chosen, score)
    
    # --- MODIFIED: pass static_output and context to save_results ---
    selector.save_results(pr_number, features, chosen, review, score, heur, meta_parsed, static_output, context)

        # --- ✅ NEW: Post the AI Review Comment on GitHub ---
    if post_to_github:
        try:
            review_body = f"""### 🤖 AI Review (Prompt: {chosen})
**Score:** {score}/10

{review}

---

🧩 **Static Analysis Summary:**
{static_output[:1000]}...

---

📚 **Retrieved Context Summary:**
{context[:1000]}...
"""
            post_review_comment(owner, repo, pr_number, review_body, token)
            print(f"✅ Successfully posted AI review comment for PR #{pr_number}")
        except Exception as e:
            print(f"⚠️ Failed to post review comment for PR #{pr_number}: {e}")

    # ----------------------------------------------------
    
    return {
        "pr_number": pr_number,
        "chosen_prompt": chosen,
        "review": review,
        "score": score,
        "features": features
    }
