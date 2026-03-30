import json
import os
import sys

from flask import Flask, jsonify, render_template, request

from core.practice.recommender import (
    ProblemLoader,
    UserProfile,
    get_contest_json,
    get_progress_json,
    get_recommendations_json,
)

app = Flask(__name__, static_folder="ui/static", template_folder="ui/template")


def load_db():
    db_path = os.path.join("data", "db.json")
    try:
        with open(db_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
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


@app.route("/api/recommendations")
def get_recommendations():
    handle = request.args.get("handle")
    count = int(request.args.get("count", 8))
    mode = request.args.get("mode", "balanced")
    tags = request.args.get("tags")
    min_rating = request.args.get("min_rating")
    max_rating = request.args.get("max_rating")
    platform = request.args.get("platform")

    if not handle:
        return jsonify({"success": False, "error": "Handle is required"}), 400

    min_rating = int(min_rating) if min_rating else None
    max_rating = int(max_rating) if max_rating else None
    tag_filter = [t.strip() for t in tags.split(",")] if tags else None

    try:
        result = get_recommendations_json(
            handle=handle,
            count=count,
            mode=mode,
            tag_filter=tag_filter,
            min_rating=min_rating,
            max_rating=max_rating,
            platform_filter=platform,
        )
        return jsonify({"success": True, "data": result})
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
