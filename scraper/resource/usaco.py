import argparse
import json
import os
import re
import sys
from pathlib import Path

LEVELS = {
    "1_General": {"id": "general", "label": "General", "order": 0},
    "2_Bronze": {"id": "bronze", "label": "Bronze", "order": 1},
    "3_Silver": {"id": "silver", "label": "Silver", "order": 2},
    "4_Gold": {"id": "gold", "label": "Gold", "order": 3},
    "5_Plat": {"id": "platinum", "label": "Platinum", "order": 4},
    "6_Advanced": {"id": "advanced", "label": "Advanced", "order": 5},
}

# Skip these files — they are meta/navigation pages, not algorithm topics
SKIP_FILES = {
    "Conclusion.mdx",
    "Modules.mdx",
    "Using_This_Guide.mdx",
    "Contributing.mdx",
    "Working_MDX.mdx",
    "Resources_CP.mdx",
    "Resources_USA-specific.mdx",
    "USACO_FAQs.mdx",
    "USACO_Camp.mdx",
    "USACO_Monthlies.mdx",
    "Olympiads.mdx",
    "Practicing.mdx",
}

REMOVE_ENTIRELY = {
    "JavaSection",
    "PySection",
    "FocusProblem",
    "CodeSnip",
    "Problems",
}

KEEP_CONTENT = {
    "LanguageSection",
    "CPPSection",
    "Spoiler",
    "Optional",
    "Details",
}

TO_BLOCKQUOTE = {
    "Info",
    "Warning",
    "Danger",
    "Note",
}


def remove_block(text: str, tag: str) -> str:
    """Remove an entire JSX block including its children."""
    # Self-closing: <Tag ... />
    text = re.sub(rf"<{tag}[^>]*/>", "", text)
    # Opening + closing pairs (handles nesting naively — good enough for these files)
    pattern = (rf"<{tag}(\s[^>]*)?>.*?</{tag}>",)
    text = re.sub(rf"<{tag}(\s[^>]*)?>.*?</{tag}>", "", text, flags=re.DOTALL)
    return text


def strip_tags_keep_content(text: str, tag: str) -> str:
    """Strip opening and closing JSX tags but keep everything between them."""
    # Remove opening tag (with optional attributes)
    text = re.sub(rf"<{tag}(\s[^>]*)?>", "", text)
    # Remove closing tag
    text = re.sub(rf"</{tag}>", "", text)
    # Remove self-closing
    text = re.sub(rf"<{tag}[^>]*/>", "", text)
    return text


def convert_to_blockquote(text: str, tag: str) -> str:
    """Wrap the content of a component in a markdown blockquote."""

    def replacer(m):
        inner = m.group(2).strip()
        # Prefix each line with >
        quoted = "\n".join(
            "> " + line if line.strip() else ">" for line in inner.split("\n")
        )
        return f"\n{quoted}\n"

    text = re.sub(rf"<{tag}(\s[^>]*)?>(.+?)</{tag}>", replacer, text, flags=re.DOTALL)
    return text


def convert_resource_tags(text: str) -> str:
    """
    Convert <Resource source="X" title="Y" url="Z">description</Resource>
    into a markdown link: - [Y](Z) (X) — description
    """

    def replacer(m):
        attrs = m.group(1)
        inner = m.group(2).strip()

        source = re.search(r'source=["\']([^"\']*)["\']', attrs)
        title = re.search(r'title=["\']([^"\']*)["\']', attrs)
        url = re.search(r'url=["\']([^"\']*)["\']', attrs)

        source = source.group(1) if source else ""
        title = title.group(1) if title else "Resource"
        url = url.group(1) if url else ""

        # If url is just a number it's a CF blog post ID
        if url.isdigit():
            url = f"https://codeforces.com/blog/entry/{url}"
        elif url and not url.startswith("http"):
            url = f"https://usaco.guide/{url}"

        desc = f" — {inner}" if inner else ""
        src = f" ({source})" if source else ""
        if url:
            return f"- [{title}]({url}){src}{desc}"
        else:
            return f"- **{title}**{src}{desc}"

    text = re.sub(
        r"<Resource(\s[^>]*)?>(.+?)</Resource>", replacer, text, flags=re.DOTALL
    )

    # Self-closing Resource tags
    def replacer_self(m):
        attrs = m.group(1)
        source = re.search(r'source=["\']([^"\']*)["\']', attrs)
        title = re.search(r'title=["\']([^"\']*)["\']', attrs)
        url = re.search(r'url=["\']([^"\']*)["\']', attrs)
        source = source.group(1) if source else ""
        title = title.group(1) if title else "Resource"
        url = url.group(1) if url else ""
        if url.isdigit():
            url = f"https://codeforces.com/blog/entry/{url}"
        src = f" ({source})" if source else ""
        if url:
            return f"- [{title}]({url}){src}"
        return f"- **{title}**{src}"

    text = re.sub(r"<Resource(\s[^>]*)/>", replacer_self, text)
    return text


def clean_mdx_content(raw: str) -> str:
    """
    Full MDX → clean Markdown pipeline.
    Processes the body (after frontmatter is stripped).
    """
    text = raw

    # 1. Remove entirely: Java, Python sections, Problems tables, FocusProblem
    for tag in REMOVE_ENTIRELY:
        text = remove_block(text, tag)

    # 2. Convert Info/Warning/Danger blocks to blockquotes
    for tag in TO_BLOCKQUOTE:
        text = convert_to_blockquote(text, tag)

    # 3. Convert <Resource> tags to markdown links
    text = convert_resource_tags(text)

    # 4. Strip <Resources> wrapper tags (keep the list items inside)
    text = strip_tags_keep_content(text, "Resources")

    # 5. Strip LanguageSection/CPPSection/Spoiler/Optional wrapper tags
    for tag in KEEP_CONTENT:
        text = strip_tags_keep_content(text, tag)

    # 6. Remove any remaining unknown JSX opening/closing tags
    #    (catches anything we missed — strip tags but keep inner text)
    text = re.sub(r"<[A-Z][A-Za-z]*(\s[^>]*)?>", "", text)  # opening tags
    text = re.sub(r"</[A-Z][A-Za-z]*>", "", text)  # closing tags
    text = re.sub(r"<[A-Z][A-Za-z]*/>", "", text)  # self-closing

    # 7. Remove import statements (MDX-specific)
    text = re.sub(r"^import\s+.*$", "", text, flags=re.MULTILINE)

    # 8. Fix internal USACO guide links: [text](/module/slug) → [text](usaco.guide/module/slug)
    text = re.sub(
        r"\[([^\]]+)\]\(/([^)]+)\)",
        lambda m: f"[{m.group(1)}](https://usaco.guide/{m.group(2)})",
        text,
    )

    # 9. Clean up: collapse 3+ blank lines into 2, strip trailing spaces
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)
    text = text.strip()

    return text


# ─────────────────────────────────────────────────────────────
#  FRONTMATTER PARSER
# ─────────────────────────────────────────────────────────────


def parse_frontmatter(raw: str) -> tuple[dict, str]:
    """
    Split a file into (frontmatter_dict, body_string).
    Frontmatter is the YAML block between the first pair of --- lines.
    Returns ({}, raw) if no frontmatter found.
    """
    if not raw.startswith("---"):
        return {}, raw

    end = raw.find("\n---", 3)
    if end == -1:
        return {}, raw

    fm_block = raw[3:end].strip()
    body = raw[end + 4 :].strip()

    fm = {}
    current_key = None
    current_list = None

    for line in fm_block.split("\n"):
        # List item
        if line.startswith("  - ") or line.startswith("- "):
            item = line.strip().lstrip("- ").strip()
            if current_list is not None:
                current_list.append(item)
            continue

        # Key: value
        if ":" in line:
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip().strip("'\"")

            if val == "":
                # This key starts a list on the next lines
                current_list = []
                fm[key] = current_list
                current_key = key
            else:
                current_list = None
                current_key = key
                fm[key] = val

    return fm, body


def load_problems(mdx_path: Path) -> list:
    """
    Load the sidecar .problems.json file for a given .mdx file.
    Returns a list of simplified problem dicts.
    """
    problems_path = mdx_path.with_suffix("").with_suffix(".problems.json")
    # e.g. DSU.mdx → DSU.problems.json
    # pathlib: DSU.mdx → stem=DSU → DSU.problems.json
    problems_path = mdx_path.parent / (mdx_path.stem + ".problems.json")

    if not problems_path.exists():
        return []

    try:
        with open(problems_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []

    problems = []

    if isinstance(data, dict):
        for section_name, problem_list in data.items():
            if not isinstance(problem_list, list):
                continue
            for p in problem_list:
                if not isinstance(p, dict):
                    continue
                problems.append(
                    {
                        "uniqueId": p.get("uniqueId", ""),
                        "name": p.get("name", ""),
                        "url": p.get("url", ""),
                        "source": p.get("source", ""),
                        "difficulty": p.get("difficulty", ""),
                        "isStarred": p.get("isStarred", False),
                        "tags": p.get("tags", []),
                        "section": section_name,
                    }
                )
    elif isinstance(data, list):
        for p in data:
            if not isinstance(p, dict):
                continue
            problems.append(
                {
                    "uniqueId": p.get("uniqueId", ""),
                    "name": p.get("name", ""),
                    "url": p.get("url", ""),
                    "source": p.get("source", ""),
                    "difficulty": p.get("difficulty", ""),
                    "isStarred": p.get("isStarred", False),
                    "tags": p.get("tags", []),
                    "section": "",
                }
            )

    return problems


# ─────────────────────────────────────────────────────────────
#  EXTRACT SECTION HEADINGS
# ─────────────────────────────────────────────────────────────


def extract_sections(content: str) -> list:
    """Extract all ## headings from cleaned content as a table of contents."""
    sections = []
    for m in re.finditer(r"^#{1,3}\s+(.+)$", content, re.MULTILINE):
        level = len(m.group(0)) - len(m.group(0).lstrip("#"))
        sections.append(
            {
                "level": level,
                "title": m.group(1).strip(),
            }
        )
    return sections


def parse_mdx_file(path: Path, level_meta: dict, topic_order: int) -> dict:
    """
    Parse one .mdx file into a structured topic dict.
    """
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()

    frontmatter, body = parse_frontmatter(raw)
    clean_content = clean_mdx_content(body)
    problems = load_problems(path)
    sections = extract_sections(clean_content)

    # Derive a slug from filename if frontmatter id is missing
    topic_id = frontmatter.get("id") or path.stem.lower().replace("_", "-")

    # prerequisites can be a list or a single string
    prereqs = frontmatter.get("prerequisites", [])
    if isinstance(prereqs, str):
        prereqs = [prereqs] if prereqs else []

    # Word count for estimated reading time (roughly 200 words/min for technical content)
    word_count = len(clean_content.split())
    reading_time = max(5, round(word_count / 200) * 5)  # round to nearest 5 min

    return {
        # ── Identity ──────────────────────────────────────────
        "id": topic_id,
        "title": frontmatter.get("title", path.stem.replace("_", " ")),
        "source": "usaco",
        # ── Difficulty / ordering ─────────────────────────────
        "level": level_meta["id"],  # bronze / silver / gold / etc.
        "level_label": level_meta["label"],
        "level_order": level_meta["order"],  # 0–5 for sorting
        "topic_order": topic_order,  # position within the level
        # ── Frontmatter metadata ──────────────────────────────
        "description": frontmatter.get("description", ""),
        "author": frontmatter.get("author", ""),
        "contributors": frontmatter.get("contributors", ""),
        "prerequisites": prereqs,
        # ── Content ───────────────────────────────────────────
        "content": clean_content,
        "sections": sections,  # table of contents
        # ── Practice problems ─────────────────────────────────
        "problems": problems,
        "problem_count": len(problems),
        # ── Metadata ─────────────────────────────────────────
        "estimated_time": f"{reading_time} min",
        "word_count": word_count,
        "filename": path.name,
        "tags": [],  # populated below
    }


# ─────────────────────────────────────────────────────────────
#  AUTO-TAG FROM TITLE + CONTENT
# ─────────────────────────────────────────────────────────────

TAG_PATTERNS = [
    ("binary-search", ["binary search"]),
    ("graphs", ["graph", "bfs", "dfs", "breadth", "depth"]),
    ("shortest-path", ["shortest path", "dijkstra", "bellman", "floyd"]),
    ("trees", ["tree", "lca", "euler tour", "hld", "centroid"]),
    ("dp", ["dynamic programming", " dp ", "knapsack", "lis", "lcs"]),
    (
        "data-structures",
        ["segment tree", "fenwick", "dsu", "union find", "sparse table", "treap"],
    ),
    ("strings", ["string", "hashing", "kmp", "z-function", "suffix", "trie", "aho"]),
    ("math", ["modular", "prime", "sieve", "gcd", "combinatorics", "number theory"]),
    ("geometry", ["geometry", "convex hull", "polygon", "intersection"]),
    ("greedy", ["greedy"]),
    ("sorting", ["sort", "comparator"]),
    ("flow", ["flow", "matching", "bipartite"]),
    ("bitmask", ["bitmask", "bitmask dp", "sos dp"]),
    ("two-pointers", ["two pointer", "sliding window"]),
    ("prefix-sums", ["prefix sum"]),
]


def assign_tags(topic: dict) -> list:
    text = (
        topic["title"] + " " + topic["description"] + " " + topic["content"][:300]
    ).lower()
    tags = []
    for tag, keywords in TAG_PATTERNS:
        if any(kw in text for kw in keywords):
            tags.append(tag)
    return tags


def parse_usaco(input_dir: Path) -> dict:
    """
    Walk the usaco-guide directory and parse all MDX files.
    Returns the full structured output dict.
    """
    if not input_dir.exists():
        print(f"Error: Directory not found: {input_dir}")
        sys.exit(1)

    levels_output = []
    total_topics = 0
    total_problems = 0

    # Walk folders in level order
    for folder_name, level_meta in LEVELS.items():
        folder_path = input_dir / folder_name
        if not folder_path.exists():
            print(f"  ⚠ Folder not found, skipping: {folder_name}")
            continue

        mdx_files = sorted(folder_path.glob("*.mdx"))
        topics = []
        order = 0

        print(f"\n{'─' * 50}")
        print(f"  {level_meta['label']} ({folder_name})")
        print(f"{'─' * 50}")

        for mdx_path in mdx_files:
            # Skip meta files
            if mdx_path.name in SKIP_FILES:
                print(f"  ⊘ skip  {mdx_path.name}")
                continue

            # Skip .problems.json files (they're sidecars)
            if mdx_path.suffix != ".mdx":
                continue

            try:
                topic = parse_mdx_file(mdx_path, level_meta, order)
                topic["tags"] = assign_tags(topic)
                topics.append(topic)
                order += 1

                prob_str = (
                    f"  ({topic['problem_count']} problems)"
                    if topic["problem_count"]
                    else ""
                )
                print(
                    f"  ✓ [{order:02d}] {topic['title']:<40} {topic['estimated_time']}{prob_str}"
                )

            except Exception as e:
                print(f"  ✗ ERROR parsing {mdx_path.name}: {e}")
                import traceback

                traceback.print_exc()

        total_topics += len(topics)
        total_problems += sum(t["problem_count"] for t in topics)

        levels_output.append(
            {
                "id": level_meta["id"],
                "label": level_meta["label"],
                "order": level_meta["order"],
                "topic_count": len(topics),
                "topics": topics,
            }
        )

    return {
        "meta": {
            "source": "usaco-guide",
            "total_topics": total_topics,
            "total_problems": total_problems,
            "levels": len(levels_output),
        },
        "levels": levels_output,
    }


def print_summary(data: dict):
    meta = data["meta"]
    print(f"\n{'═' * 55}")
    print(f"  USACO Parse Summary")
    print(f"{'═' * 55}")
    print(f"  Total topics:    {meta['total_topics']}")
    print(f"  Total problems:  {meta['total_problems']}")
    print()
    for level in data["levels"]:
        print(f"  {level['label']:<12}  {level['topic_count']:>3} topics")
    print(f"{'═' * 55}")


def main():
    parser = argparse.ArgumentParser(
        description="Parse USACO Guide MDX files into structured JSON"
    )
    parser.add_argument(
        "--input",
        "-i",
        default="./data/raw/usaco-guide",
        help="Path to usaco-guide content directory (default: ./data/raw/usaco-guide)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="./data/knowledgeBase/usaco.json",
        help="Output JSON file path (default: ./data/knowledgeBase/usaco.json)",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="JSON indentation spaces (default: 2, use 0 for compact)",
    )
    args = parser.parse_args()

    input_dir = Path(args.input)
    output_path = Path(args.output)

    print(f"\n📂 Input:  {input_dir.resolve()}")
    print(f"📄 Output: {output_path.resolve()}")

    data = parse_usaco(input_dir)

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    indent = args.indent if args.indent > 0 else None
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)

    size_kb = output_path.stat().st_size // 1024
    print(f"\n✓ Written → {output_path}  ({size_kb} KB)")
    print_summary(data)


if __name__ == "__main__":
    main()
