import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

TOPICS_FILE = ../data/topics.json
SCRAPED_DIR = ../data/raw
SCRAPED_DIR.mkdir(exist_ok=True)

CPALGO_BASE = "https://cp-algorithms.com"
USACO_BASE = "https://usaco.guide"
WIKI_API = "https://en.wikipedia.org/w/api.php"
CF_API = "https://codeforces.com/api/problemset.problems"
CSES_BASE = "https://cses.fi/problemset/task"

USACO_PATHS: dict[str, str] = {
    "binary-search": "/silver/binary-search",
    "bfs": "/silver/bfs",
    "dfs": "/silver/dfs",
    "two-pointers": "/silver/two-pointers",
    "prefix-sums": "/bronze/prefix-sums",
    "greedy": "/bronze/greedy",
    "sorting": "/bronze/intro-sorting",
    "segment-tree": "/gold/segtree",
    "lazy-seg-tree": "/gold/segtree",
    "fenwick-tree": "/gold/PURS",
    "dsu": "/gold/dsu",
    "dijkstra": "/gold/shortest-paths",
    "bellman-ford": "/gold/shortest-paths",
    "floyd-warshall": "/gold/shortest-paths",
    "toposort": "/gold/toposort",
    "lca": "/gold/tree-euler",
    "tree-dp": "/gold/dp-trees",
    "bitmask-dp": "/gold/dp-bitmasks",
    "hld": "/plat/hld",
    "centroid-decomp": "/plat/centroid",
    "convex-hull-trick": "/plat/convex-hull-trick",
    "max-flow": "/plat/max-flow",
    "string-hashing": "/gold/string-hashing",
    "kmp": "/gold/string-search",
    "z-function": "/gold/string-search",
    "suffix-array": "/gold/suffix-array",
    "meet-in-middle": "/gold/meet-in-the-middle",
    "euler-tour": "/gold/tree-euler",
    "dp-basics": "/gold/intro-dp",
    "knapsack": "/gold/knapsack",
    "lis": "/gold/lis",
    "interval-dp": "/gold/dp-intervals",
    "scc": "/gold/scc",
    "bridges-articulation": "/gold/bridges",
    "kruskal-mst": "/gold/mst",
    "prim": "/gold/mst",
    "game-theory": "/plat/grundy",
    "geometry-basics": "/plat/geo-pri",
    "convex-hull": "/plat/convex-hull",
    "sieve": "/gold/prime-factorization",
    "matrix-exp": "/plat/matrix-exp",
    "bipartite-matching": "/plat/max-flow",
    "2-sat": "/plat/2-sat",
    "aho-corasick": "/plat/aho-corasick",
    "sqrt-decomposition": "/plat/sqrt",
    "mo-algorithm": "/plat/sqrt",
    "persistent-seg-tree": "/plat/persistent",
    "divide-conquer-dp": "/plat/dc-dp",
    "li-chao-tree": "/plat/convex-hull-trick",
    "digit-dp": "/gold/digit-dp",
    "parallel-binary-search": "/plat/pbs",
    "small-to-large": "/plat/merging",
    "dsu-on-tree": "/plat/merging",
}

CF_EDU_URLS: dict[str, str] = {
    "segment-tree": "https://codeforces.com/edu/course/2/lesson/4",
    "dsu": "https://codeforces.com/edu/course/2/lesson/7",
    "suffix-array": "https://codeforces.com/edu/course/2/lesson/2",
    "aho-corasick": "https://codeforces.com/edu/course/2/lesson/10",
    "max-flow": "https://codeforces.com/edu/course/3",
    "bipartite-matching": "https://codeforces.com/edu/course/3/lesson/4",
    "scc": "https://codeforces.com/edu/course/3/lesson/2",
    "bridges-articulation": "https://codeforces.com/edu/course/3/lesson/2",
    "hld": "https://codeforces.com/edu/course/2/lesson/5",
    "fenwick-tree": "https://codeforces.com/edu/course/2/lesson/4",
    "suffix-automaton": "https://codeforces.com/edu/course/2/lesson/10",
}

CLIENT = httpx.Client(
    timeout=25,
    follow_redirects=True,
    headers={"User-Agent": "cp-guide-educational-scraper/1.0"},
)

DELAY = 1.2  # seconds between requests — be polite


def _get(url: str) -> httpx.Response | None:
    try:
        time.sleep(DELAY)
        r = CLIENT.get(url)
        r.raise_for_status()
        return r
    except httpx.HTTPStatusError as e:
        print(f"    ✗ HTTP {e.response.status_code}: {url}")
        return None
    except Exception as e:
        print(f"    ✗ {type(e).__name__}: {url}")
        return None




def _extract_content(
    html: str,
    selectors: list[str],
    max_text: int = 6000,
    max_code_blocks: int = 5,
) -> tuple[str, list[str]]:
    """
    Given HTML, try selectors in order until one finds content.
    Returns (clean_prose_text, [code_block_str, ...]).
    """
    soup = BeautifulSoup(html, "lxml")

    root = None
    for sel in selectors:
        found = soup.select_one(sel)
        if found and len(found.get_text(strip=True)) > 200:
            root = found
            break
    if root is None:
        root = soup.find("body") or soup

    # Extract code blocks before stripping them out
    code_blocks: list[str] = []
    for tag in root.find_all(["pre", "code"]):
        text = tag.get_text(strip=True)
        # Only keep non-trivial blocks, prefer C++ / pseudocode
        if len(text) > 40 and text not in code_blocks:
            code_blocks.append(text[:2500])
        if len(code_blocks) >= max_code_blocks:
            break
        tag.decompose()

    # Remove noise
    for tag in root.find_all(
        ["nav", "header", "footer", "script", "style", "aside", ".sidebar", ".toc"]
    ):
        tag.decompose()

    text = root.get_text(separator="\n", strip=True)
    # Collapse excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text[:max_text], code_blocks




def scrape_cp_algorithms(topic: dict) -> dict | None:
    path = topic.get("cpalgo_path")
    if not path:
        return None
    url = CPALGO_BASE + path
    print(f"    [cp-algorithms] {url}")
    r = _get(url)
    if not r:
        return None

    text, code = _extract_content(
        r.text,
        [".content", "article.md-content", "main", ".md-typeset"],
    )
    if len(text) < 100:
        return None

    return {"url": url, "text": text, "code_blocks": code}


def scrape_usaco_guide(topic: dict) -> dict | None:
    path = USACO_PATHS.get(topic["slug"])
    if not path:
        return None
    url = USACO_BASE + path
    print(f"    [usaco.guide] {url}")
    r = _get(url)
    if not r:
        return None

    text, code = _extract_content(
        r.text,
        ["main", "#content", "article", ".module-content"],
    )
    # USACO guide is a React SPA — server-side render may be sparse
    if len(text) < 150:
        print("      (page mostly JS-rendered, minimal static text captured)")
        return {"url": url, "text": text[:500], "code_blocks": code} if text else None

    return {"url": url, "text": text, "code_blocks": code}


def scrape_wikipedia(topic: dict) -> dict | None:
    wiki_title = topic.get("wikipedia")
    if not wiki_title:
        return None

    url = f"https://en.wikipedia.org/wiki/{wiki_title}"
    print(f"    [wikipedia] {url}")
    try:
        time.sleep(DELAY)
        r = CLIENT.get(
            WIKI_API,
            params={
                "action": "query",
                "prop": "extracts",
                "exintro": True,
                "explaintext": True,
                "titles": wiki_title.replace("_", " "),
                "format": "json",
            },
        )
        r.raise_for_status()
        pages = r.json()["query"]["pages"]
        page = next(iter(pages.values()))
        text = page.get("extract", "").strip()
        if not text or len(text) < 80:
            return None
        # Trim to first 3500 chars — intro is enough for context
        return {"url": url, "text": text[:3500]}
    except Exception as e:
        print(f"      ✗ Wikipedia error: {e}")
        return None


def scrape_cf_edu(topic: dict) -> dict | None:
    url = CF_EDU_URLS.get(topic["slug"])
    if not url:
        return None
    print(f"    [cf-edu] {url}")
    r = _get(url)
    if not r:
        return None

    text, code = _extract_content(
        r.text,
        [".ttypography", ".content", "main", ".statement-body"],
    )
    if len(text) < 80:
        return None

    return {"url": url, "text": text, "code_blocks": code}


# ─── problem fetchers ─────────────────────────────────────────────────────────

_CF_CACHE: list[dict] | None = None


def _load_cf_problemset() -> list[dict]:
    global _CF_CACHE
    if _CF_CACHE is not None:
        return _CF_CACHE

    print("  [CF API] Fetching full problem set (one-time)...")
    try:
        time.sleep(DELAY)
        r = CLIENT.get(CF_API, timeout=30)
        r.raise_for_status()
        data = r.json()
        if data.get("status") != "OK":
            print(f"  [CF API] Bad status: {data.get('status')}")
            _CF_CACHE = []
            return []

        stats: dict[str, int] = {
            f"{s['contestId']}{s['index']}": s.get("solvedCount", 0)
            for s in data["result"].get("problemStatistics", [])
        }

        problems = []
        for p in data["result"]["problems"]:
            cid = p.get("contestId", "")
            idx = p.get("index", "")
            pid = f"{cid}{idx}"
            problems.append(
                {
                    "id": pid,
                    "name": p["name"],
                    "url": f"https://codeforces.com/problemset/problem/{cid}/{idx}",
                    "difficulty": p.get("rating"),
                    "tags": [t.lower() for t in p.get("tags", [])],
                    "solved_count": stats.get(pid, 0),
                }
            )

        _CF_CACHE = problems
        print(f"  [CF API] Loaded {len(problems):,} problems.")
        return _CF_CACHE
    except Exception as e:
        print(f"  [CF API] Failed: {e}")
        _CF_CACHE = []
        return []


def fetch_cf_problems(topic: dict, limit: int = 12) -> list[dict]:
    """Return CF problems that match the topic's cf_tags, sorted easiest first."""
    all_probs = _load_cf_problemset()
    query_tags = set(t.lower() for t in (topic.get("cf_tags") or topic.get("tags", [])))

    matched = []
    for p in all_probs:
        if not p["difficulty"]:
            continue
        if query_tags and not query_tags.intersection(set(p["tags"])):
            continue
        matched.append(p)

    matched.sort(key=lambda p: (p["difficulty"], -p["solved_count"]))

    seen: set[str] = set()
    result = []
    for p in matched:
        if p["id"] not in seen and len(result) < limit:
            seen.add(p["id"])
            result.append(p)
    return result


_CSES_NAME_CACHE: dict[str, str] = {}


def fetch_cses_problems(topic: dict) -> list[dict]:
    """Resolve CSES problem IDs to names by scraping cses.fi."""
    ids = [i for i in (topic.get("cses_ids") or []) if i]
    problems = []

    for pid in ids:
        if pid not in _CSES_NAME_CACHE:
            url = f"{CSES_BASE}/{pid}"
            r = _get(url)
            if r:
                soup = BeautifulSoup(r.text, "lxml")
                h1 = soup.find("h1")
                _CSES_NAME_CACHE[pid] = h1.get_text(strip=True) if h1 else f"CSES {pid}"
            else:
                _CSES_NAME_CACHE[pid] = f"CSES {pid}"

        problems.append(
            {
                "id": pid,
                "name": _CSES_NAME_CACHE[pid],
                "url": f"{CSES_BASE}/{pid}",
            }
        )

    return problems


# ─── single-topic scrape ──────────────────────────────────────────────────────


def scrape_topic(topic: dict) -> dict:
    """
    Scrape all sources for one topic. Returns the full structured dict
    that gets written to scraped/<slug>.json.
    """
    slug = topic["slug"]
    title = topic["title"]
    print(f"\n  ── {title} ({slug})")

    sources: dict[str, dict | None] = {}

    sources["cp_algorithms"] = scrape_cp_algorithms(topic)
    sources["usaco_guide"] = scrape_usaco_guide(topic)
    sources["wikipedia"] = scrape_wikipedia(topic)
    sources["cf_edu"] = scrape_cf_edu(topic)

    # Remove None sources
    sources = {k: v for k, v in sources.items() if v is not None}

    problems = {
        "cses": fetch_cses_problems(topic),
        "codeforces": fetch_cf_problems(topic),
    }

    result = {
        "slug": slug,
        "title": title,
        "category": topic.get("category", ""),
        "tags": topic.get("tags", []),
        "prereqs": topic.get("prereqs", []),
        "leads_to": topic.get("leads_to", []),
        "scraped_at": datetime.utcnow().isoformat(),
        "sources": sources,
        "problems": problems,
    }

    # Write immediately so we can resume
    out = SCRAPED_DIR / f"{slug}.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    src_names = list(sources.keys()) or ["(none)"]
    n_cses = len(problems["cses"])
    n_cf = len(problems["codeforces"])
    print(f"    ✓ sources={src_names}  cses={n_cses}  cf={n_cf}")
    return result


# ─── index + problems flat file ───────────────────────────────────────────────


def write_index(results: list[dict]) -> None:
    index = []
    for r in results:
        index.append(
            {
                "slug": r["slug"],
                "title": r["title"],
                "category": r["category"],
                "scraped_at": r["scraped_at"],
                "sources": list(r["sources"].keys()),
                "n_cses": len(r["problems"]["cses"]),
                "n_cf": len(r["problems"]["codeforces"]),
            }
        )
    (SCRAPED_DIR / "_index.json").write_text(json.dumps(index, indent=2))
    print(f"\n  Wrote _index.json ({len(index)} entries)")


def write_problems_flat(results: list[dict]) -> None:
    """Write a flat deduplicated list of all problems across all topics."""
    seen: dict[str, dict] = {}
    for r in results:
        slug = r["slug"]
        for p in r["problems"]["cses"]:
            key = f"cses:{p['id']}"
            if key not in seen:
                seen[key] = {
                    **p,
                    "source": "cses",
                    "topic_slugs": [],
                    "difficulty": None,
                }
            if slug not in seen[key]["topic_slugs"]:
                seen[key]["topic_slugs"].append(slug)

        for p in r["problems"]["codeforces"]:
            key = f"cf:{p['id']}"
            if key not in seen:
                seen[key] = {**p, "source": "codeforces", "topic_slugs": []}
            if slug not in seen[key]["topic_slugs"]:
                seen[key]["topic_slugs"].append(slug)

    flat = list(seen.values())
    (SCRAPED_DIR / "_problems.json").write_text(json.dumps(flat, indent=2))
    print(f"  Wrote _problems.json ({len(flat)} unique problems)")


# ─── CLI ──────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scrape CP reference sources for every topic in topics.json"
    )
    parser.add_argument("--slug", help="Scrape a single topic by slug")
    parser.add_argument("--category", help="Scrape an entire category")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip topics that already have a scraped/<slug>.json",
    )
    parser.add_argument(
        "--problems-only",
        action="store_true",
        help="Only fetch CF/CSES problems (no page scraping)",
    )
    parser.add_argument("--list", action="store_true", help="List all topics and exit")
    args = parser.parse_args()

    topics: list[dict] = json.loads(TOPICS_FILE.read_text())

    if args.list:
        for t in topics:
            print(f"  {t['id']:3}  {t['slug']:40}  {t['category']}")
        print(f"\nTotal: {len(topics)}")
        return

    # Filter
    if args.slug:
        topics = [t for t in topics if t["slug"] == args.slug]
        if not topics:
            print(f"No topic with slug '{args.slug}'")
            sys.exit(1)
    elif args.category:
        topics = [t for t in topics if t["category"].lower() == args.category.lower()]
        if not topics:
            print(f"No topics in category '{args.category}'")
            sys.exit(1)

    if args.resume:
        before = len(topics)
        topics = [t for t in topics if not (SCRAPED_DIR / f"{t['slug']}.json").exists()]
        print(f"Resuming: {before - len(topics)} already done, {len(topics)} remaining")

    print(f"\nScraping {len(topics)} topic(s) → {SCRAPED_DIR}/\n{'=' * 60}")

    results: list[dict] = []

    for i, topic in enumerate(topics, 1):
        print(f"[{i}/{len(topics)}]", end="")

        if args.problems_only:
            # Load existing scraped file and only refresh problems
            out = SCRAPED_DIR / f"{topic['slug']}.json"
            if out.exists():
                existing = json.loads(out.read_text())
            else:
                existing = {
                    "slug": topic["slug"],
                    "title": topic["title"],
                    "category": topic.get("category", ""),
                    "tags": topic.get("tags", []),
                    "prereqs": topic.get("prereqs", []),
                    "leads_to": topic.get("leads_to", []),
                    "scraped_at": datetime.utcnow().isoformat(),
                    "sources": {},
                }
            existing["problems"] = {
                "cses": fetch_cses_problems(topic),
                "codeforces": fetch_cf_problems(topic),
            }
            out.write_text(json.dumps(existing, indent=2, ensure_ascii=False))
            print(f"  (problems-only) {topic['slug']}")
            results.append(existing)
        else:
            try:
                result = scrape_topic(topic)
                results.append(result)
            except KeyboardInterrupt:
                print("\n\nInterrupted. Index will be written for completed topics.")
                break
            except Exception as e:
                print(f"\n  ✗ ERROR: {topic['slug']}: {e}")
                import traceback

                traceback.print_exc()
                continue

    # Write aggregate files
    if results:
        print(f"\n{'=' * 60}")
        write_index(results)
        write_problems_flat(results)

    print(f"\nDone. {len(results)} topic(s) scraped → {SCRAPED_DIR}/")


if __name__ == "__main__":
    main()
