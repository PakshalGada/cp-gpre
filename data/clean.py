import argparse
import json
import re
from collections import Counter
from pathlib import Path

DATA_DIR = Path(__file__).parent  # data/
KB_DIR = DATA_DIR / "knowledgeBase"
INPUT_PATH = KB_DIR / "corpus.json"
OUTPUT_PATH = KB_DIR / "corpus_clean.json"


JUNK_LINE_PATTERNS = [
    # Navigation / breadcrumbs
    re.compile(r"^(Home|Algorithms|Problems|Solutions)\s*(>|›|→)"),
    re.compile(r"^(Previous|Next|Back|Skip to content)\s*$", re.I),
    re.compile(r"^(Table of Contents|Contents|Index)\s*$", re.I),
    re.compile(r"^(Edit this page|Edit on GitHub|View source)\s*$", re.I),
    re.compile(r"^(Share|Tweet|Copy link)\s*$", re.I),
    re.compile(r"^(Comments|Discuss|Feedback)\s*$", re.I),
    # PDF artifacts
    re.compile(r"^—\s*\d+\s*—$"),  # — 47 —
    re.compile(r"^\s*\d{1,3}\s*$"),  # lone page number
    re.compile(r"^Competitive Programmer.?s Handbook", re.I),
    re.compile(r"^CHAPTER\s+\d+", re.I),
    re.compile(r"^cp-algorithms\.com", re.I),
    re.compile(r"^cses\.fi", re.I),
    # Copyright / metadata
    re.compile(r"^©.*\d{4}"),
    re.compile(r"^All rights reserved", re.I),
    re.compile(r"^Last (updated|modified|edited):", re.I),
    # UI chrome that leaked
    re.compile(r"^(Search|Menu|Toggle|Dark mode|Light mode)\s*$", re.I),
    re.compile(r"^\s*\[.*?\]\s*$"),  # lone [button text]
]

DIFFICULTY_KEYWORDS = {
    "beginner": [
        "brute force",
        "complete search",
        "for loop",
        "array",
        "input output",
        "time complexity",
        "big o",
        "sorting",
        "binary search",
        "prefix sum",
        "two pointer",
        "greedy",
        "gcd",
        "lcm",
        "prime",
        "sieve",
    ],
    "intermediate": [
        "dynamic programming",
        "bfs",
        "dfs",
        "dijkstra",
        "bellman",
        "union find",
        "dsu",
        "topological",
        "knapsack",
        "lis",
        "lcs",
        "hashing",
        "sparse table",
        "segment tree",
        "fenwick",
        "binary indexed",
    ],
    "advanced-intermediate": [
        "lazy propagation",
        "lca",
        "binary lifting",
        "kmp",
        "z-function",
        "merge sort tree",
        "sqrt decomposition",
        "offline queries",
        "floyd warshall",
        "mst",
        "kruskal",
        "prim",
    ],
    "advanced": [
        "heavy light decomposition",
        "centroid decomposition",
        "suffix array",
        "suffix automaton",
        "aho corasick",
        "max flow",
        "min cut",
        "dinic",
        "convex hull trick",
        "persistent segment",
        "2-sat",
        "scc",
        "bridges",
        "articulation",
        "li chao",
    ],
    "expert": [
        "fft",
        "ntt",
        "polynomial",
        "treap",
        "splay",
        "link cut tree",
        "mo algorithm",
        "xor basis",
        "matroid",
        "parallel binary search",
        "virtual tree",
        "min cost flow",
        "hall theorem",
        "dilworth",
    ],
}

# Reverse map: keyword → difficulty
_KW_TO_DIFF: dict[str, str] = {}
for _diff, _kws in DIFFICULTY_KEYWORDS.items():
    for _kw in _kws:
        _KW_TO_DIFF[_kw] = _diff

DIFFICULTY_ORDER = [
    "beginner",
    "intermediate",
    "advanced-intermediate",
    "advanced",
    "expert",
]


def clean_junk_lines(text: str) -> str:
    """Remove lines matching junk patterns."""
    lines = text.splitlines()
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if any(p.search(stripped) for p in JUNK_LINE_PATTERNS):
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


def clean_whitespace(text: str) -> str:
    """Collapse excessive blank lines and trailing spaces."""
    # Normalise line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Collapse 3+ blank lines → 2  (but not inside code fences)
    lines = text.splitlines()
    result = []
    blank_run = 0
    in_code = False

    for line in lines:
        if line.strip().startswith("```"):
            in_code = not in_code

        if not in_code and not line.strip():
            blank_run += 1
            if blank_run <= 2:
                result.append("")
        else:
            blank_run = 0
            # Strip trailing spaces from non-code lines
            result.append(line.rstrip() if not in_code else line)

    return "\n".join(result).strip()


def clean_nav_artifacts(text: str) -> str:
    """
    Remove multi-word navigation strings that span a line.
    e.g. 'Home > Algebra > Sieve of Eratosthenes'
    """
    text = re.sub(r"^.*?(>|›|→).*$", "", text, flags=re.MULTILINE)
    return text


def clean_pdf_header_repeats(text: str) -> str:
    """
    PDF headers often repeat every N lines. Detect and remove them.
    Strategy: if the exact same short line (< 60 chars) appears 4+ times,
    remove all occurrences.
    """
    lines = text.splitlines()
    counts = Counter(l.strip() for l in lines if 3 < len(l.strip()) < 60)
    repeated = {line for line, count in counts.items() if count >= 4}

    if not repeated:
        return text

    cleaned = [l for l in lines if l.strip() not in repeated]
    return "\n".join(cleaned)


def clean_lone_short_lines(text: str) -> str:
    """
    Remove lines with 1–2 words that are not headings or list items.
    These are usually stray labels, button text, or PDF column headers.
    """
    lines = text.splitlines()
    result = []
    in_code = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code = not in_code

        if in_code:
            result.append(line)
            continue

        words = stripped.split()
        # Keep: headings (#), list items (- / 1.), empty lines, lines 3+ words
        if (
            not stripped
            or stripped.startswith("#")
            or stripped.startswith("-")
            or stripped.startswith("*")
            or re.match(r"^\d+\.", stripped)
            or len(words) >= 3
        ):
            result.append(line)
        # Drop: 1–2 word non-heading lines

    return "\n".join(result)


def infer_difficulty(text: str, current: str) -> str:
    """
    If difficulty is 'unknown', scan text for curriculum keywords
    and assign the most advanced level found.
    Returns the existing difficulty if it's already set.
    """
    if current and current != "unknown":
        return current

    text_lower = text.lower()
    found_levels: list[str] = []

    for kw, diff in _KW_TO_DIFF.items():
        if kw in text_lower:
            found_levels.append(diff)

    if not found_levels:
        return "intermediate"  # safe default for CP content

    # Return the most advanced level found
    best = max(
        found_levels,
        key=lambda d: DIFFICULTY_ORDER.index(d) if d in DIFFICULTY_ORDER else 0,
    )
    return best


def detect_has_code(text: str) -> bool:
    """True if the text contains a fenced code block."""
    return "```" in text


def clean_text(text: str) -> str:
    """Apply all text-level cleaners in order."""
    text = clean_nav_artifacts(text)
    text = clean_junk_lines(text)
    text = clean_pdf_header_repeats(text)
    text = clean_lone_short_lines(text)
    text = clean_whitespace(text)
    return text


def clean_doc(doc: dict) -> dict | None:
    """
    Clean a single document dict.
    Returns the cleaned doc, or None if it should be dropped.
    """
    # Skip the metadata header doc
    if doc.get("__meta__"):
        return doc

    for key in ("doc_id", "title", "url", "source", "text"):
        if not doc.get(key):
            return None  # drop: missing required field

    text = clean_text(doc["text"])

    word_count = len(text.split())
    if word_count < 60:
        return None  # drop: too short to be useful

    doc = dict(doc)  # don't mutate original
    doc["text"] = text
    doc["title"] = clean_title(doc["title"])
    text = clean_first_line_artifact(text)
    doc["word_count"] = word_count
    doc["has_code"] = detect_has_code(text)
    doc["difficulty"] = infer_difficulty(text, doc.get("difficulty", "unknown"))

    return doc


def clean_title(title: str) -> str:
    return title.replace("¶", "").strip()


def clean_first_line_artifact(text: str) -> str:
    lines = text.splitlines()
    if lines and (
        "contribution" in lines[0].lower()
        or "last commit" in lines[0].lower()
        or "author" in lines[0].lower()
    ):
        lines = lines[1:]
    return "\n".join(lines)


def clean_corpus(
    docs: list[dict],
    show_dropped: bool = False,
) -> tuple[list[dict], dict]:
    """
    Clean all docs.
    Returns (cleaned_docs, stats_dict).
    """
    cleaned: list[dict] = []
    dropped: list[dict] = []
    seen_ids: set[str] = set()

    for doc in docs:
        if doc.get("__meta__"):
            cleaned.append(doc)
            continue

        result = clean_doc(doc)

        if result is None:
            dropped.append(doc)
            if show_dropped:
                print(
                    f"  DROP (too short / missing field): {doc.get('doc_id', '?')[:60]}"
                )
            continue

        did = result["doc_id"]
        if did in seen_ids:
            dropped.append(doc)
            if show_dropped:
                print(f"  DROP (duplicate id): {did[:60]}")
            continue
        seen_ids.add(did)

        cleaned.append(result)

    real_docs = [d for d in cleaned if not d.get("__meta__")]
    stats = {
        "total_in": len(docs) - 1,  # exclude meta header
        "total_out": len(real_docs),
        "dropped": len(dropped),
        "with_code": sum(1 for d in real_docs if d.get("has_code")),
        "by_source": dict(Counter(d["source"] for d in real_docs)),
        "by_difficulty": dict(Counter(d["difficulty"] for d in real_docs)),
        "total_words": sum(d.get("word_count", 0) for d in real_docs),
    }
    return cleaned, stats


def print_stats(stats: dict) -> None:
    print(f"\n  ╔══════════════════════════════════════════╗")
    print(f"  ║  Input docs    : {stats['total_in']:<6}                  ║")
    print(f"  ║  Output docs   : {stats['total_out']:<6}                  ║")
    print(f"  ║  Dropped       : {stats['dropped']:<6}                  ║")
    print(f"  ║  Total words   : {stats['total_words']:<10,}            ║")
    print(f"  ║  With code     : {stats['with_code']:<6}                  ║")
    print(f"  ╚══════════════════════════════════════════╝")

    print(f"\n  By source:")
    for src, n in sorted(stats["by_source"].items(), key=lambda x: -x[1]):
        bar = "▓" * (n * 25 // max(stats["by_source"].values(), default=1))
        print(f"    {src:<25s}  {bar:<25s}  {n}")

    print(f"\n  By difficulty:")
    for diff in DIFFICULTY_ORDER:
        n = stats["by_difficulty"].get(diff, 0)
        if n:
            bar = "▓" * (n * 25 // max(stats["by_difficulty"].values(), default=1))
            print(f"    {diff:<25s}  {bar:<25s}  {n}")


def main(
    input_path: Path = INPUT_PATH,
    output_path: Path = OUTPUT_PATH,
    show_dropped: bool = False,
) -> None:

    if not input_path.exists():
        print(f"  ✗  Input not found: {input_path}")
        print(f"     Run the scraper first:  python -m scraper.base")
        return

    print(f"\n  Loading {input_path} …")
    with open(input_path, encoding="utf-8") as f:
        docs = json.load(f)

    print(f"  Loaded {len(docs)} entries (including meta header)")

    print(f"\n  Cleaning …")
    cleaned, stats = clean_corpus(docs, show_dropped=show_dropped)

    print_stats(stats)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2)

    size_mb = output_path.stat().st_size / 1e6
    print(f"\n  ✓  Saved → {output_path}  ({size_mb:.1f} MB)")
    print(f"\n  Next step: run the chunker on corpus_clean.json")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="cp-gpre corpus cleaner")
    p.add_argument(
        "--input",
        default=str(INPUT_PATH),
        help=f"Input corpus JSON  (default: {INPUT_PATH})",
    )
    p.add_argument(
        "--output",
        default=str(OUTPUT_PATH),
        help=f"Output path  (default: {OUTPUT_PATH})",
    )
    p.add_argument(
        "--show-dropped",
        action="store_true",
        help="Print every doc that gets removed and why",
    )
    args = p.parse_args()

    main(
        input_path=Path(args.input),
        output_path=Path(args.output),
        show_dropped=args.show_dropped,
    )
