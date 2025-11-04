import os
from groq import Groq

# === Setup ===
groq_key = os.getenv("GROQ_API_KEY")
diff_path = os.getenv("DIFF_FILE", "diff.txt")
output_path = os.getenv("OUTPUT_FILE", "review_output.md")

if not groq_key:
    raise SystemExit("❌ Missing GROQ_API_KEY environment variable")

client = Groq(api_key=groq_key)

def chunk_text(text, max_chars=3500):
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

def generate_review(diff_chunk: str) -> str:
    prompt = f"""
You are an AI pull request reviewer.
Here is a code diff chunk from a PR:

{diff_chunk}

Write a structured review:
- Briefly summarize what this chunk changes
- Give at least 2 improvement suggestions
- Note any risks (bugs, performance, security)
Respond in markdown format.
"""
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=500
    )
    return response.choices[0].message.content

def main():
    with open(diff_path, "r", encoding="utf-8") as f:
        diff = f.read()

    chunks = chunk_text(diff)
    print(f"📦 Split diff into {len(chunks)} chunks")

    all_reviews = []
    for i, chunk in enumerate(chunks, 1):
        review = generate_review(chunk)
        all_reviews.append(f"### 🤖 AI Review (Part {i}/{len(chunks)})\n\n{review}")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n\n---\n\n".join(all_reviews))

    print(f"✅ Review saved to {output_path}")

if __name__ == "__main__":
    main()
