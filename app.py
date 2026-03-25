import json
import os

from flask import Flask, jsonify, render_template

app = Flask(__name__, static_folder="ui/static", template_folder="ui/template")


# Load database
def load_db():
    db_path = os.path.join("core", "data", "db.json")
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
    """Get all topics organized by category"""
    data = load_db()

    # Organize by category
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
    """Get a specific topic by slug"""
    data = load_db()

    for topic in data:
        if topic.get("slug") == slug:
            return jsonify(topic)

    return jsonify({"error": "Topic not found"}), 404


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
