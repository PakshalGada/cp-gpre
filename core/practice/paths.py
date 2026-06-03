import os

_DATA_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "data")
)

PROBLEMS_CACHE = os.path.join(_DATA_DIR, "problems.json")
CSES_CACHE = os.path.join(_DATA_DIR, "cses_problems.json")
PROGRESS_CACHE = os.path.join(_DATA_DIR, "progress_{}.json")
CSES_PROGRESS_CACHE = os.path.join(_DATA_DIR, "cses_progress_{}.json")
