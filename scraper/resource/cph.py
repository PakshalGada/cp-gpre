import re
from pathlib import Path

import requests

PDF_URL = "https://cses.fi/book/book.pdf"
PDF_PATH = "data/raw/cph/book.pdf"


def _difficulty(chapter_num: int) -> str:
    if chapter_num <= 5:
        return "beginner"
    if chapter_num <= 13:
        return "intermediate"
    if chapter_num <= 21:
        return "advanced-intermediate"
    if chapter_num <= 27:
        return "advanced"
    return "expert"


def _category(title: str) -> str:
    t = title.lower()
    if any(w in t for w in ["sort", "search", "binary"]):
        return "sorting"
    if any(w in t for w in ["dynamic", " dp", "knapsack"]):
        return "dp"
    if any(w in t for w in ["graph", "path", "bfs", "dfs", "flow", "component"]):
        return "graphs"
    if any(w in t for w in ["tree", "segment", "fenwick", "heavy", "lca"]):
        return "data-structures"
    if any(w in t for w in ["string", "suffix", "automaton", "hashing"]):
        return "strings"
    if any(w in t for w in ["math", "number", "prime", "modular", "combinat"]):
        return "math"
    if "geometry" in t:
        return "geometry"
    return "misc"


def _slug(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")[:50]


def _ensure_pdf(pdf_path: Path) -> bool:
    if pdf_path.exists():
        print(f"[cph] PDF already at {pdf_path}")
        return True

    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"[cph] Downloading PDF from {PDF_URL} …")
    try:
        r = requests.get(PDF_URL, timeout=60, stream=True)
        r.raise_for_status()
        with open(pdf_path, "wb") as f:
            for chunk in r.iter_content(65536):
                f.write(chunk)
        size_kb = pdf_path.stat().st_size // 1024
        print(f"[cph] Downloaded ({size_kb} KB)")
        return True
    except Exception as e:
        print(f"[cph] Download failed: {e}")
        return False


# Lines to strip: page numbers, running headers
_JUNK = re.compile(
    r"^\s*(\d{1,3}|—\s*\d+\s*—|Competitive Programmer.s Handbook|CHAPTER \d+)\s*$",
    re.IGNORECASE,
)


def _clean_page(text: str) -> str:
    lines = [l for l in text.splitlines() if not _JUNK.match(l)]
    cleaned = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", cleaned)


def _is_heading(line: str) -> tuple[bool, str]:
    """Return (is_heading, cleaned_title)."""
    s = line.strip()
    if not (5 < len(s) < 65):
        return False, ""
    if s[-1] in ".,:;?!":
        return False, ""
    alpha = sum(c.isalpha() for c in s) / max(len(s), 1)
    if alpha < 0.55:
        return False, ""
    if not s[0].isupper():
        return False, ""
    return True, s


def _reconstruct(text: str) -> str:
    """Join lines that were broken mid-sentence by the PDF layout."""
    lines = text.splitlines()
    result = []
    buf = []

    for line in lines:
        s = line.strip()
        if not s:
            if buf:
                result.append(" ".join(buf))
                buf = []
            result.append("")
            continue
        # De-hyphenation
        if buf and buf[-1].endswith("-"):
            buf[-1] = buf[-1][:-1] + s
        else:
            buf.append(s)

    if buf:
        result.append(" ".join(buf))

    text = "\n".join(result)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


_CODE_KW = re.compile(
    r"\b(int|void|long|bool|for|while|return|include|using|vector|"
    r"map|set|pair|auto|struct|cout|cin|#include|#define)\b"
)


def _fence_code(text: str) -> str:
    """Wrap indented C++ blocks in ``` fences."""
    lines = text.splitlines()
    result = []
    i = 0

    while i < len(lines):
        line = lines[i]
        if (line.startswith("    ") or line.startswith("\t")) and _CODE_KW.search(line):
            block = []
            while i < len(lines) and (
                lines[i].startswith("    ")
                or lines[i].startswith("\t")
                or not lines[i].strip()
            ):
                block.append(lines[i])
                i += 1
            code = "\n".join(block).rstrip()
            if code.strip() and len(block) >= 2:
                result.append(f"```cpp\n{code}\n```")
            else:
                result.extend(block)
        else:
            result.append(line)
            i += 1

    return "\n".join(result)


def scrape(pdf_path: str = PDF_PATH) -> list[dict]:
    """
    Extract chapters from the CPH PDF and return doc dicts.
    Each dict has: doc_id, title, url, source, category, difficulty, text.
    """
    try:
        import fitz
    except ImportError:
        print("[cph] PyMuPDF not installed. Run: pip install PyMuPDF")
        return []

    path = Path(pdf_path)
    if not _ensure_pdf(path):
        return []

    print(f"[cph] Extracting text from {path} …")

    pdf = fitz.open(str(path))
    pages = [page.get_text() for page in pdf]
    pdf.close()

    sections: list[tuple[str, list[str]]] = []  # [(title, [page_texts])]
    current_title = "Introduction"
    current_pages: list[str] = []

    for page_text in pages:
        cleaned = _clean_page(page_text)
        for line in cleaned.splitlines():
            ok, title = _is_heading(line)
            if ok and current_pages:
                sections.append((current_title, list(current_pages)))
                current_title = title
                current_pages = []
        current_pages.append(cleaned)

    if current_pages:
        sections.append((current_title, current_pages))

    docs = []

    for chapter_num, (title, sec_pages) in enumerate(sections):
        text = "\n\n".join(sec_pages)
        text = _reconstruct(text)
        text = _fence_code(text)
        text = re.sub(r"\n{3,}", "\n\n", text).strip()

        if len(text.split()) < 60:
            continue

        doc_id = f"cph/chapter-{chapter_num:02d}-{_slug(title)}"
        url = f"{PDF_URL}#chapter={chapter_num}"

        docs.append(
            {
                "doc_id": doc_id,
                "title": f"CPH · {title}",
                "url": url,
                "source": "cph",
                "category": _category(title),
                "difficulty": _difficulty(chapter_num),
                "text": text,
            }
        )

        print(f"  Chapter {chapter_num:02d}: {title}")

    print(f"[cph] Done — {len(docs)} chapters")
    return docs
