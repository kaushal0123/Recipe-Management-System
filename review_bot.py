import os
import json
import requests
import sys
from openai import OpenAI

# === Environment setup ===
repo = os.getenv("GITHUB_REPOSITORY")
pr_number = os.getenv("PR_NUMBER")
token = os.getenv("GITHUB_TOKEN")
openai_key = os.getenv("OPENAI_API_KEY")

if not all([repo, pr_number, token, openai_key]):
    raise SystemExit("❌ Missing required environment variables")

headers = {
    "Authorization": f"token {token}",
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "ai-pr-bot"
}

client = OpenAI(api_key=openai_key)

# === GitHub API helpers ===
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
    r.raise_for_status()
    print("✅ Comment posted successfully")

# === Utility ===
def chunk_text(text, max_chars=3500):
    """Split text into safe chunks"""
    lines = text.splitlines()
    chunks, current = [], []
    length = 0

    for line in lines:
        if length + len(line) > max_chars:
            chunks.append("\n".join(current))
            current, length = [], 0
        current.append(line)
        length += len(line)
    if current:
        chunks.append("\n".join(current))
    return chunks

# === LLM functions ===
def generate_review(diff_chunk: str, static_issues=None) -> str:
    """Send chunk to LLM for review"""
    if static_issues:
        issues_summary = "\n".join(
            [f"- {issue}" for issue in static_issues[:10]]
        )
        analyzer_text = f"\nStatic Analyzer Findings:\n{issues_summary}\n"
    else:
        analyzer_text = ""

    prompt = f"""
You are an AI pull request reviewer.

Here is a code diff chunk from a PR:
{diff_chunk}

{analyzer_text}

Write a structured review:
- Briefly summarize what this chunk changes
- Give at least 2 improvement suggestions
- Mention any risks (bugs, performance, security)
Respond in markdown format.
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=600
    )
    return response.choices[0].message.content


def load_static_issues():
    """Read flake8 static analysis output if present"""
    if not os.path.exists("flake8-report.json"):
        return []
    with open("flake8-report.json") as f:
        data = json.load(f)

    issues = []
    for file, file_issues in data.items():
        for issue in file_issues:
            issues.append(
                f"{file}:{issue['line_number']} - {issue['text']}"
            )
    return issues


def main():
    with_analyzer = "--with-analyzer" in sys.argv
    mode = "Static Analyzer Mode" if with_analyzer else "Normal Mode"

    print(f"🔍 Reviewing PR #{pr_number} in {repo} ({mode})...")

    diff = fetch_diff()
    chunks = chunk_text(diff)
    print(f"📦 Split diff into {len(chunks)} chunks")

    static_issues = load_static_issues() if with_analyzer else None

    for i, chunk in enumerate(chunks, start=1):
        review = generate_review(chunk, static_issues)
        prefix = "🤖 AI Review" if not with_analyzer else "🧠 AI Review (with Static Analyzer)"
        post_comment(f"### {prefix} (Part {i}/{len(chunks)})\n\n{review}")

    print("🎉 Review completed!")


if __name__ == "__main__":
    main()
