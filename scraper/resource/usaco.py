import re
import subprocess
from pathlib import Path

REPO_URL = "https://github.com/cpinitiative/usaco-guide.git"

DIFFICULTY_MAP = {
    "bronze": "beginner",
    "silver": "intermediate",
    "gold": "advanced-intermediate",
    "platinum": "advanced",
    "advanced": "expert",
    "general": "beginner",
    "intro": "beginner",
}

CATEGORY_MAP = {
    "sorting": "sorting",
    "binary": "binary-search",
    "graph": "graphs",
    "tree": "trees",
    "dp": "dp",
    "dynamic": "dp",
    "string": "strings",
    "math": "math",
    "segment": "data-structures",
    "flow": "graphs",
    "hashing": "strings",
    "geometry": "geometry",
}


def _strip_mdx(text: str) -> str:
    """Remove JSX/React syntax, keep pure markdown."""
    # Remove import and export lines
    text = re.sub(r"^import\s+.*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^export\s+.*$", "", text, flags=re.MULTILINE)
    # Remove self-closing JSX  <Tag ... />
    text = re.sub(r"<[A-Z][A-Za-z]*[^>]*/\s*>", "", text)
    # Remove paired JSX blocks  <Tag>...</Tag>
    text = re.sub(r"<([A-Z][A-Za-z]*)[^>]*>.*?</\1>", "", text, flags=re.DOTALL)
    # Remove JSX comments  {/* ... */}
    text = re.sub(r"\{/\*.*?\*/\}", "", text, flags=re.DOTALL)
    # Collapse blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _parse_frontmatter(raw: str) -> tuple[str, str]:
    """
    Extract title from YAML frontmatter.
    Returns (title, body_without_frontmatter).
    """
    title = ""
    body = raw

    if raw.startswith("---"):
        end = raw.find("---", 3)
        if end != -1:
            fm = raw[3:end]
            body = raw[end + 3 :].strip()
            for line in fm.splitlines():
                if line.strip().startswith("title:"):
                    title = line.split(":", 1)[1].strip().strip("\"'")
                    break

    return title, body


def _difficulty(path_str: str) -> str:
    lower = path_str.lower().replace("\\", "/")
    for folder, diff in DIFFICULTY_MAP.items():
        if f"/{folder}/" in lower or lower.startswith(folder):
            return diff
    return "unknown"


def _category(path_str: str) -> str:
    lower = path_str.lower()
    for kw, cat in CATEGORY_MAP.items():
        if kw in lower:
            return cat
    return "misc"


def _ensure_repo(repo_dir: Path) -> bool:
    if repo_dir.exists():
        print(f"[usaco] Repo already at {repo_dir}")
        return True
    print(f"[usaco] Cloning USACO Guide into {repo_dir} …")
    try:
        subprocess.run(
            ["git", "clone", "--depth=1", REPO_URL, str(repo_dir)],
            check=True,
            timeout=300,
        )
        return True
    except Exception as e:
        print(f"[usaco] Clone failed: {e}")
        return False


def scrape(repo_dir: str = "data/raw/usaco-guide") -> list[dict]:
    """
    Walk all .mdx files in the USACO Guide repo and return doc dicts.
    Each dict has: doc_id, title, url, source, category, difficulty, text.
    """
    repo = Path(repo_dir)

    if not _ensure_repo(repo):
        return []

    content_dir = repo / "content"
    if not content_dir.exists():
        print(f"[usaco] content/ not found inside {repo}")
        return []

    mdx_files = sorted(content_dir.rglob("*.mdx"))
    print(f"[usaco] Found {len(mdx_files)} .mdx files — parsing …")

    docs = []

    for path in mdx_files:
        try:
            raw = path.read_text(encoding="utf-8", errors="ignore")

            title, body = _parse_frontmatter(raw)

            # Fallback title = filename without extension
            if not title:
                title = path.stem.replace("-", " ").replace("_", " ").title()

            body = _strip_mdx(body)

            if len(body.split()) < 60:
                continue

            rel = str(path.relative_to(repo)).replace("\\", "/")
            doc_id = f"usaco-guide/{re.sub(r'\.mdx$', '', rel)}"
            slug = path.stem
            url = f"https://usaco.guide/{slug}"

            docs.append(
                {
                    "doc_id": doc_id,
                    "title": title,
                    "url": url,
                    "source": "usaco-guide",
                    "category": _category(rel),
                    "difficulty": _difficulty(rel),
                    "text": body,
                }
            )

        except Exception as e:
            print(f"  SKIP {path.name}  ({e})")

    print(f"[usaco] Done — {len(docs)} modules")
    return docs
