import json
import os
import sys

from flask import Flask, jsonify, render_template, request

from core.practice.cses_profile import CsesLoginError
from core.practice.recommender import (
    ProblemLoader,
    UserProfile,
    get_contest_json,
    get_progress_json,
    get_recommendations_json,
)

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
    return render_template("practice.html")


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


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)
