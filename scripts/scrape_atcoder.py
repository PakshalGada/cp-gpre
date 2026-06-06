import json
import os
import re
import sys
import requests

# Set stdout encoding to utf-8 just in case
sys.stdout.reconfigure(encoding='utf-8')

# Ensure directory exists
os.makedirs("data", exist_ok=True)

def fetch_atcoder():
    print("=== STARTING STANDALONE ATCODER SCRAPING ===")
    print("Fetching AtCoder contests from Kenkoooo API...")
    try:
        r = requests.get("https://kenkoooo.com/atcoder/resources/contests.json", timeout=25)
        r.raise_for_status()
        contests = r.json()
    except Exception as e:
        print(f"Error fetching AtCoder contests: {e}")
        return

    print("Fetching AtCoder problems from Kenkoooo API...")
    try:
        r = requests.get("https://kenkoooo.com/atcoder/resources/problems.json", timeout=25)
        r.raise_for_status()
        problems = r.json()
    except Exception as e:
        print(f"Error fetching AtCoder problems: {e}")
        return

    print("Fetching AtCoder contest-problem mappings...")
    try:
        r = requests.get("https://kenkoooo.com/atcoder/resources/contest-problem.json", timeout=25)
        r.raise_for_status()
        mappings = r.json()
    except Exception as e:
        print(f"Error fetching AtCoder contest-problem mappings: {e}")
        return

    # Map problem_id to problem details
    problems_map = {}
    for p in problems:
        problems_map[p["id"]] = p

    # Map contest_id to its problems mapping
    contest_problems = {}
    for m in mappings:
        cid = m["contest_id"]
        pid = m["problem_id"]
        pindex = m.get("problem_index", "")

        if cid not in contest_problems:
            contest_problems[cid] = []

        p_details = problems_map.get(pid)
        if p_details:
            contest_problems[cid].append({
                "id": pid,
                "index": pindex,
                "name": p_details.get("title", p_details.get("name", "")),
                "url": f"https://atcoder.jp/contests/{cid}/tasks/{pid}"
            })

    # Sort problems in each contest by index
    for cid in contest_problems:
        def sort_key(x):
            idx = x["index"]
            if len(idx) == 1:
                return (0, idx)
            num_match = re.search(r'\d+', idx)
            if num_match:
                return (1, int(num_match.group()))
            return (2, idx)
        
        contest_problems[cid].sort(key=sort_key)

    # Group contests by type
    categories = {
        "ABC": [],
        "ARC": [],
        "AGC": [],
        "Other": []
    }

    print("Grouping AtCoder contests by type...")
    for c in contests:
        cid = c["id"]
        if cid not in contest_problems:
            continue

        title = c.get("title", "")
        start_time = c.get("start_epoch_second", 0)

        if cid.startswith("abc"):
            category = "ABC"
        elif cid.startswith("arc"):
            category = "ARC"
        elif cid.startswith("agc"):
            category = "AGC"
        else:
            category = "Other"

        categories[category].append({
            "contestId": cid,
            "name": title,
            "startTime": start_time,
            "problems": contest_problems[cid]
        })

    # Sort contests by start time descending (latest first)
    for cat in categories:
        categories[cat].sort(key=lambda x: x["startTime"], reverse=True)
        print(f"  {cat}: {len(categories[cat])} contests")

    # Save to file
    out_path = os.path.join("data", "atcoder_problems.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(categories, f, indent=2, ensure_ascii=False)
    print(f"Saved AtCoder problems to {out_path}")
    print("=== SCRAPING COMPLETE ===")

if __name__ == "__main__":
    fetch_atcoder()
