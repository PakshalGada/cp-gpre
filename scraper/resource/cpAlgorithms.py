import re
import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://cp-algorithms.com"
HEADERS = {"User-Agent": "cp-gpre-bot/1.0 (educational scraper)"}

# URL path → topic category
CATEGORY_MAP = {
    "algebra": "math",
    "graph": "graphs",
    "data_structures": "data-structures",
    "dynamic_programming": "dp",
    "dp": "dp",
    "string": "strings",
    "geometry": "geometry",
    "combinatorics": "math",
    "sequences": "misc",
    "others": "misc",
}


def _get(url: str, retries: int = 3) -> requests.Response | None:
    """Polite GET with retry and delay."""
    time.sleep(0.5)
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=14)
            if r.status_code == 200:
                return r
        except requests.RequestException:
            pass
        time.sleep(2**attempt)
    return None


def _html_to_markdown(tag) -> str:
    """
    Walk a BeautifulSoup tag and convert it to clean markdown text.
    Handles: headings, paragraphs, code blocks, inline code, lists, tables.
    """
    lines = []

    def walk(node):
        if isinstance(node, str):
            t = node.strip()
            if t:
                lines.append(t)
            return

        name = node.name
        if name is None:
            return

        if name in ("nav", "header", "footer", "script", "style", "button", "aside"):
            return

        if name in ("h1", "h2", "h3", "h4"):
            text = node.get_text(strip=True)
            if text:
                level = int(name[1])
                lines.append(f"\n{'#' * level} {text}\n")
            return

        if name == "pre":
            code = node.find("code")
            src = (code or node).get_text()
            lang = ""
            if code:
                for cls in code.get("class", []):
                    if cls.startswith("language-"):
                        lang = cls[9:]
            lines.append(f"\n```{lang}\n{src.rstrip()}\n```\n")
            return

        if name == "code":
            lines.append(f"`{node.get_text()}`")
            return

        if name == "p":
            text = node.get_text(separator=" ", strip=True)
            if text:
                lines.append(f"\n{text}\n")
            return

        if name in ("ul", "ol"):
            for i, li in enumerate(node.find_all("li", recursive=False)):
                prefix = f"{i + 1}." if name == "ol" else "-"
                lines.append(f"{prefix} {li.get_text(separator=' ', strip=True)}")
            lines.append("")
            return

        if name == "table":
            rows = node.find_all("tr")
            for ri, row in enumerate(rows):
                cells = [c.get_text(strip=True) for c in row.find_all(["th", "td"])]
                lines.append("| " + " | ".join(cells) + " |")
                if ri == 0:
                    lines.append("|" + "|".join(["---"] * len(cells)) + "|")
            lines.append("")
            return

        for child in node.children:
            walk(child)

    walk(tag)

    text = " ".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def _category(url: str) -> str:
    path = urlparse(url).path.lower()
    for segment, cat in CATEGORY_MAP.items():
        if f"/{segment}/" in path:
            return cat
    return "misc"


def _difficulty(category: str) -> str:
    return {
        "math": "intermediate",
        "graphs": "intermediate",
        "dp": "intermediate",
        "data-structures": "advanced-intermediate",
        "strings": "advanced",
        "geometry": "advanced",
        "misc": "intermediate",
    }.get(category, "intermediate")


def _collect_links() -> list[str]:
    r = _get(BASE_URL)
    if not r:
        return []

    soup = BeautifulSoup(r.text, "lxml")
    seen = set()
    links = []

    for a in soup.find_all("a", href=True):
        href = a["href"].split("#")[0].strip()
        if not href:
            continue
        full = urljoin(BASE_URL, href)
        parsed = urlparse(full)
        if "cp-algorithms.com" not in parsed.netloc:
            continue
        path = parsed.path
        if path in ("/", "") or path.endswith("/"):
            continue
        if full in seen:
            continue
        seen.add(full)
        links.append(full)

    return links


def scrape() -> list[dict]:
    """
    Crawl cp-algorithms.com and return a list of doc dicts.
    Each dict has: doc_id, title, url, source, category, difficulty, text.
    """
    print("[cp-algorithms] Collecting links …")
    links = _collect_links()
    print(f"[cp-algorithms] Found {len(links)} URLs — scraping …")

    docs = []

    for i, url in enumerate(links):
        try:
            r = _get(url)
            if not r:
                continue

            soup = BeautifulSoup(r.text, "lxml")

            body = (
                soup.find("article")
                or soup.find("div", class_="md-content")
                or soup.find("main")
            )
            if not body:
                continue

            h1 = soup.find("h1")
            title = h1.get_text(strip=True) if h1 else url.split("/")[-1]

            text = _html_to_markdown(body)

            if len(text.split()) < 60:
                continue

            # Build a clean doc_id from the URL path
            path = urlparse(url).path
            path = re.sub(r"\.(html|htm)$", "", path).strip("/")
            doc_id = f"cp-algorithms/{path}"

            category = _category(url)

            docs.append(
                {
                    "doc_id": doc_id,
                    "title": title,
                    "url": url,
                    "source": "cp-algorithms",
                    "category": category,
                    "difficulty": _difficulty(category),
                    "text": text,
                }
            )

            print(f"  [{i + 1}/{len(links)}] {title[:70]}")

        except Exception as e:
            print(f"  SKIP {url[:60]}  ({e})")

    print(f"[cp-algorithms] Done — {len(docs)} articles")
    return docs
