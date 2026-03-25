import json
import subprocess
import sys
from pathlib import Path

DB_FILE = "data/db.json"


def main():
    if not Path(DB_FILE).exists():
        print(f"No DB at {DB_FILE}. Nothing to retry.")
        sys.exit(0)

    with open(DB_FILE) as f:
        entries = json.load(f)

    failed: list[str] = []
    for e in entries:
        math_fail = e.get("description") == "GENERATION_FAILED"
        code_fail = "GENERATION_FAILED" in e.get("cpp", "")
        if math_fail or code_fail:
            failed.append(e["slug"])

    if not failed:
        print("No failures found in db.json. All good.")
        sys.exit(0)

    print(f"Found {len(failed)} failed topic(s):")
    for slug in failed:
        print(f"  → {slug}")

    print()
    for slug in failed:
        print(f"{'─' * 50}")
        print(f"Retrying: {slug}")
        result = subprocess.run(
            [sys.executable, "localModel.py", "--only", slug, "--regen"],
            check=False,
        )
        if result.returncode != 0:
            print(f"  ✗  still failed for {slug}")
        else:
            print(f"  ✓  {slug} done")

    print("\nRetry run complete.")


if __name__ == "__main__":
    main()
