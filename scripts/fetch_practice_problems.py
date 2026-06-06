import json
import os
import re
import sys
import time
import requests

# Set stdout encoding to utf-8 just in case
sys.stdout.reconfigure(encoding='utf-8')

# Ensure directories exist
os.makedirs("data", exist_ok=True)

# ----------------- CODEFORCES FETCHING -----------------
def classify_cf_contest(name):
    name_lower = name.lower()
    if "div. 1 + div. 2" in name_lower or "div. 1 and div. 2" in name_lower or "div. 1+2" in name_lower or "div 1 + div 2" in name_lower:
        return "Combined"
    elif "div. 1" in name_lower:
        return "Div. 1"
    elif "div. 2" in name_lower:
        return "Div. 2"
    elif "div. 3" in name_lower:
        return "Div. 3"
    elif "div. 4" in name_lower:
        return "Div. 4"
    elif "educational" in name_lower:
        return "Educational"
    elif "global" in name_lower:
        return "Global Round"
    else:
        return "Other"

def fetch_codeforces():
    print("Fetching Codeforces contests...")
    try:
        r = requests.get("https://codeforces.com/api/contest.list", timeout=20)
        r.raise_for_status()
        contests_data = r.json()
        if contests_data.get("status") != "OK":
            raise Exception("CF API error: " + contests_data.get("comment", ""))
        contests = contests_data["result"]
    except Exception as e:
        print(f"Error fetching Codeforces contests: {e}")
        return

    print("Fetching Codeforces problems...")
    try:
        r = requests.get("https://codeforces.com/api/problemset.problems", timeout=20)
        r.raise_for_status()
        problems_data = r.json()
        if problems_data.get("status") != "OK":
            raise Exception("CF API error: " + problems_data.get("comment", ""))
        problems_list = problems_data["result"]["problems"]
        stats_list = problems_data["result"]["problemStatistics"]
    except Exception as e:
        print(f"Error fetching Codeforces problems: {e}")
        return

    # Map problem stats (solvedCount)
    stats_map = {}
    for stat in stats_list:
        key = (stat.get("contestId"), stat.get("index"))
        stats_map[key] = stat.get("solvedCount", 0)

    # Group problems by contestId
    problems_by_contest = {}
    for p in problems_list:
        cid = p.get("contestId")
        if cid is None:
            continue
        if cid not in problems_by_contest:
            problems_by_contest[cid] = []
        problems_by_contest[cid].append(p)

    # Sort problems in each contest by index
    for cid in problems_by_contest:
        problems_by_contest[cid].sort(key=lambda x: x.get("index", ""))

    # Process and group contests
    categories = {
        "Div. 1": [],
        "Div. 2": [],
        "Div. 3": [],
        "Div. 4": [],
        "Educational": [],
        "Global Round": [],
        "Combined": [],
        "Other": []
    }

    print("Grouping Codeforces contests by Division...")
    for c in contests:
        if c.get("phase") != "FINISHED":
            continue
        cid = c.get("id")
        # Only include contests that actually have problems in the problemset
        if cid not in problems_by_contest:
            continue
        
        name = c.get("name", "")
        category = classify_cf_contest(name)

        contest_problems = []
        for p in problems_by_contest[cid]:
            key = (cid, p.get("index"))
            solved_count = stats_map.get(key, 0)
            contest_problems.append({
                "index": p.get("index"),
                "name": p.get("name"),
                "rating": p.get("rating"),
                "tags": p.get("tags", []),
                "solvedCount": solved_count,
                "url": f"https://codeforces.com/problemset/problem/{cid}/{p.get('index')}"
            })

        categories[category].append({
            "contestId": cid,
            "name": name,
            "problems": contest_problems
        })

    # Sort contests in each category by contestId descending (latest first)
    for cat in categories:
        categories[cat].sort(key=lambda x: x["contestId"], reverse=True)
        print(f"  {cat}: {len(categories[cat])} contests")

    # Save to file
    out_path = os.path.join("data", "codeforces_div_problems.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(categories, f, indent=2, ensure_ascii=False)
    print(f"Saved Codeforces div problems to {out_path}")


# ----------------- ATCODER FETCHING -----------------
def fetch_atcoder():
    print("Fetching AtCoder contests from Kenkoooo API...")
    try:
        r = requests.get("https://kenkoooo.com/atcoder/resources/contests.json", timeout=20)
        r.raise_for_status()
        contests = r.json()
    except Exception as e:
        print(f"Error fetching AtCoder contests: {e}")
        return

    print("Fetching AtCoder problems from Kenkoooo API...")
    try:
        r = requests.get("https://kenkoooo.com/atcoder/resources/problems.json", timeout=20)
        r.raise_for_status()
        problems = r.json()
    except Exception as e:
        print(f"Error fetching AtCoder problems: {e}")
        return

    print("Fetching AtCoder contest-problem mappings...")
    try:
        r = requests.get("https://kenkoooo.com/atcoder/resources/contest-problem.json", timeout=20)
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
        # Sort index numerically if possible, otherwise alphabetically
        def sort_key(x):
            idx = x["index"]
            # If it's single letter, return its ASCII code
            if len(idx) == 1:
                return (0, idx)
            # Try to extract number
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

    print("Grouping AtCoder contests...")
    for c in contests:
        cid = c["id"]
        # Only include contests that have problems mapped
        if cid not in contest_problems:
            continue

        title = c.get("title", "")
        start_time = c.get("start_epoch_second", 0)

        # Classify based on contest id prefix
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

    # Sort contests in each category by start time descending (latest first)
    for cat in categories:
        categories[cat].sort(key=lambda x: x["startTime"], reverse=True)
        print(f"  {cat}: {len(categories[cat])} contests")

    # Save to file
    out_path = os.path.join("data", "atcoder_problems.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(categories, f, indent=2, ensure_ascii=False)
    print(f"Saved AtCoder problems to {out_path}")


if __name__ == "__main__":
    print("=== STARTING PRACTICE PROBLEMS INGESTION ===")
    fetch_codeforces()
    print("-" * 40)
    fetch_atcoder()
    print("=== INGESTION COMPLETE ===")
