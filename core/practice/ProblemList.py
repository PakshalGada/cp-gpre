"""Fetch Codeforces problems and scrape CSES into separate data files."""

import argparse
import json
import time

import requests

from core.practice.paths import CSES_CACHE, PROBLEMS_CACHE
from core.practice.scrape_cses import save_cses_problems, scrape_cses_problems


def fetch_codeforces_problems():
    print("Fetching Codeforces problems...")
    url = "https://codeforces.com/api/problemset.problems"
    response = requests.get(url, timeout=20)
    data = response.json()

    if data.get("status") != "OK":
        raise Exception("Codeforces API error: " + data.get("comment", "Unknown"))

    problems = []

    stats_map = {
        (s.get("contestId"), s.get("index")): s.get("solvedCount", 0)
        for s in data["result"]["problemStatistics"]
    }

    for p in data["result"]["problems"]:
        key = (p.get("contestId"), p.get("index"))
        solved_count = stats_map.get(key, 0)

        problems.append(
            {
                "platform": "codeforces",
                "contestId": p.get("contestId"),
                "index": p.get("index"),
                "name": p.get("name"),
                "rating": p.get("rating"),
                "tags": p.get("tags", []),
                "solvedCount": solved_count,
                "url": f"https://codeforces.com/problemset/problem/{p.get('contestId')}/{p.get('index')}",
            }
        )

    print(f"Fetched {len(problems)} Codeforces problems (with solvedCount)")
    return problems


def save_codeforces_problems(problems, path=PROBLEMS_CACHE):
    import os

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(problems, f, indent=2, ensure_ascii=False)
    print(f"Saved Codeforces problems to {path}")


def main():
    parser = argparse.ArgumentParser(
        description="Refresh Codeforces and/or CSES problem caches"
    )
    parser.add_argument(
        "--platform",
        choices=["codeforces", "cses", "all"],
        default="all",
        help="Which platform to refresh (default: all)",
    )
    args = parser.parse_args()

    if args.platform in ("codeforces", "all"):
        cf = fetch_codeforces_problems()
        save_codeforces_problems(cf)

    if args.platform in ("cses", "all"):
        if args.platform == "all":
            time.sleep(2)
        cses = scrape_cses_problems()
        save_cses_problems(cses)

    print("\nDone.")


if __name__ == "__main__":
    main()
