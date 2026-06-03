"""Scrape all CSES problem set tasks into data/cses_problems.json."""

import argparse
import json
import re
import sys

import requests

from core.practice.paths import CSES_CACHE

CSES_URL = "https://cses.fi/problemset/"
TASK_PATTERN = re.compile(
    r'<a href="(/problemset/task/(\d+))">([^<]+)</a>'
    r'<span class="detail">(\d+)\s*/\s*(\d+)</span>',
    re.DOTALL,
)
SECTION_PATTERN = re.compile(r"<h2>([^<]+)</h2>")


def scrape_cses_problems() -> list[dict]:
    print(f"Fetching {CSES_URL} …")
    response = requests.get(CSES_URL, timeout=30)
    response.raise_for_status()
    html = response.text

    problems = []
    sections = SECTION_PATTERN.split(html)

    # split returns: [preamble, title1, body1, title2, body2, ...]
    for i in range(1, len(sections), 2):
        category = sections[i].strip()
        if category == "General":
            continue

        body = sections[i + 1] if i + 1 < len(sections) else ""
        for match in TASK_PATTERN.finditer(body):
            relative_url, pid_str, name, solved_str, attempts_str = match.groups()
            pid = int(pid_str)
            problems.append(
                {
                    "platform": "cses",
                    "id": pid,
                    "name": name.strip(),
                    "category": category,
                    "url": f"https://cses.fi{relative_url}",
                    "rating": None,
                    "tags": [
                        category.lower()
                        .replace(" ", "_")
                        .replace("&", "and")
                    ],
                    "solvedCount": int(solved_str),
                    "attemptCount": int(attempts_str),
                }
            )

    print(f"Scraped {len(problems)} CSES problems.")
    return problems


def save_cses_problems(problems: list[dict], path: str = CSES_CACHE) -> None:
    import os

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(problems, f, indent=2, ensure_ascii=False)
    print(f"Saved to {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape CSES problem set")
    parser.add_argument(
        "--output",
        "-o",
        default=CSES_CACHE,
        help="Output JSON path (default: data/cses_problems.json)",
    )
    args = parser.parse_args()

    try:
        problems = scrape_cses_problems()
    except requests.RequestException as exc:
        print(f"Failed to fetch CSES: {exc}", file=sys.stderr)
        return 1

    if not problems:
        print("No problems scraped — page structure may have changed.", file=sys.stderr)
        return 1

    save_cses_problems(problems, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
