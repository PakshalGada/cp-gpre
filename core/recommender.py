import argparse
import json
import math
import os
import sys
import time
from collections import Counter, defaultdict

import requests

CF_API = "https://codeforces.com/api"
RETRY_WAIT = 5
MAX_RETRIES = 3
PROBLEMS_CACHE = "data/problems.json"


def cf_get(endpoint: str, params: dict = None, retries: int = MAX_RETRIES) -> dict:
    url = f"{CF_API}/{endpoint}"
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, params=params, timeout=20)
            data = r.json()
            if data.get("status") == "OK":
                return data["result"]
            comment = data.get("comment", "unknown error")
            if "limit exceeded" in comment.lower() or r.status_code == 429:
                print(
                    f"  Rate-limited. Waiting {RETRY_WAIT}s … (attempt {attempt}/{retries})"
                )
                time.sleep(RETRY_WAIT)
            else:
                raise RuntimeError(f"Codeforces API error: {comment}")
        except requests.RequestException as exc:
            if attempt == retries:
                raise
            print(f"  Network error ({exc}). Retrying in {RETRY_WAIT}s …")
            time.sleep(RETRY_WAIT)
    raise RuntimeError("Failed to fetch from Codeforces after retries.")


def load_problems(path: str = PROBLEMS_CACHE):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    print(f"  Cache not found at '{path}'. Fetching live from Codeforces …")
    raw = cf_get("problemset.problems")
    stats_map = {
        (s.get("contestId"), s.get("index")): s.get("solvedCount", 0)
        for s in raw["problemStatistics"]
    }
    problems = []
    for p in raw["problems"]:
        key = (p.get("contestId"), p.get("index"))
        problems.append(
            {
                "platform": "codeforces",
                "contestId": p.get("contestId"),
                "index": p.get("index"),
                "name": p.get("name"),
                "rating": p.get("rating"),
                "tags": p.get("tags", []),
                "solvedCount": stats_map.get(key, 0),
                "url": f"https://codeforces.com/problemset/problem/{p.get('contestId')}/{p.get('index')}",
            }
        )
    print(f"  Fetched {len(problems)} problems.")
    return problems


def fetch_user_profile(handle: str) -> dict:
    print(f"  Fetching profile for '{handle}' …")
    result = cf_get("user.info", {"handles": handle})
    u = result[0]
    return {
        "handle": u.get("handle"),
        "rating": u.get("rating", 0),
        "max_rating": u.get("maxRating", 0),
        "rank": u.get("rank", "unrated"),
    }


def fetch_user_submissions(handle: str) -> list:
    print(f"  Fetching submission history for '{handle}' …")
    return cf_get("user.status", {"handle": handle, "from": 1, "count": 10000})


def build_solved_set(submissions: list) -> set:
    return {
        (sub["problem"].get("contestId"), sub["problem"].get("index"))
        for sub in submissions
        if sub.get("verdict") == "OK"
    }


def build_attempted_set(submissions: list) -> set:
    return {
        (sub["problem"].get("contestId"), sub["problem"].get("index"))
        for sub in submissions
    }


IGNORED_TAGS = {"*special", "interactive", "2-sat"}


def analyse_topics(submissions: list, solved_set: set) -> dict:
    """
    Returns solved/attempted counts per tag, average solved rating per tag,
    and a ranked list of weak tags.
    """
    solved_per_tag: Counter = Counter()
    attempted_per_tag: Counter = Counter()
    rating_sum: dict = defaultdict(int)
    rating_cnt: dict = defaultdict(int)

    seen_keys = set()
    for sub in submissions:
        p = sub.get("problem", {})
        key = (p.get("contestId"), p.get("index"))
        tags = [t for t in p.get("tags", []) if t not in IGNORED_TAGS]
        rating = p.get("rating") or 0

        for tag in tags:
            if key not in seen_keys:
                attempted_per_tag[tag] += 1
            if key in solved_set and rating:
                if key not in seen_keys:
                    solved_per_tag[tag] += 1
                    rating_sum[tag] += rating
                    rating_cnt[tag] += 1
        seen_keys.add(key)

    avg_rating_per_tag = {tag: rating_sum[tag] / rating_cnt[tag] for tag in rating_cnt}

    # Weak: low absolute solve count, or low solve/attempt ratio
    weak_tags = sorted(
        [t for t in attempted_per_tag if t not in IGNORED_TAGS],
        key=lambda t: (
            solved_per_tag.get(t, 0),
            solved_per_tag.get(t, 0) / max(attempted_per_tag[t], 1),
        ),
    )

    return {
        "solved_per_tag": solved_per_tag,
        "attempted_per_tag": attempted_per_tag,
        "avg_rating_per_tag": avg_rating_per_tag,
        "weak_tags": weak_tags,
    }


def score_problem(
    problem: dict,
    solved_set: set,
    attempted_set: set,
    topic_analysis: dict,
    target_rating: int,
    weak_tag_set: set,
    explore_tag_set: set,
    mode: str,
) -> float:
    """
    Returns a float score (higher = better recommendation), or None to skip.
    """
    if problem.get("platform") != "codeforces":
        return None
    if problem.get("rating") is None:
        return None

    key = (problem.get("contestId"), problem.get("index"))
    if key in solved_set:
        return None

    p_rating = problem["rating"]
    tags = set(problem.get("tags", [])) - IGNORED_TAGS
    solved_count = problem.get("solvedCount", 0)

    if mode == "stretch":
        ideal_delta, tolerance = 200, 300
    elif mode == "grind":
        ideal_delta, tolerance = -100, 250
    else:
        ideal_delta, tolerance = 100, 250

    delta = p_rating - target_rating
    rating_score = max(0.0, 1 - abs(delta - ideal_delta) / tolerance)

    topic_score = 0.0
    if mode in ("weak-topics", "balanced"):
        topic_score += len(tags & weak_tag_set) * 0.3
    if mode == "explore":
        topic_score += len(tags & explore_tag_set) * 0.5
        mastered = set(topic_analysis["solved_per_tag"].keys()) - explore_tag_set
        if tags & mastered:
            topic_score -= 0.3

    pop_score = math.log1p(solved_count) / math.log1p(50000)

    attempt_penalty = 0.1 if key in attempted_set else 0.0

    if mode == "grind":
        score = 0.3 * rating_score + 0.2 * topic_score + 0.6 * pop_score
    elif mode == "explore":
        score = 0.4 * rating_score + 0.6 * topic_score + 0.1 * pop_score
    elif mode == "weak-topics":
        score = 0.3 * rating_score + 0.7 * topic_score + 0.1 * pop_score
    else:
        score = 0.5 * rating_score + 0.3 * topic_score + 0.2 * pop_score

    return max(0.0, score - attempt_penalty)


def recommend(
    user_handle: str,
    count: int = 8,
    mode: str = "balanced",
    tag_filter: list = None,
    min_rating: int = None,
    max_rating: int = None,
    show_attempts: bool = False,
) -> None:
    """Main recommendation pipeline."""

    print("\n" + "═" * 62)
    print(f"  Codeforces Problem Recommender  |  user: {user_handle}")
    print("═" * 62)

    # 1. Fetch user data
    profile = fetch_user_profile(user_handle)
    submissions = fetch_user_submissions(user_handle)
    solved_set = build_solved_set(submissions)
    attempted_set = build_attempted_set(submissions)

    current_rating = profile["rating"] or 800
    print(f"\n  Rating    : {current_rating}  ({profile['rank']})")
    print(f"  Max rating: {profile['max_rating']}")
    print(f"  Solved    : {len(solved_set)} problems")

    # 2. Topic analysis
    topic_analysis = analyse_topics(submissions, solved_set)
    solved_per_tag = topic_analysis["solved_per_tag"]
    attempted_per_tag = topic_analysis["attempted_per_tag"]

    all_tags = [t for t in attempted_per_tag if t not in IGNORED_TAGS]
    sorted_tags = sorted(all_tags, key=lambda t: solved_per_tag.get(t, 0))
    weak_tag_set = set(sorted_tags[: max(1, len(sorted_tags) // 3)])

    # 3. Load problem set
    print(f"\n  Loading problem set …")
    all_problems = load_problems()
    cf_problems = [p for p in all_problems if p.get("platform") == "codeforces"]
    print(f"  {len(cf_problems)} Codeforces problems loaded.")

    # Explore set = tags in problem set never yet solved
    all_problem_tags: set = set()
    for p in cf_problems:
        all_problem_tags.update(p.get("tags", []))
    explore_tag_set = (all_problem_tags - set(solved_per_tag.keys())) - IGNORED_TAGS

    # 4. Rating window
    effective_min = min_rating if min_rating else max(800, current_rating - 100)
    effective_max = max_rating if max_rating else current_rating + 400

    # 5. Score every problem
    scored = []
    for p in cf_problems:
        p_rating = p.get("rating") or 0
        if not (effective_min <= p_rating <= effective_max):
            continue
        if tag_filter and not any(t in p.get("tags", []) for t in tag_filter):
            continue
        sc = score_problem(
            p,
            solved_set,
            attempted_set,
            topic_analysis,
            current_rating,
            weak_tag_set,
            explore_tag_set,
            mode,
        )
        if sc is not None:
            scored.append((sc, p))

    scored.sort(key=lambda x: -x[0])

    # 6. Deduplicate: max 2 per primary tag
    tag_budget: Counter = Counter()
    deduplicated = []
    for sc, p in scored:
        tags = [t for t in p.get("tags", []) if t not in IGNORED_TAGS]
        primary = tags[0] if tags else "misc"
        if tag_budget[primary] < 2 or len(deduplicated) < count // 2:
            deduplicated.append((sc, p))
            tag_budget[primary] += 1
        if len(deduplicated) >= count:
            break

    # Pad if needed
    if len(deduplicated) < count:
        seen_urls = {p["url"] for _, p in deduplicated}
        for sc, p in scored:
            if p["url"] not in seen_urls:
                deduplicated.append((sc, p))
                seen_urls.add(p["url"])
            if len(deduplicated) >= count:
                break

    # 7. Print recommendations
    print(f"\n  Mode      : {mode}")
    print(f"  Window    : {effective_min} – {effective_max}")
    if tag_filter:
        print(f"  Tag filter: {', '.join(tag_filter)}")

    weak_display = ", ".join(list(weak_tag_set)[:6]) or "N/A"
    explore_display = ", ".join(list(explore_tag_set)[:6]) or "none"
    print(f"\n  Weakest topics  : {weak_display}")
    print(f"  Unexplored topics: {explore_display}")

    print("\n" + "─" * 62)
    print(f"  {'#':<3}  {'Rat':<5}  {'AC':<7}  {'Tags'}")
    print("─" * 62)

    for i, (sc, p) in enumerate(deduplicated[:count], 1):
        tags_str = ", ".join(p.get("tags", [])[:3])
        name = p.get("name", "?")
        rating = p.get("rating") or "?"
        solved = p.get("solvedCount", 0)
        url = p.get("url", "")
        is_attempted = (p.get("contestId"), p.get("index")) in attempted_set
        flag = " ⚑ attempted" if is_attempted else ""
        print(f"  {i:<3}  {str(rating):<5}  {solved:<7}  {tags_str}")
        print(f"       {name}{flag}")
        print(f"       {url}")
        print()

    print("─" * 62)
    print(f"  {len(deduplicated[:count])} recommendations  |  mode: {mode}")

    # 8. Optional topic breakdown
    if show_attempts:
        print("\n  ── Topic breakdown (solved / attempted / avg rating) ──────")
        for tag in sorted(solved_per_tag, key=lambda t: -solved_per_tag[t])[:20]:
            s = solved_per_tag[tag]
            a = attempted_per_tag.get(tag, 0)
            avg = int(topic_analysis["avg_rating_per_tag"].get(tag, 0))
            pct = s / max(a, 1) * 100
            bar = "█" * min(25, s // 2)
            weak_mark = " ←" if tag in weak_tag_set else ""
            print(
                f"    {tag:<32}  {s:>4}/{a:<4}  avg {avg:>4}  ({pct:4.0f}%)  {bar}{weak_mark}"
            )

    print()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Codeforces personalised problem recommender",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--user", "-u", default=None, help="Codeforces handle (prompted if omitted)"
    )
    parser.add_argument(
        "--count",
        "-n",
        type=int,
        default=8,
        help="Number of problems to recommend (default 8)",
    )
    parser.add_argument(
        "--mode",
        "-m",
        choices=["balanced", "stretch", "weak-topics", "explore", "grind"],
        default="balanced",
        help=(
            "balanced    – weak topics + slight rating push (default)\n"
            "stretch     – harder problems to force growth\n"
            "weak-topics – focus on your weakest areas\n"
            "explore     – topics you have never touched\n"
            "grind       – popular problems to build speed"
        ),
    )
    parser.add_argument(
        "--tags",
        default=None,
        help="Comma-separated list of required tags, e.g. dp,graphs",
    )
    parser.add_argument("--min-rating", type=int, default=None)
    parser.add_argument("--max-rating", type=int, default=None)
    parser.add_argument(
        "--show-topics",
        action="store_true",
        help="Print your full topic breakdown after recommendations",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    handle = args.user
    if not handle:
        handle = input("  Enter your Codeforces handle: ").strip()
    if not handle:
        print("No handle provided. Exiting.")
        sys.exit(1)

    tag_filter = [t.strip() for t in args.tags.split(",")] if args.tags else None

    recommend(
        user_handle=handle,
        count=args.count,
        mode=args.mode,
        tag_filter=tag_filter,
        min_rating=args.min_rating,
        max_rating=args.max_rating,
        show_attempts=args.show_topics,
    )


if __name__ == "__main__":
    main()
