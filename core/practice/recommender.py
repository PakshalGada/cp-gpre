import argparse
import json
import math
import os
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Optional

import requests

CF_API = "https://codeforces.com/api"
RETRY_WAIT = 5
MAX_RETRIES = 3
PROBLEMS_CACHE = "../../data/problems.json"
CSES_CACHE = "../../data/cses_problems.json"
PROGRESS_CACHE = "../../data/progress_{}.json"


__all__ = [
    "APIClient",
    "ProblemLoader",
    "UserProfile",
    "ProgressTracker",
    "ContestSimulator",
    "TopicAnalyzer",
    "ProblemScorer",
    "Recommender",
    "get_recommendations_json",
    "get_progress_json",
    "get_contest_json",
]


class APIClient:
    @staticmethod
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


class ProblemLoader:
    IGNORED_TAGS = {"*special", "interactive", "2-sat"}

    @staticmethod
    def load_codeforces(path: str = PROBLEMS_CACHE) -> list:
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                return json.load(f)

        print(f"  Cache not found at '{path}'. Fetching live from Codeforces …")
        raw = APIClient.cf_get("problemset.problems")
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

        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(problems, f)

        return problems

    @staticmethod
    def load_cses(path: str = CSES_CACHE) -> list:
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                return json.load(f)

        problems = [
            {
                "platform": "cses",
                "id": 1068,
                "name": "Weird Algorithm",
                "category": "Introductory Problems",
                "url": "https://cses.fi/problemset/task/1068",
            },
            {
                "platform": "cses",
                "id": 1083,
                "name": "Missing Number",
                "category": "Introductory Problems",
                "url": "https://cses.fi/problemset/task/1083",
            },
            {
                "platform": "cses",
                "id": 1069,
                "name": "Repetitions",
                "category": "Introductory Problems",
                "url": "https://cses.fi/problemset/task/1069",
            },
            {
                "platform": "cses",
                "id": 1094,
                "name": "Increasing Array",
                "category": "Introductory Problems",
                "url": "https://cses.fi/problemset/task/1094",
            },
            {
                "platform": "cses",
                "id": 1070,
                "name": "Permutations",
                "category": "Introductory Problems",
                "url": "https://cses.fi/problemset/task/1070",
            },
            {
                "platform": "cses",
                "id": 1071,
                "name": "Number Spiral",
                "category": "Introductory Problems",
                "url": "https://cses.fi/problemset/task/1071",
            },
            {
                "platform": "cses",
                "id": 1072,
                "name": "Two Knights",
                "category": "Introductory Problems",
                "url": "https://cses.fi/problemset/task/1072",
            },
            {
                "platform": "cses",
                "id": 1092,
                "name": "Two Sets",
                "category": "Introductory Problems",
                "url": "https://cses.fi/problemset/task/1092",
            },
            {
                "platform": "cses",
                "id": 1617,
                "name": "Bit Strings",
                "category": "Introductory Problems",
                "url": "https://cses.fi/problemset/task/1617",
            },
            {
                "platform": "cses",
                "id": 1618,
                "name": "Trailing Zeros",
                "category": "Introductory Problems",
                "url": "https://cses.fi/problemset/task/1618",
            },
            {
                "platform": "cses",
                "id": 1754,
                "name": "Coin Piles",
                "category": "Introductory Problems",
                "url": "https://cses.fi/problemset/task/1754",
            },
            {
                "platform": "cses",
                "id": 1755,
                "name": "Palindrome Reorder",
                "category": "Introductory Problems",
                "url": "https://cses.fi/problemset/task/1755",
            },
            {
                "platform": "cses",
                "id": 2165,
                "name": "Tower of Hanoi",
                "category": "Introductory Problems",
                "url": "https://cses.fi/problemset/task/2165",
            },
            {
                "platform": "cses",
                "id": 1622,
                "name": "Creating Strings",
                "category": "Introductory Problems",
                "url": "https://cses.fi/problemset/task/1622",
            },
            {
                "platform": "cses",
                "id": 1623,
                "name": "Apple Division",
                "category": "Introductory Problems",
                "url": "https://cses.fi/problemset/task/1623",
            },
            {
                "platform": "cses",
                "id": 1624,
                "name": "Chessboard and Queens",
                "category": "Introductory Problems",
                "url": "https://cses.fi/problemset/task/1624",
            },
            {
                "platform": "cses",
                "id": 2431,
                "name": "Digit Queries",
                "category": "Introductory Problems",
                "url": "https://cses.fi/problemset/task/2431",
            },
            {
                "platform": "cses",
                "id": 1625,
                "name": "Grid Paths",
                "category": "Introductory Problems",
                "url": "https://cses.fi/problemset/task/1625",
            },
            {
                "platform": "cses",
                "id": 1640,
                "name": "Sum of Two Values",
                "category": "Sorting and Searching",
                "url": "https://cses.fi/problemset/task/1640",
            },
            {
                "platform": "cses",
                "id": 1084,
                "name": "Apartments",
                "category": "Sorting and Searching",
                "url": "https://cses.fi/problemset/task/1084",
            },
            {
                "platform": "cses",
                "id": 1090,
                "name": "Ferris Wheel",
                "category": "Sorting and Searching",
                "url": "https://cses.fi/problemset/task/1090",
            },
            {
                "platform": "cses",
                "id": 1091,
                "name": "Concert Tickets",
                "category": "Sorting and Searching",
                "url": "https://cses.fi/problemset/task/1091",
            },
            {
                "platform": "cses",
                "id": 1619,
                "name": "Restaurant Customers",
                "category": "Sorting and Searching",
                "url": "https://cses.fi/problemset/task/1619",
            },
            {
                "platform": "cses",
                "id": 1629,
                "name": "Movie Festival",
                "category": "Sorting and Searching",
                "url": "https://cses.fi/problemset/task/1629",
            },
            {
                "platform": "cses",
                "id": 1074,
                "name": "Stick Lengths",
                "category": "Sorting and Searching",
                "url": "https://cses.fi/problemset/task/1074",
            },
            {
                "platform": "cses",
                "id": 1620,
                "name": "Factory Machines",
                "category": "Sorting and Searching",
                "url": "https://cses.fi/problemset/task/1620",
            },
            {
                "platform": "cses",
                "id": 1158,
                "name": "Book Shop",
                "category": "Dynamic Programming",
                "url": "https://cses.fi/problemset/task/1158",
            },
            {
                "platform": "cses",
                "id": 1746,
                "name": "Array Description",
                "category": "Dynamic Programming",
                "url": "https://cses.fi/problemset/task/1746",
            },
            {
                "platform": "cses",
                "id": 1638,
                "name": "Grid Paths",
                "category": "Dynamic Programming",
                "url": "https://cses.fi/problemset/task/1638",
            },
            {
                "platform": "cses",
                "id": 1633,
                "name": "Dice Combinations",
                "category": "Dynamic Programming",
                "url": "https://cses.fi/problemset/task/1633",
            },
            {
                "platform": "cses",
                "id": 1634,
                "name": "Minimizing Coins",
                "category": "Dynamic Programming",
                "url": "https://cses.fi/problemset/task/1634",
            },
            {
                "platform": "cses",
                "id": 1635,
                "name": "Coin Combinations I",
                "category": "Dynamic Programming",
                "url": "https://cses.fi/problemset/task/1635",
            },
            {
                "platform": "cses",
                "id": 1636,
                "name": "Coin Combinations II",
                "category": "Dynamic Programming",
                "url": "https://cses.fi/problemset/task/1636",
            },
            {
                "platform": "cses",
                "id": 1637,
                "name": "Removing Digits",
                "category": "Dynamic Programming",
                "url": "https://cses.fi/problemset/task/1637",
            },
            {
                "platform": "cses",
                "id": 1745,
                "name": "Money Sums",
                "category": "Dynamic Programming",
                "url": "https://cses.fi/problemset/task/1745",
            },
            {
                "platform": "cses",
                "id": 1744,
                "name": "Rectangle Cutting",
                "category": "Dynamic Programming",
                "url": "https://cses.fi/problemset/task/1744",
            },
            {
                "platform": "cses",
                "id": 1193,
                "name": "Labyrinth",
                "category": "Graph Algorithms",
                "url": "https://cses.fi/problemset/task/1193",
            },
            {
                "platform": "cses",
                "id": 1666,
                "name": "Building Roads",
                "category": "Graph Algorithms",
                "url": "https://cses.fi/problemset/task/1666",
            },
            {
                "platform": "cses",
                "id": 1667,
                "name": "Message Route",
                "category": "Graph Algorithms",
                "url": "https://cses.fi/problemset/task/1667",
            },
            {
                "platform": "cses",
                "id": 1668,
                "name": "Building Teams",
                "category": "Graph Algorithms",
                "url": "https://cses.fi/problemset/task/1668",
            },
            {
                "platform": "cses",
                "id": 1669,
                "name": "Round Trip",
                "category": "Graph Algorithms",
                "url": "https://cses.fi/problemset/task/1669",
            },
            {
                "platform": "cses",
                "id": 1192,
                "name": "Counting Rooms",
                "category": "Graph Algorithms",
                "url": "https://cses.fi/problemset/task/1192",
            },
            {
                "platform": "cses",
                "id": 1194,
                "name": "Monsters",
                "category": "Graph Algorithms",
                "url": "https://cses.fi/problemset/task/1194",
            },
            {
                "platform": "cses",
                "id": 1671,
                "name": "Shortest Routes I",
                "category": "Graph Algorithms",
                "url": "https://cses.fi/problemset/task/1671",
            },
            {
                "platform": "cses",
                "id": 1672,
                "name": "Shortest Routes II",
                "category": "Graph Algorithms",
                "url": "https://cses.fi/problemset/task/1672",
            },
            {
                "platform": "cses",
                "id": 1673,
                "name": "High Score",
                "category": "Graph Algorithms",
                "url": "https://cses.fi/problemset/task/1673",
            },
            {
                "platform": "cses",
                "id": 1093,
                "name": "Two Sets II",
                "category": "Mathematics",
                "url": "https://cses.fi/problemset/task/1093",
            },
            {
                "platform": "cses",
                "id": 2177,
                "name": "Josephus Problem I",
                "category": "Mathematics",
                "url": "https://cses.fi/problemset/task/2177",
            },
            {
                "platform": "cses",
                "id": 2165,
                "name": "Exponentiation",
                "category": "Mathematics",
                "url": "https://cses.fi/problemset/task/1095",
            },
            {
                "platform": "cses",
                "id": 1712,
                "name": "Exponentiation II",
                "category": "Mathematics",
                "url": "https://cses.fi/problemset/task/1712",
            },
            {
                "platform": "cses",
                "id": 1079,
                "name": "Binomial Coefficients",
                "category": "Mathematics",
                "url": "https://cses.fi/problemset/task/1079",
            },
            {
                "platform": "cses",
                "id": 1082,
                "name": "Sum of Divisors",
                "category": "Mathematics",
                "url": "https://cses.fi/problemset/task/1082",
            },
        ]

        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(problems, f)

        return problems

    @classmethod
    def load_all(cls) -> list:
        cf_problems = cls.load_codeforces()
        cses_problems = cls.load_cses()
        return cf_problems + cses_problems


class UserProfile:
    def __init__(self, handle: str, platform: str = "codeforces"):
        self.handle = handle
        self.platform = platform
        self.rating = 0
        self.max_rating = 0
        self.rank = "unrated"
        self.submissions = []
        self.solved_set = set()
        self.attempted_set = set()

    def fetch(self):
        if self.platform == "codeforces":
            self._fetch_codeforces()

    def _fetch_codeforces(self):
        print(f"  Fetching profile for '{self.handle}' …")
        result = APIClient.cf_get("user.info", {"handles": self.handle})
        u = result[0]
        self.rating = u.get("rating", 0) or 800
        self.max_rating = u.get("maxRating", 0)
        self.rank = u.get("rank", "unrated")

        print(f"  Fetching submission history for '{self.handle}' …")
        self.submissions = APIClient.cf_get(
            "user.status", {"handle": self.handle, "from": 1, "count": 10000}
        )

        self.solved_set = {
            (sub["problem"].get("contestId"), sub["problem"].get("index"))
            for sub in self.submissions
            if sub.get("verdict") == "OK"
        }

        self.attempted_set = {
            (sub["problem"].get("contestId"), sub["problem"].get("index"))
            for sub in self.submissions
        }


class ProgressTracker:
    def __init__(self, handle: str):
        self.handle = handle
        self.cache_path = PROGRESS_CACHE.format(handle)
        self.history = self._load_cache()

    def _load_cache(self) -> list:
        if os.path.exists(self.cache_path):
            with open(self.cache_path, encoding="utf-8") as f:
                return json.load(f)
        return []

    def _save_cache(self):
        os.makedirs(os.path.dirname(self.cache_path) or ".", exist_ok=True)
        with open(self.cache_path, "w", encoding="utf-8") as f:
            json.dump(self.history, f, indent=2)

    def update(self, submissions: list):
        entries_by_date = defaultdict(
            lambda: {"solved": 0, "attempted": 0, "rating": None}
        )

        for sub in submissions:
            ts = sub.get("creationTimeSeconds", 0)
            date = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")

            entries_by_date[date]["attempted"] += 1
            if sub.get("verdict") == "OK":
                entries_by_date[date]["solved"] += 1

        rating_data = APIClient.cf_get("user.rating", {"handle": self.handle})
        for change in rating_data:
            ts = change.get("ratingUpdateTimeSeconds", 0)
            date = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
            entries_by_date[date]["rating"] = change.get("newRating")

        self.history = [
            {"date": date, **data} for date, data in sorted(entries_by_date.items())
        ]
        self._save_cache()

    def get_current_streak(self, submissions: list) -> dict:
        if not submissions:
            return {"submission_streak": 0, "solve_streak": 0}

        sorted_subs = sorted(
            submissions, key=lambda x: x.get("creationTimeSeconds", 0), reverse=True
        )

        submission_dates = []
        solve_dates = []

        for sub in sorted_subs:
            ts = sub.get("creationTimeSeconds", 0)
            date = datetime.fromtimestamp(ts).date()

            if not submission_dates or date not in [d for d in submission_dates]:
                submission_dates.append(date)

            if sub.get("verdict") == "OK" and (
                not solve_dates or date not in [d for d in solve_dates]
            ):
                solve_dates.append(date)

        submission_streak = self._calculate_streak(submission_dates)
        solve_streak = self._calculate_streak(solve_dates)

        return {"submission_streak": submission_streak, "solve_streak": solve_streak}

    @staticmethod
    def _calculate_streak(dates: list) -> int:
        if not dates:
            return 0

        today = datetime.now().date()
        if dates[0] != today and dates[0] != today - timedelta(days=1):
            return 0

        streak = 1
        for i in range(len(dates) - 1):
            diff = (dates[i] - dates[i + 1]).days
            if diff <= 1:
                streak += 1
            else:
                break

        return streak

    def get_rating_graph(self) -> list:
        return [
            {"date": entry["date"], "rating": entry["rating"]}
            for entry in self.history
            if entry["rating"] is not None
        ]

    def get_activity_graph(self) -> list:
        return [
            {
                "date": entry["date"],
                "solved": entry["solved"],
                "attempted": entry["attempted"],
            }
            for entry in self.history
        ]


class ContestSimulator:
    def __init__(self, profile: UserProfile):
        self.profile = profile

    def get_contest_problems(self, contest_id: int) -> list:
        print(f"  Fetching contest {contest_id} …")
        result = APIClient.cf_get(
            "contest.standings", {"contestId": contest_id, "from": 1, "count": 1}
        )
        problems = result.get("problems", [])

        return [
            {
                "platform": "codeforces",
                "contestId": p.get("contestId"),
                "index": p.get("index"),
                "name": p.get("name"),
                "rating": p.get("rating"),
                "tags": p.get("tags", []),
                "url": f"https://codeforces.com/contest/{p.get('contestId')}/problem/{p.get('index')}",
            }
            for p in problems
        ]

    def get_unsolved_from_contest(self, contest_id: int) -> list:
        problems = self.get_contest_problems(contest_id)
        return [
            p
            for p in problems
            if (p.get("contestId"), p.get("index")) not in self.profile.solved_set
        ]

    def recommend_div_contests(self, division: int, count: int = 5) -> list:
        contests = APIClient.cf_get("contest.list")

        div_map = {1: "Div. 1", 2: "Div. 2", 3: "Div. 3", 4: "Div. 4"}
        div_str = div_map.get(division, "Div. 2")

        relevant = [
            c
            for c in contests
            if c.get("phase") == "FINISHED" and div_str in c.get("name", "")
        ][:50]

        recommendations = []
        for contest in relevant:
            contest_id = contest.get("id")
            try:
                unsolved = self.get_unsolved_from_contest(contest_id)
                if unsolved:
                    recommendations.append(
                        {
                            "contest_id": contest_id,
                            "name": contest.get("name"),
                            "unsolved_count": len(unsolved),
                            "problems": unsolved[:3],
                        }
                    )
                if len(recommendations) >= count:
                    break
            except:
                continue

        return recommendations


class TopicAnalyzer:
    IGNORED_TAGS = {"*special", "interactive", "2-sat"}

    def __init__(self, submissions: list, solved_set: set):
        self.submissions = submissions
        self.solved_set = solved_set
        self.analysis = self._analyze()

    def _analyze(self) -> dict:
        solved_per_tag = Counter()
        attempted_per_tag = Counter()
        rating_sum = defaultdict(int)
        rating_cnt = defaultdict(int)

        seen_keys = set()
        for sub in self.submissions:
            p = sub.get("problem", {})
            key = (p.get("contestId"), p.get("index"))
            tags = [t for t in p.get("tags", []) if t not in self.IGNORED_TAGS]
            rating = p.get("rating") or 0

            for tag in tags:
                if key not in seen_keys:
                    attempted_per_tag[tag] += 1
                if key in self.solved_set and rating:
                    if key not in seen_keys:
                        solved_per_tag[tag] += 1
                        rating_sum[tag] += rating
                        rating_cnt[tag] += 1
            seen_keys.add(key)

        avg_rating_per_tag = {
            tag: rating_sum[tag] / rating_cnt[tag] for tag in rating_cnt
        }

        weak_tags = sorted(
            [t for t in attempted_per_tag if t not in self.IGNORED_TAGS],
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

    def get_weak_tags(self, top_n: Optional[int] = None) -> set:
        weak = self.analysis["weak_tags"]
        if top_n:
            return set(weak[:top_n])
        return set(weak[: max(1, len(weak) // 3)])

    def get_stats(self) -> dict:
        return self.analysis


class ProblemScorer:
    IGNORED_TAGS = {"*special", "interactive", "2-sat"}

    def __init__(
        self,
        profile: UserProfile,
        topic_analyzer: TopicAnalyzer,
        mode: str,
        all_problems: list,
    ):
        self.profile = profile
        self.topic_analyzer = topic_analyzer
        self.mode = mode
        self.weak_tag_set = topic_analyzer.get_weak_tags()
        self.explore_tag_set = self._get_explore_tags(all_problems)

    def _get_explore_tags(self, all_problems: list) -> set:
        all_problem_tags = set()
        for p in all_problems:
            if p.get("platform") == "codeforces":
                all_problem_tags.update(p.get("tags", []))

        solved_tags = set(self.topic_analyzer.analysis["solved_per_tag"].keys())
        return (all_problem_tags - solved_tags) - self.IGNORED_TAGS

    def score(self, problem: dict) -> Optional[float]:
        if problem.get("platform") == "cses":
            return self._score_cses(problem)

        if problem.get("platform") != "codeforces":
            return None
        if problem.get("rating") is None:
            return None

        key = (problem.get("contestId"), problem.get("index"))
        if key in self.profile.solved_set:
            return None

        p_rating = problem["rating"]
        tags = set(problem.get("tags", [])) - self.IGNORED_TAGS
        solved_count = problem.get("solvedCount", 0)

        if self.mode == "stretch":
            ideal_delta, tolerance = 200, 300
        elif self.mode == "grind":
            ideal_delta, tolerance = -100, 250
        else:
            ideal_delta, tolerance = 100, 250

        delta = p_rating - self.profile.rating
        rating_score = max(0.0, 1 - abs(delta - ideal_delta) / tolerance)

        topic_score = 0.0
        if self.mode in ("weak-topics", "balanced"):
            topic_score += len(tags & self.weak_tag_set) * 0.3
        if self.mode == "explore":
            topic_score += len(tags & self.explore_tag_set) * 0.5
            mastered = (
                set(self.topic_analyzer.analysis["solved_per_tag"].keys())
                - self.explore_tag_set
            )
            if tags & mastered:
                topic_score -= 0.3

        pop_score = math.log1p(solved_count) / math.log1p(50000)

        attempt_penalty = 0.1 if key in self.profile.attempted_set else 0.0

        if self.mode == "grind":
            score = 0.3 * rating_score + 0.2 * topic_score + 0.6 * pop_score
        elif self.mode == "explore":
            score = 0.4 * rating_score + 0.6 * topic_score + 0.1 * pop_score
        elif self.mode == "weak-topics":
            score = 0.3 * rating_score + 0.7 * topic_score + 0.1 * pop_score
        else:
            score = 0.5 * rating_score + 0.3 * topic_score + 0.2 * pop_score

        return max(0.0, score - attempt_penalty)

    def _score_cses(self, problem: dict) -> float:
        if problem.get("id") in getattr(self, "_cses_solved", set()):
            return None
        return 0.5


class Recommender:
    def __init__(self, profile: UserProfile):
        self.profile = profile
        self.topic_analyzer = TopicAnalyzer(profile.submissions, profile.solved_set)
        self.all_problems = ProblemLoader.load_all()

    def recommend(
        self,
        count: int = 8,
        mode: str = "balanced",
        tag_filter: list = None,
        min_rating: int = None,
        max_rating: int = None,
        platform_filter: str = None,
    ) -> list:
        scorer = ProblemScorer(
            self.profile, self.topic_analyzer, mode, self.all_problems
        )

        effective_min = (
            min_rating if min_rating else max(800, self.profile.rating - 100)
        )
        effective_max = max_rating if max_rating else self.profile.rating + 400

        scored = []
        for p in self.all_problems:
            if platform_filter and p.get("platform") != platform_filter:
                continue

            if p.get("platform") == "codeforces":
                p_rating = p.get("rating") or 0
                if not (effective_min <= p_rating <= effective_max):
                    continue
                if tag_filter and not any(t in p.get("tags", []) for t in tag_filter):
                    continue

            sc = scorer.score(p)
            if sc is not None:
                scored.append((sc, p))

        scored.sort(key=lambda x: -x[0])

        tag_budget = Counter()
        deduplicated = []
        for sc, p in scored:
            if p.get("platform") == "cses":
                deduplicated.append((sc, p))
            else:
                tags = [
                    t for t in p.get("tags", []) if t not in ProblemScorer.IGNORED_TAGS
                ]
                primary = tags[0] if tags else "misc"
                if tag_budget[primary] < 2 or len(deduplicated) < count // 2:
                    deduplicated.append((sc, p))
                    tag_budget[primary] += 1

            if len(deduplicated) >= count:
                break

        if len(deduplicated) < count:
            seen_urls = {p["url"] for _, p in deduplicated}
            for sc, p in scored:
                if p["url"] not in seen_urls:
                    deduplicated.append((sc, p))
                    seen_urls.add(p["url"])
                if len(deduplicated) >= count:
                    break

        return deduplicated[:count]


def print_recommendations(
    profile: UserProfile,
    recommendations: list,
    mode: str,
    topic_analyzer: TopicAnalyzer,
    show_topics: bool = False,
):
    print("\n" + "═" * 62)
    print(f"  Codeforces Problem Recommender  |  user: {profile.handle}")
    print("═" * 62)

    print(f"\n  Rating    : {profile.rating}  ({profile.rank})")
    print(f"  Max rating: {profile.max_rating}")
    print(f"  Solved    : {len(profile.solved_set)} problems")

    tracker = ProgressTracker(profile.handle)
    streaks = tracker.get_current_streak(profile.submissions)
    print(
        f"  Streaks   : {streaks['submission_streak']}d submissions, {streaks['solve_streak']}d solves"
    )

    weak_tags = topic_analyzer.get_weak_tags(6)
    weak_display = ", ".join(list(weak_tags)) or "N/A"
    print(f"\n  Weakest topics: {weak_display}")

    print(f"\n  Mode: {mode}")
    print("\n" + "─" * 62)
    print(f"  {'#':<3}  {'Platform':<10}  {'Rat':<5}  {'AC':<7}  {'Tags/Category'}")
    print("─" * 62)

    for i, (sc, p) in enumerate(recommendations, 1):
        platform = p.get("platform", "?")
        name = p.get("name", "?")
        url = p.get("url", "")

        if platform == "cses":
            category = p.get("category", "")
            rating_str = "-"
            solved_str = "-"
            tags_str = category
        else:
            rating = p.get("rating") or "?"
            solved = p.get("solvedCount", 0)
            tags_str = ", ".join(p.get("tags", [])[:3])
            rating_str = str(rating)
            solved_str = str(solved)

            is_attempted = (p.get("contestId"), p.get("index")) in profile.attempted_set
            flag = " ⚑ attempted" if is_attempted else ""
            name = name + flag

        print(f"  {i:<3}  {platform:<10}  {rating_str:<5}  {solved_str:<7}  {tags_str}")
        print(f"       {name}")
        print(f"       {url}")
        print()

    print("─" * 62)
    print(f"  {len(recommendations)} recommendations  |  mode: {mode}")

    if show_topics:
        stats = topic_analyzer.get_stats()
        solved_per_tag = stats["solved_per_tag"]
        attempted_per_tag = stats["attempted_per_tag"]
        avg_rating_per_tag = stats["avg_rating_per_tag"]

        print("\n  ── Topic breakdown (solved / attempted / avg rating) ──────")
        for tag in sorted(solved_per_tag, key=lambda t: -solved_per_tag[t])[:20]:
            s = solved_per_tag[tag]
            a = attempted_per_tag.get(tag, 0)
            avg = int(avg_rating_per_tag.get(tag, 0))
            pct = s / max(a, 1) * 100
            bar = "█" * min(25, s // 2)
            weak_mark = " ←" if tag in weak_tags else ""
            print(
                f"    {tag:<32}  {s:>4}/{a:<4}  avg {avg:>4}  ({pct:4.0f}%)  {bar}{weak_mark}"
            )

    print()


def show_progress(handle: str):
    profile = UserProfile(handle)
    profile.fetch()

    tracker = ProgressTracker(handle)
    tracker.update(profile.submissions)

    print("\n" + "═" * 62)
    print(f"  Progress Tracker  |  user: {handle}")
    print("═" * 62)

    streaks = tracker.get_current_streak(profile.submissions)
    print(f"\n  Current submission streak: {streaks['submission_streak']} days")
    print(f"  Current solve streak: {streaks['solve_streak']} days")

    rating_history = tracker.get_rating_graph()
    if rating_history:
        print(f"\n  Rating history (last 10 contests):")
        for entry in rating_history[-10:]:
            print(f"    {entry['date']}: {entry['rating']}")

    activity = tracker.get_activity_graph()
    if activity:
        print(f"\n  Recent activity (last 7 days):")
        for entry in activity[-7:]:
            print(
                f"    {entry['date']}: {entry['solved']} solved, {entry['attempted']} attempted"
            )

    print()


def simulate_contest(handle: str, division: int = 2, contest_count: int = 5):
    profile = UserProfile(handle)
    profile.fetch()

    simulator = ContestSimulator(profile)
    contests = simulator.recommend_div_contests(division, contest_count)

    print("\n" + "═" * 62)
    print(f"  Contest Simulator  |  user: {handle}  |  Div. {division}")
    print("═" * 62)

    for contest in contests:
        print(f"\n  Contest {contest['contest_id']}: {contest['name']}")
        print(f"  Unsolved: {contest['unsolved_count']} problems")
        print("  Sample problems:")
        for p in contest["problems"]:
            print(f"    - {p['index']}: {p['name']} ({p.get('rating', '?')})")
            print(f"      {p['url']}")

    print()


def interactive_mode():
    print("\n" + "═" * 62)
    print("  Codeforces Problem Recommender - Interactive Mode")
    print("═" * 62)

    handle = input("\n  Enter your Codeforces handle: ").strip()
    if not handle:
        print("No handle provided. Exiting.")
        return

    print("\n  Available commands:")
    print("    1. Get problem recommendations")
    print("    2. View progress and streaks")
    print("    3. Simulate contest")
    print("    4. Exit")

    choice = input("\n  Choose (1-4): ").strip()

    if choice == "1":
        print("\n  Recommendation modes:")
        print("    1. Balanced (weak topics + slight rating push)")
        print("    2. Stretch (harder problems for growth)")
        print("    3. Weak-topics (focus on weakest areas)")
        print("    4. Explore (new untouched topics)")
        print("    5. Grind (popular problems for speed)")

        mode_choice = input("\n  Choose mode (1-5, default 1): ").strip() or "1"
        mode_map = {
            "1": "balanced",
            "2": "stretch",
            "3": "weak-topics",
            "4": "explore",
            "5": "grind",
        }
        mode = mode_map.get(mode_choice, "balanced")

        count_input = input("  Number of problems (default 8): ").strip()
        count = int(count_input) if count_input.isdigit() else 8

        platform = (
            input("  Platform (codeforces/cses/both, default both): ").strip().lower()
        )
        platform_filter = platform if platform in ["codeforces", "cses"] else None

        profile = UserProfile(handle)
        profile.fetch()

        recommender = Recommender(profile)
        recommendations = recommender.recommend(
            count=count,
            mode=mode,
            platform_filter=platform_filter,
        )

        print_recommendations(
            profile, recommendations, mode, recommender.topic_analyzer, False
        )

    elif choice == "2":
        show_progress(handle)

    elif choice == "3":
        div_input = input("\n  Division (1-4, default 2): ").strip()
        division = int(div_input) if div_input in ["1", "2", "3", "4"] else 2

        count_input = input("  Number of contests (default 5): ").strip()
        count = int(count_input) if count_input.isdigit() else 5

        simulate_contest(handle, division, count)

    else:
        print("\n  Goodbye!")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Codeforces personalised problem recommender with progress tracking and contest simulation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s recommend --user tourist --mode stretch --count 10
  %(prog)s progress --user tourist
  %(prog)s contest --user tourist --division 2
  %(prog)s interactive
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    rec_parser = subparsers.add_parser(
        "recommend", aliases=["rec"], help="Get problem recommendations"
    )
    rec_parser.add_argument("--user", "-u", default=None, help="Codeforces handle")
    rec_parser.add_argument(
        "--count", "-n", type=int, default=8, help="Number of problems (default: 8)"
    )
    rec_parser.add_argument(
        "--mode",
        "-m",
        choices=["balanced", "stretch", "weak-topics", "explore", "grind"],
        default="balanced",
        help="Recommendation mode (default: balanced)",
    )
    rec_parser.add_argument(
        "--tags", default=None, help="Comma-separated required tags (e.g. dp,graphs)"
    )
    rec_parser.add_argument(
        "--min-rating", type=int, default=None, help="Minimum problem rating"
    )
    rec_parser.add_argument(
        "--max-rating", type=int, default=None, help="Maximum problem rating"
    )
    rec_parser.add_argument(
        "--platform",
        choices=["codeforces", "cses"],
        default=None,
        help="Filter by platform",
    )
    rec_parser.add_argument(
        "--show-topics", "-t", action="store_true", help="Show detailed topic breakdown"
    )
    rec_parser.add_argument("--json", action="store_true", help="Output as JSON")

    prog_parser = subparsers.add_parser(
        "progress", aliases=["prog"], help="Show progress and streaks"
    )
    prog_parser.add_argument("--user", "-u", required=True, help="Codeforces handle")
    prog_parser.add_argument("--json", action="store_true", help="Output as JSON")

    contest_parser = subparsers.add_parser(
        "contest", aliases=["con"], help="Simulate contest participation"
    )
    contest_parser.add_argument("--user", "-u", required=True, help="Codeforces handle")
    contest_parser.add_argument(
        "--division",
        "-d",
        type=int,
        default=2,
        choices=[1, 2, 3, 4],
        help="Contest division (default: 2)",
    )
    contest_parser.add_argument(
        "--count", "-n", type=int, default=5, help="Number of contests (default: 5)"
    )
    contest_parser.add_argument("--json", action="store_true", help="Output as JSON")

    subparsers.add_parser("interactive", aliases=["i"], help="Launch interactive mode")

    return parser.parse_args()


def get_recommendations_json(
    handle: str,
    count: int = 8,
    mode: str = "balanced",
    tag_filter: list = None,
    min_rating: int = None,
    max_rating: int = None,
    platform_filter: str = None,
) -> dict:
    profile = UserProfile(handle)
    profile.fetch()

    recommender = Recommender(profile)
    recommendations = recommender.recommend(
        count=count,
        mode=mode,
        tag_filter=tag_filter,
        min_rating=min_rating,
        max_rating=max_rating,
        platform_filter=platform_filter,
    )

    tracker = ProgressTracker(handle)
    streaks = tracker.get_current_streak(profile.submissions)

    return {
        "user": {
            "handle": profile.handle,
            "rating": profile.rating,
            "max_rating": profile.max_rating,
            "rank": profile.rank,
            "solved_count": len(profile.solved_set),
            "submission_streak": streaks["submission_streak"],
            "solve_streak": streaks["solve_streak"],
        },
        "recommendations": [
            {
                "rank": i + 1,
                "score": sc,
                "problem": p,
            }
            for i, (sc, p) in enumerate(recommendations)
        ],
        "mode": mode,
        "weak_topics": list(recommender.topic_analyzer.get_weak_tags(6)),
    }


def get_progress_json(handle: str) -> dict:
    profile = UserProfile(handle)
    profile.fetch()

    tracker = ProgressTracker(handle)
    tracker.update(profile.submissions)
    streaks = tracker.get_current_streak(profile.submissions)

    return {
        "user": {
            "handle": profile.handle,
            "rating": profile.rating,
            "max_rating": profile.max_rating,
            "rank": profile.rank,
            "solved_count": len(profile.solved_set),
        },
        "streaks": streaks,
        "rating_history": tracker.get_rating_graph(),
        "activity_history": tracker.get_activity_graph(),
    }


def get_contest_json(handle: str, division: int = 2, contest_count: int = 5) -> dict:
    profile = UserProfile(handle)
    profile.fetch()

    simulator = ContestSimulator(profile)
    contests = simulator.recommend_div_contests(division, contest_count)

    return {
        "user": {
            "handle": profile.handle,
            "rating": profile.rating,
        },
        "division": division,
        "contests": contests,
    }


def main():
    args = parse_args()

    if not args.command:
        print("No command specified. Use --help for usage or run 'interactive' mode.")
        print("\nQuick start:")
        print("  python recommender_enhanced.py recommend --user <handle>")
        print("  python recommender_enhanced.py interactive")
        sys.exit(0)

    if args.command in ["interactive", "i"]:
        interactive_mode()
        return

    if args.command in ["recommend", "rec"]:
        handle = args.user
        if not handle:
            handle = input("  Enter your Codeforces handle: ").strip()
        if not handle:
            print("No handle provided. Exiting.")
            sys.exit(1)

        tag_filter = [t.strip() for t in args.tags.split(",")] if args.tags else None

        if args.json:
            result = get_recommendations_json(
                handle,
                args.count,
                args.mode,
                tag_filter,
                args.min_rating,
                args.max_rating,
                args.platform,
            )
            print(json.dumps(result, indent=2))
        else:
            profile = UserProfile(handle)
            profile.fetch()

            recommender = Recommender(profile)
            recommendations = recommender.recommend(
                count=args.count,
                mode=args.mode,
                tag_filter=tag_filter,
                min_rating=args.min_rating,
                max_rating=args.max_rating,
                platform_filter=args.platform,
            )

            print_recommendations(
                profile,
                recommendations,
                args.mode,
                recommender.topic_analyzer,
                args.show_topics,
            )

    elif args.command in ["progress", "prog"]:
        if args.json:
            result = get_progress_json(args.user)
            print(json.dumps(result, indent=2))
        else:
            show_progress(args.user)

    elif args.command in ["contest", "con"]:
        if args.json:
            result = get_contest_json(args.user, args.division, args.count)
            print(json.dumps(result, indent=2))
        else:
            simulate_contest(args.user, args.division, args.count)


if __name__ == "__main__":
    main()
