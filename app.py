import json
import os
import sys
import threading

from flask import Flask, jsonify, redirect, render_template, request

from core.practice.cses_profile import CsesLoginError
from core.practice.recommender import (
    ProblemLoader,
    UserProfile,
    get_contest_json,
    get_progress_json,
    get_recommendations_json,
    get_virtual_contest_json,
)
from core.practice.ProblemList import fetch_codeforces_problems, save_codeforces_problems
from core.practice.scrape_cses import scrape_cses_problems, save_cses_problems
from scripts.fetch_practice_problems import fetch_codeforces as fetch_cf_div, fetch_atcoder


def run_auto_scrapers():
    print("=== STARTING AUTO BACKGROUND SCRAPING ===")
    try:
        # 1. Fetch Codeforces problems
        cf_problems = fetch_codeforces_problems()
        save_codeforces_problems(cf_problems)
    except Exception as e:
        print(f"Auto-scraper Codeforces problems error: {e}")

    try:
        # 2. Fetch CSES problems
        cses_problems = scrape_cses_problems()
        save_cses_problems(cses_problems)
    except Exception as e:
        print(f"Auto-scraper CSES problems error: {e}")

    try:
        # 3. Fetch CF div contests/problems
        fetch_cf_div()
    except Exception as e:
        print(f"Auto-scraper CF div problems error: {e}")

    try:
        # 4. Fetch AtCoder contests/problems
        fetch_atcoder()
    except Exception as e:
        print(f"Auto-scraper AtCoder problems error: {e}")

    print("=== AUTO BACKGROUND SCRAPING COMPLETE ===")


def start_background_scraping():
    if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        thread = threading.Thread(target=run_auto_scrapers, daemon=True)
        thread.start()


app = Flask(__name__, static_folder="ui/static", template_folder="ui/template")


_db_cache = None
_db_last_mtime = 0


def load_db():
    global _db_cache, _db_last_mtime
    db_path = os.path.join("data", "db.json")
    try:
        mtime = os.path.getmtime(db_path)
        if _db_cache is None or mtime > _db_last_mtime:
            with open(db_path, "r", encoding="utf-8") as f:
                _db_cache = json.load(f)
                _db_last_mtime = mtime
        return _db_cache
    except (FileNotFoundError, OSError):
        return []



@app.route("/")
def index():
    return render_template("index.html")


@app.route("/resource")
def resource():
    return render_template("resource.html")


@app.route("/practice")
def practice():
    return redirect("/practice/recommender")


@app.route("/practice/recommender")
def practice_recommender():
    return render_template("practice_recommender.html")


@app.route("/practice/progress")
def practice_progress():
    return render_template("progress.html")


@app.route("/practice/contest")
def practice_contest():
    return render_template("practice_contest.html")


@app.route("/api/topics")
def get_topics():
    data = load_db()
    categories = {}
    for topic in data:
        category = topic.get("category", "Uncategorized")
        if category not in categories:
            categories[category] = []
        categories[category].append(
            {
                "id": topic.get("id"),
                "slug": topic.get("slug"),
                "title": topic.get("title"),
                "tags": topic.get("tags", []),
            }
        )
    return jsonify(categories)


@app.route("/api/topic/<slug>")
def get_topic(slug):
    data = load_db()
    for topic in data:
        if topic.get("slug") == slug:
            return jsonify(topic)
    return jsonify({"error": "Topic not found"}), 404


@app.route("/api/search")
def search_topics():
    query = request.args.get("q", "").strip().lower()
    if not query:
        return jsonify([])

    data = load_db()
    results = []
    for topic in data:
        slug = topic.get("slug")
        title = topic.get("title", "")
        category = topic.get("category", "")
        tags = topic.get("tags", [])

        match_in = []
        if query in title.lower():
            match_in.append("title")
        if query in category.lower():
            match_in.append("category")
        for tag in tags:
            if query in tag.lower():
                match_in.append("tags")
                break

        # Check other rich content fields for deep search
        text_fields = {
            "description": topic.get("description"),
            "explanation": topic.get("explanation"),
            "key_insight": topic.get("key_insight"),
            "worked_example": topic.get("worked_example"),
            "when_to_use": topic.get("when_to_use"),
            "variants": topic.get("variants"),
            "pitfalls": topic.get("pitfalls"),
            "prereqs": topic.get("prereqs"),
            "leads_to": topic.get("leads_to"),
            "cpp_notes": topic.get("cpp_notes"),
            "walkthrough": topic.get("walkthrough"),
            "proof": topic.get("proof"),
        }

        for name, value in text_fields.items():
            if value:
                if isinstance(value, list):
                    parts = []
                    for item in value:
                        if isinstance(item, str):
                            parts.append(item)
                        elif isinstance(item, dict):
                            for v in item.values():
                                if isinstance(v, str):
                                    parts.append(v)
                        else:
                            parts.append(str(item))
                    joined = " ".join(parts).lower()
                    if query in joined:
                        match_in.append(name)
                elif isinstance(value, str):
                    if query in value.lower():
                        match_in.append(name)

        if match_in:
            results.append({
                "slug": slug,
                "title": title,
                "category": category,
                "match_in": match_in
            })

    return jsonify(results)


def _parse_recommendation_request():
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
        getter = payload.get
    else:
        getter = request.args.get

    handle = getter("handle")
    count = int(getter("count", 8))
    mode = getter("mode", "balanced")
    tags = getter("tags")
    min_rating = getter("min_rating")
    max_rating = getter("max_rating")
    platform = getter("platform")
    cses_user = getter("cses_user")
    cses_password = getter("cses_password") if request.method == "POST" else None

    min_rating = int(min_rating) if min_rating else None
    max_rating = int(max_rating) if max_rating else None
    tag_filter = [t.strip() for t in tags.split(",")] if tags else None

    return {
        "handle": handle,
        "count": count,
        "mode": mode,
        "tag_filter": tag_filter,
        "min_rating": min_rating,
        "max_rating": max_rating,
        "platform_filter": platform,
        "cses_user": cses_user,
        "cses_password": cses_password,
    }


@app.route("/api/recommendations", methods=["GET", "POST"])
def get_recommendations():
    params = _parse_recommendation_request()

    if not params["handle"]:
        return jsonify({"success": False, "error": "Handle is required"}), 400

    try:
        result = get_recommendations_json(**params)
        return jsonify({"success": True, "data": result})
    except CsesLoginError as e:
        return jsonify({"success": False, "error": str(e)}), 401
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/cses/progress", methods=["POST"])
def sync_cses_progress():
    payload = request.get_json(silent=True) or {}
    cses_user = payload.get("cses_user")
    cses_password = payload.get("cses_password")

    if not cses_user or not cses_password:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "cses_user and cses_password are required.",
                }
            ),
            400,
        )

    try:
        from core.practice.cses_profile import CsesProfile

        profile = CsesProfile(cses_user, cses_password)
        solved = profile.fetch(force_refresh=True)
        return jsonify(
            {
                "success": True,
                "data": {
                    "username": profile.username,
                    "solved_count": len(solved),
                    "solved_ids": list(solved),
                    "updated_at": profile.updated_at,
                },
            }
        )
    except CsesLoginError as e:
        return jsonify({"success": False, "error": str(e)}), 401
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/progress")
def get_progress():
    handle = request.args.get("handle")

    if not handle:
        return jsonify({"success": False, "error": "Handle is required"}), 400

    try:
        result = get_progress_json(handle)
        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/contest")
def get_contest():
    handle = request.args.get("handle")
    division = int(request.args.get("division", 2))
    count = int(request.args.get("count", 5))

    if not handle:
        return jsonify({"success": False, "error": "Handle is required"}), 400

    try:
        result = get_contest_json(handle, division, count)
        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/contest/generate")
def generate_contest():
    handle = request.args.get("handle")
    division = int(request.args.get("division", 2))
    count = int(request.args.get("count", 5))

    if not handle:
        return jsonify({"success": False, "error": "Handle is required"}), 400

    try:
        result = get_virtual_contest_json(handle, division, count)
        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/user/stats")
def get_user_stats():
    handle = request.args.get("handle")

    if not handle:
        return jsonify({"success": False, "error": "Handle is required"}), 400

    try:
        profile = UserProfile(handle)
        profile.fetch()
        result = {
            "handle": profile.handle,
            "rating": profile.rating,
            "max_rating": profile.max_rating,
            "rank": profile.rank,
            "solved_count": len(profile.solved_set),
        }
        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/problems")
def get_problems():
    platform = request.args.get("platform")

    try:
        if platform == "codeforces":
            problems = ProblemLoader.load_codeforces()
        elif platform == "cses":
            problems = ProblemLoader.load_cses()
        else:
            problems = ProblemLoader.load_all()
        return jsonify({"success": True, "data": problems, "count": len(problems)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/compare")
def compare_users():
    handles = request.args.get("handles", "").split(",")
    handles = [h.strip() for h in handles if h.strip()]

    if not handles:
        return jsonify({"success": False, "error": "Handles are required"}), 400

    try:
        results = []
        for handle in handles:
            profile = UserProfile(handle)
            profile.fetch()
            results.append(
                {
                    "handle": profile.handle,
                    "rating": profile.rating,
                    "max_rating": profile.max_rating,
                    "rank": profile.rank,
                    "solved_count": len(profile.solved_set),
                }
            )
        return jsonify({"success": True, "data": results})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/practice/problems")
def practice_problems():
    return render_template("practice_problems.html")


@app.route("/api/practice/codeforces")
def api_practice_codeforces():
    cf_path = os.path.join("data", "codeforces_div_problems.json")
    try:
        with open(cf_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return jsonify({"success": True, "data": data})
    except Exception as e:
        return jsonify({"success": False, "error": f"Failed to load Codeforces problems: {str(e)}"}), 500


@app.route("/api/practice/atcoder")
def api_practice_atcoder():
    ac_path = os.path.join("data", "atcoder_problems.json")
    try:
        with open(ac_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return jsonify({"success": True, "data": data})
    except Exception as e:
        return jsonify({"success": False, "error": f"Failed to load AtCoder problems: {str(e)}"}), 500


@app.route("/api/practice/solved")
def api_practice_solved():
    cf_handle = request.args.get("handle", "").strip()
    atcoder_handle = request.args.get("atcoder_handle", "").strip()

    solved_cf = []
    solved_ac = []

    if cf_handle:
        try:
            profile = UserProfile(cf_handle)
            profile.fetch()
            solved_cf = [f"{cid}{idx}" for cid, idx in profile.solved_set]
        except Exception as e:
            print(f"Error fetching Codeforces solved for {cf_handle}: {e}")

    if atcoder_handle:
        try:
            import requests
            url = f"https://kenkoooo.com/atcoder/atcoder-api/v3/user/submissions?user={atcoder_handle}&from_second=0"
            r = requests.get(url, timeout=15)
            if r.status_code == 200:
                subs = r.json()
                solved_ac = [sub["problem_id"] for sub in subs if sub.get("result") == "AC"]
        except Exception as e:
            print(f"Error fetching AtCoder solved for {atcoder_handle}: {e}")

    return jsonify({
        "success": True,
        "codeforces": solved_cf,
        "atcoder": solved_ac
    })


if __name__ == "__main__":
    app.debug = True
    start_background_scraping()
    app.run(host="0.0.0.0", debug=True)
