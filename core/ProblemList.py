import json
import re
import time

import requests


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


def fetch_cses_problems():
    print("Fetching CSES problems with solved counts...")
    url = "https://cses.fi/problemset/"
    response = requests.get(url, timeout=20)
    html = response.text

    problems = []

    pattern = r'<a href="(/problemset/task/(\d+))">([^<]+)</a>.*?<span[^>]*>(\d+)\s*/\s*(\d+)</span>'
    matches = re.findall(pattern, html, re.DOTALL)

    section_pattern = r"<h2>([^<]+)</h2>"
    sections = re.findall(section_pattern, html)

    section_idx = 0
    current_section = "Uncategorized"

    for i, match in enumerate(matches):
        relative_url, pid_str, name, solved_str, attempts_str = match
        pid = int(pid_str)
        solved_count = int(solved_str)
        full_url = "https://cses.fi" + relative_url

        if section_idx < len(sections):
            current_section = sections[section_idx]
            if i % 20 == 0 and section_idx < len(sections) - 1:
                section_idx += 1

        problems.append(
            {
                "platform": "cses",
                "id": pid,
                "name": name.strip(),
                "category": current_section,
                "url": full_url,
                "rating": None,
                "tags": [current_section.lower().replace(" ", "_").replace("&", "and")],
                "solvedCount": solved_count,
            }
        )

    print(f"Fetched {len(problems)} CSES problems with solvedCount")
    return problems


def main():
    all_problems = []

    all_problems.extend(fetch_codeforces_problems())
    time.sleep(2)

    all_problems.extend(fetch_cses_problems())

    with open("../data/problems.json", "w", encoding="utf-8") as f:
        json.dump(all_problems, f, indent=2, ensure_ascii=False)

    print(f"\nDone! Total {len(all_problems)} problems saved to problems.json")
    print("solvedCount is now correctly filled for both platforms.")


if __name__ == "__main__":
    main()
