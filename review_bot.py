import os, json, requests, time
from dotenv import load_dotenv

load_dotenv()

GITHUB_REPOSITORY = os.getenv("GITHUB_REPOSITORY", "Kaushal0123/Recipe-Management-System")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
POLL_INTERVAL = 60  # Check every 60 seconds (adjust as needed)

if not GITHUB_TOKEN:
    raise SystemExit("Set GITHUB_TOKEN in .env as a PAT with repo scope.")

owner, repo = GITHUB_REPOSITORY.split("/")

def get_open_prs():
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls?state=open"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json", "User-Agent": "ai-bot"}
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        raise RuntimeError(f"GitHub API Error: {r.status_code} - {r.text}")
    return r.json()

def fetch_pr_diff(owner, repo, pr_number, token):
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json", "User-Agent": "ai-bot"}
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        raise RuntimeError(f"GitHub API Error: {r.status_code} - {r.text}")
    pr_json = r.json()
    diff_url = pr_json.get("diff_url")
    if diff_url:
        r2 = requests.get(diff_url, headers={"Authorization": f"token {token}", "User-Agent": "ai-bot"})
        r2.raise_for_status()
        return r2.text
    r3 = requests.get(url, headers={**headers, "Accept": "application/vnd.github.v3.diff"})
    r3.raise_for_status()
    return r3.text

def generate_review(diff_text):
    snippet = "\n".join(diff_text.splitlines()[:40])
    mock = (
        "### Automated Review (Local)\n\n"
        "This is a mock review generated for testing.\n\n"
        "**Quick Suggestions (example):**\n"
        "- Check for missing headers/includes and compile errors.\n"
        "- Validate any array indexing for out-of-bounds.\n"
        "- Add error checks around I/O.\n\n"
        "**Diff Snippet:**\n```\n" + snippet + "\n```\n\n"
    )
    return mock

def main():
    print("Starting PR review bot. Monitoring for new or updated PRs...")
    last_prs = set()  # Track processed PRs to avoid duplicates

    while True:
        try:
            prs = get_open_prs()
            current_prs = {pr["number"] for pr in prs}

            # Check for new or updated PRs
            new_prs = current_prs - last_prs
            if new_prs:
                for pr_number in new_prs:
                    print(f"\nDetected new PR: {owner}/{repo}#{pr_number}")
                    diff = fetch_pr_diff(owner, repo, pr_number, GITHUB_TOKEN)
                    if diff.strip():
                        review_text = generate_review(diff)
                        print("Review Output:\n", review_text)
                    else:
                        print("No diff content for PR.")
            
            last_prs = current_prs
        except Exception as e:
            print("Error:", e)
        
        time.sleep(POLL_INTERVAL)  # Wait before next check

if __name__ == "__main__":
    main()