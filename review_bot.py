import os
import requests
import json # Needed for reading flake8 report
import sys # Needed for reading command-line arguments
from groq import Groq, APIError # Groq’s OpenAI-compatible client

# === Configuration ===
GROQ_MODEL = "llama-3.1-8b-instant" # Fast, high-quality model

# === Environment setup ===
repo = os.getenv("GITHUB_REPOSITORY")
pr_number = os.getenv("PR_NUMBER")
# Use GITHUB_TOKEN for GitHub Actions bot
token = os.getenv("GITHUB_TOKEN") 
groq_key = os.getenv("GROQ_API_KEY")

if not all([repo, pr_number, token, groq_key]):
    # Note: Check for GROQ_API_KEY
    raise SystemExit("❌ Missing required environment variables (GITHUB_TOKEN, PR_NUMBER, GROQ_API_KEY).")

headers = {
    "Authorization": f"token {token}",
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "ai-pr-bot"
}

# Groq client
client = Groq(api_key=groq_key)

# === GitHub API helpers (Unchanged) ===
def fetch_diff():
    """Fetch PR diff text"""
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    diff_url = r.json()["diff_url"]

    r2 = requests.get(diff_url, headers=headers)
    r2.raise_for_status()
    return r2.text

def post_comment(body: str):
    """Post a comment on the PR"""
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    r = requests.post(url, headers=headers, json={"body": body})
    if r.status_code == 403:
        print("⚠️ Forbidden: Token may not have permission to comment on this PR.")
        print(r.json())
        return
    r.raise_for_status()
    print("✅ Comment posted successfully")

# === Utility and Analyzer Logic ===
def chunk_text(text, max_chars=3500):
    """Split text into safe chunks"""
    lines = text.splitlines()
    chunks, current = [], []
    length = 0

    for line in lines:
        # Check if adding the line exceeds the max length
        if length + len(line) > max_chars:
            chunks.append("\n".join(current))
            current, length = [], 0
        
        # Add the line to the current chunk
        current.append(line)
        length += len(line)
        
    if current:
        chunks.append("\n".join(current))
    return chunks

def load_static_issues():
    """Read flake8 static analysis output if present"""
    report_path = "flake8-report.json"
    if not os.path.exists(report_path):
        print(f"File not found: {report_path}")
        return []
        
    print(f"Loading static analysis report from {report_path}...")
    
    with open(report_path) as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            print("Warning: flake8-report.json is invalid JSON.")
            return []

    issues = []
    for file, file_issues in data.items():
        if isinstance(file_issues, list):
            for issue in file_issues:
                if isinstance(issue, dict) and 'line_number' in issue and 'text' in issue:
                    issues.append(f"{file}:{issue['line_number']} - {issue['text']}")
    return issues

# === LLM Review Core ===
def generate_review(diff_chunk: str, static_issues=None) -> str:
    """Send one chunk to Groq LLM for review"""
    analyzer_text = ""
    # If static issues are provided, include them in the prompt
    if static_issues:
        issues_summary = "\n".join([f"- {issue}" for issue in static_issues[:15]])
        analyzer_text = f"\nStatic Analyzer Findings to consider (max 15 issues):\n{issues_summary}\n"
    
    prompt = f"""
You are an AI pull request reviewer. Your goal is to provide constructive feedback.
Here is a code diff chunk from a PR:

{diff_chunk}

{analyzer_text}

Write a structured review:
- Briefly summarize what this chunk changes
- Give at least 2 improvement suggestions
- Note any risks (bugs, performance, security). Explicitly incorporate or dismiss static analyzer findings if present.
Respond ONLY in markdown format.
"""
    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=700 # Increased max tokens for detailed response
        )
        return response.choices[0].message.content
    except APIError as e:
        print(f"❌ Groq API Error: {e}")
        return f"❌ AI Review failed due to Groq API error: {e}"
    except Exception as e:
        print(f"❌ An unexpected error occurred during review generation: {e}")
        return f"❌ AI Review failed due to unexpected error: {e}"

def main():
    # Check for the flag to determine the mode
    with_analyzer = "--with-analyzer" in sys.argv
    mode = "Static Analyzer Mode" if with_analyzer else "Normal Mode"
    prefix = "🤖 AI Review (Base)" if not with_analyzer else "🧠 AI Review (Informed by Flake8)"

    print(f"🔍 Reviewing PR #{pr_number} in {repo} ({mode})...")
    
    try:
        diff = fetch_diff()
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to fetch PR diff from GitHub: {e}")
        sys.exit(1)

    chunks = chunk_text(diff)
    print(f"📦 Split diff into {len(chunks)} chunks")

    # Load static issues only if the flag is present
    static_issues = load_static_issues() if with_analyzer else None
    if with_analyzer and static_issues:
        print(f"📝 Loaded {len(static_issues)} static issues.")

    # Collect all chunk reviews into one final comment body
    all_reviews = []
    
    for i, chunk in enumerate(chunks, start=1):
        review = generate_review(chunk, static_issues)
        all_reviews.append(f"#### Diff Chunk {i}/{len(chunks)}\n\n{review}")

    final_body = f"## {prefix} for PR #{pr_number}\n\n"
    final_body += "\n---\n".join(all_reviews)

    post_comment(final_body)

    print("🎉 Review completed!")

if __name__ == "__main__":
    main()
