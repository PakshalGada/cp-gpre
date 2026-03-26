import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

UTC = timezone.utc
from pathlib import Path

OLLAMA_BASE = "http://localhost:11434"
MATH_MODEL = "cp-math"
CODE_MODEL = "cp-code"
TOPICS_FILE = "../../data/topics.json"
OUTPUT_FILE = "../../data/db.json"
LOG_FILE = "data/pipeline.log"
RETRY_LIMIT = 3
RETRY_DELAY = 5  # seconds between retries
SWAP_WAIT = 2  # seconds to pause after a model swap


def _post(endpoint: str, body: dict, timeout: int = 120) -> dict:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{OLLAMA_BASE}{endpoint}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def ollama_chat(model: str, prompt: str, num_predict: int = 3000) -> str:
    result = _post(
        "/api/chat",
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"num_predict": num_predict},
        },
    )
    return result["message"]["content"].strip()


def ollama_alive() -> bool:
    try:
        urllib.request.urlopen(f"{OLLAMA_BASE}/api/tags", timeout=5)
        return True
    except Exception:
        return False


def model_exists(name: str) -> bool:
    try:
        req = urllib.request.Request(f"{OLLAMA_BASE}/api/tags")
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read().decode())
        return any(m["name"].startswith(name) for m in data.get("models", []))
    except Exception:
        return False


def extract_json(raw: str) -> dict:
    # Strip <think>...</think> blocks (deepseek-r1 chain-of-thought)
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    # Strip markdown fences
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    # Find outermost braces
    s, e = raw.find("{"), raw.rfind("}")
    if s == -1 or e == -1:
        raise ValueError(f"No JSON found in:\n{raw[:300]}")
    fragment = raw[s : e + 1]
    fragment = re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", fragment)
    return json.loads(fragment)


MATH_PROMPT = """\
You are writing a high-quality reference guide entry for competitive programmers.
Write for an audience that knows C++ and basic algorithms but may be seeing this topic for the first time.

Topic    : {title}
Category : {category}
Tags     : {tags}
Prereqs  : {prereqs}

Return ONLY a valid JSON object with exactly these keys. No preamble, no markdown fences.

{{
  "description": "3-5 sentences. Define the concept precisely: what structure/algorithm it is, what computational problem it solves, and when you would reach for it in a contest. Be specific, not generic.",

  "explanation": "3-6 paragraphs of flowing prose. Walk through the idea from scratch as if teaching it. Cover: the problem it solves, the naive approach and why it is slow, the key observation that enables the faster approach, and how the algorithm exploits that observation step by step. Use concrete small examples with actual numbers inline (e.g. array [3,1,4,1,5]). Use LaTeX for all math.",

  "proof": "A rigorous correctness or optimality argument. Structure it as numbered steps: 1) state the invariant or claim, 2) prove the base case, 3) prove the inductive step or greedy exchange argument, 4) conclude. Use LaTeX. If the algorithm is a heuristic with no formal proof write exactly: N/A",

  "worked_example": "A complete hand-trace on a small concrete input. Show the state of all data structures at each step. For example for Dijkstra: show the priority queue and dist[] array after each extraction. Use a real example with 4-6 nodes/elements.",

  "time_complexity": "The final complexity in LaTeX, e.g. $O(n \\log n)$, followed by 2-3 sentences explaining WHY: what operation dominates, how many times it runs, what data structure gives that bound.",

  "space_complexity": "The final complexity in LaTeX followed by 1-2 sentences explaining what the space is used for.",

  "variants": ["Each variant as a sentence: name + what it changes + when to use it. At least 2 entries if they exist."],

  "pitfalls": ["Each pitfall as a concrete actionable sentence. Cover: off-by-one errors, overflow issues, wrong edge case handling, common misconceptions. At least 3 entries."],

  "when_to_use": "2-3 sentences describing the contest problem patterns that signal this algorithm. What does the problem statement look like? What constraints (n <= 10^5, queries, etc.) suggest this approach?",

  "key_insight": "One sentence. The single core idea that makes this algorithm work — the aha moment. Not a description of the algorithm, but the insight that enables it."
}}
"""

CODE_PROMPT = """\
You are writing the code section of a high-quality competitive programming reference guide.

Topic    : {title}
Category : {category}
Tags     : {tags}
Prereqs  : {prereqs}

The explanation and proof for this topic are:
{math_context}

Return ONLY a valid JSON object with exactly these keys. No preamble, no markdown fences.

{{
  "cpp": "A complete, correct, contest-ready C++17 implementation. Requirements:\\n- Complexity comment block at the very top (Time + Space)\\n- Section comments dividing the code into logical parts (e.g. // --- build adjacency list ---)\\n- Inline comments on every non-obvious line explaining WHY, not just what\\n- Prefer STL containers. Use long long where overflow is possible.\\n- No main(). Self-contained: include any helper structs/typedefs needed.",

  "walkthrough": "A paragraph-by-paragraph explanation of the code above. Go section by section: explain what each block does and how it maps to the algorithm steps from the explanation. This should make the code completely transparent to a reader who just read the explanation.",

  "dry_run": "Trace the code on the same worked example from the explanation. Show variable values at key lines. Format as: 'Line X: var = value, meaning ...' This should match the worked_example from the math section.",

  "template_type": "One of: function | struct | class | global",

  "complexity_note": "Time: O(...) — Space: O(...)",

  "usage_example": "A short but complete C++ snippet (5-15 lines) showing how to call this in a real contest: read input, build the structure, call the function, print output. Use realistic variable names.",

  "cpp_notes": ["At least 3 entries. Cover: subtle implementation details, when to swap to a different variant, common TLE causes, memory layout tips, C++ specific gotchas like signed/unsigned comparison or iterator invalidation."]
}}
"""


def process(topic: dict, last_model: list) -> dict:
    slug = topic["slug"]
    title = topic["title"]
    tags = ", ".join(topic.get("tags", []))
    prereqs = ", ".join(topic.get("prereqs", [])) or "None"

    log(f"  [{slug}] math model...")
    math_data = None
    for attempt in range(1, RETRY_LIMIT + 1):
        try:
            raw = ollama_chat(
                MATH_MODEL,
                MATH_PROMPT.format(
                    title=title,
                    category=topic["category"],
                    tags=tags,
                    prereqs=prereqs,
                ),
                num_predict=3000,
            )
            math_data = extract_json(raw)
            break
        except Exception as exc:
            log(f"  [{slug}] math attempt {attempt} failed: {exc}")
            if attempt < RETRY_LIMIT:
                time.sleep(RETRY_DELAY)

    if math_data is None:
        math_data = {
            "description": "GENERATION_FAILED",
            "explanation": "",
            "proof": "",
            "worked_example": "",
            "time_complexity": "",
            "space_complexity": "",
            "variants": [],
            "pitfalls": [],
            "when_to_use": "",
            "key_insight": "",
        }

    # Model swap pause
    if last_model[0] != CODE_MODEL:
        time.sleep(SWAP_WAIT)
        last_model[0] = CODE_MODEL

    log(f"  [{slug}] code model...")
    math_context = (
        f"Description: {math_data.get('description', '')}\n\n"
        f"Explanation: {math_data.get('explanation', '')}\n\n"
        f"Proof: {math_data.get('proof', '')}\n\n"
        f"Worked example: {math_data.get('worked_example', '')}"
    )

    code_data = None
    for attempt in range(1, RETRY_LIMIT + 1):
        try:
            raw = ollama_chat(
                CODE_MODEL,
                CODE_PROMPT.format(
                    title=title,
                    category=topic["category"],
                    tags=tags,
                    prereqs=prereqs,
                    math_context=math_context,
                ),
                num_predict=3000,
            )
            code_data = extract_json(raw)
            break
        except Exception as exc:
            log(f"  [{slug}] code attempt {attempt} failed: {exc}")
            if attempt < RETRY_LIMIT:
                time.sleep(RETRY_DELAY)

    if code_data is None:
        code_data = {
            "cpp": "// GENERATION_FAILED",
            "walkthrough": "",
            "dry_run": "",
            "template_type": "unknown",
            "complexity_note": "",
            "usage_example": "",
            "cpp_notes": [],
        }

    # Swap back for next topic
    time.sleep(SWAP_WAIT)
    last_model[0] = MATH_MODEL

    return {
        "id": topic["id"],
        "slug": slug,
        "title": title,
        "category": topic["category"],
        "tags": topic.get("tags", []),
        "prereqs": topic.get("prereqs", []),
        "leads_to": topic.get("leads_to", []),
        "description": math_data.get("description", ""),
        "explanation": math_data.get("explanation", ""),
        "proof": math_data.get("proof", ""),
        "worked_example": math_data.get("worked_example", ""),
        "time_complexity": math_data.get("time_complexity", ""),
        "space_complexity": math_data.get("space_complexity", ""),
        "variants": math_data.get("variants", []),
        "pitfalls": math_data.get("pitfalls", []),
        "when_to_use": math_data.get("when_to_use", ""),
        "key_insight": math_data.get("key_insight", ""),
        "cpp": code_data.get("cpp", ""),
        "walkthrough": code_data.get("walkthrough", ""),
        "dry_run": code_data.get("dry_run", ""),
        "template_type": code_data.get("template_type", ""),
        "complexity_note": code_data.get("complexity_note", ""),
        "usage_example": code_data.get("usage_example", ""),
        "cpp_notes": code_data.get("cpp_notes", []),
        "generated_at": datetime.now(UTC).isoformat(),
        "math_model": MATH_MODEL,
        "code_model": CODE_MODEL,
    }


def load_db() -> dict:
    if not Path(OUTPUT_FILE).exists():
        return {}
    with open(OUTPUT_FILE) as f:
        return {e["slug"]: e for e in json.load(f)}


def save_db(db: dict):
    Path(OUTPUT_FILE).parent.mkdir(parents=True, exist_ok=True)
    entries = sorted(db.values(), key=lambda x: x["id"])
    with open(OUTPUT_FILE, "w") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)


_log_fh = None


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    if _log_fh:
        _log_fh.write(line + "\n")
        _log_fh.flush()


def main():
    global _log_fh

    parser = argparse.ArgumentParser(description="cp-gpre local model pipeline")
    parser.add_argument("--only", help="Process single topic by slug")
    parser.add_argument("--category", help="Process all topics in a category")
    parser.add_argument(
        "--from-id", type=int, default=1, help="Start from topic ID (inclusive)"
    )
    parser.add_argument(
        "--regen", action="store_true", help="Regenerate even if already done"
    )
    args = parser.parse_args()

    Path("data").mkdir(exist_ok=True)
    _log_fh = open(LOG_FILE, "a")

    # Startup checks
    if not ollama_alive():
        print("❌  Ollama is not running. Start it with:  ollama serve")
        sys.exit(1)

    for m in [MATH_MODEL, CODE_MODEL]:
        if not model_exists(m):
            mf = "math" if m == MATH_MODEL else "code"
            print(f"❌  Model '{m}' not found.")
            print(f"    Build it with:  ollama create {m} -f core/{mf}.Modelfile")
            sys.exit(1)

    # Load topics
    with open(TOPICS_FILE) as f:
        all_topics = json.load(f)

    # Filter
    if args.only:
        topics = [t for t in all_topics if t["slug"] == args.only]
        if not topics:
            print(f"❌  Slug '{args.only}' not found in {TOPICS_FILE}")
            sys.exit(1)
    elif args.category:
        topics = [
            t for t in all_topics if t["category"].lower() == args.category.lower()
        ]
        if not topics:
            print(f"❌  No topics for category '{args.category}'")
            sys.exit(1)
    else:
        topics = [t for t in all_topics if t["id"] >= args.from_id]

    db = load_db()
    pending = topics if args.regen else [t for t in topics if t["slug"] not in db]

    total = len(pending)
    done = len(topics) - total
    log("=== cp-gpre pipeline starting ===")
    log(f"Topics: {len(topics)}  |  already done: {done}  |  pending: {total}")
    log(f"Estimated time: ~{total * 60 // 60} minutes")

    if total == 0:
        log("Nothing to do. Use --regen to reprocess.")
        sys.exit(0)

    last_model = [MATH_MODEL]
    t0 = time.time()

    for i, topic in enumerate(pending, 1):
        log(f"\n[{i}/{total}] {topic['title']}  ({topic['category']})")
        try:
            entry = process(topic, last_model)
            db[topic["slug"]] = entry
            save_db(db)

            elapsed = time.time() - t0
            eta_min = (elapsed / i) * (total - i) / 60
            log(f"  ✓  saved  |  ETA {eta_min:.1f} min remaining")

        except KeyboardInterrupt:
            log("\n⚠️  Interrupted. Progress saved.")
            break
        except Exception as exc:
            log(f"  ✗  unexpected error: {exc}")
            continue

    log(f"\n=== Done. {len(db)} entries in {OUTPUT_FILE} ===")
    _log_fh.close()


if __name__ == "__main__":
    main()
