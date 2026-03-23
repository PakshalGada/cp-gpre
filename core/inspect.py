import argparse
import json
import sys
from pathlib import Path

DB_FILE = "data/db.json"


def load() -> dict:
    if not Path(DB_FILE).exists():
        print(f"No DB at {DB_FILE}. Run:  python core/localModel.py")
        sys.exit(1)
    with open(DB_FILE) as f:
        return {e["slug"]: e for e in json.load(f)}


def cmd_stats(db: dict):
    total = len(db)
    math_fail = sum(
        1 for e in db.values() if e.get("description") == "GENERATION_FAILED"
    )
    code_fail = sum(1 for e in db.values() if "GENERATION_FAILED" in e.get("cpp", ""))

    cats: dict[str, int] = {}
    for e in db.values():
        cats[e["category"]] = cats.get(e["category"], 0) + 1

    print(f"  Total entries  : {total}")
    print(f"  Math failures  : {math_fail}")
    print(f"  Code failures  : {code_fail}")
    print(f"\n  By category:")
    for cat, n in sorted(cats.items(), key=lambda x: -x[1]):
        bar = "█" * (n * 30 // max(cats.values()))
        print(f"    {cat:<40s} {bar:<30s} {n}")


def cmd_show(db: dict, slug: str, field: str | None):
    if slug not in db:
        close = [s for s in db if slug in s]
        hint = f"  Similar slugs: {close[:5]}" if close else ""
        print(f"Slug '{slug}' not found.{hint}")
        return

    e = db[slug]
    if field:
        val = e.get(field)
        if val is None:
            print(f"Field '{field}' not in entry. Available: {list(e.keys())}")
        elif isinstance(val, (list, dict)):
            print(json.dumps(val, indent=2))
        else:
            print(val)
        return

    sep = "─" * 60
    print(f"\n{sep}")
    print(f"  {e['title']}")
    print(f"  Category : {e['category']}")
    print(f"  Tags     : {', '.join(e.get('tags', []))}")
    print(f"  Prereqs  : {', '.join(e.get('prereqs', [])) or 'None'}")
    print(f"  Leads to : {', '.join(e.get('leads_to', [])) or 'None'}")
    print(sep)
    print(f"\nDESCRIPTION\n{e.get('description', '')}")
    print(f"\nEXPLANATION\n{e.get('explanation', '')}")
    print(f"\nWORKED EXAMPLE\n{e.get('worked_example', '')}")
    print(f"\nPROOF\n{e.get('proof', '')}")
    print(f"\nCOMPLEXITY")
    print(f"  Time  : {e.get('time_complexity', '')}")
    print(f"  Space : {e.get('space_complexity', '')}")
    print(f"\nWHEN TO USE\n{e.get('when_to_use', '')}")
    print(f"\nKEY INSIGHT\n{e.get('key_insight', '')}")
    print(f"\nPITFALLS")
    for p in e.get("pitfalls", []):
        print(f"  • {p}")
    print(f"\nVARIANTS")
    for v in e.get("variants", []):
        print(f"  • {v}")
    print(f"\nC++ IMPLEMENTATION\n{e.get('cpp', '')}")
    print(f"\nCODE WALKTHROUGH\n{e.get('walkthrough', '')}")
    print(f"\nDRY RUN\n{e.get('dry_run', '')}")
    print(f"\nUSAGE EXAMPLE\n{e.get('usage_example', '')}")
    if e.get("cpp_notes"):
        print(f"\nNOTES")
        for n in e["cpp_notes"]:
            print(f"  • {n}")


def cmd_failed(db: dict):
    math_fails = [
        s for s, e in db.items() if e.get("description") == "GENERATION_FAILED"
    ]
    code_fails = [s for s, e in db.items() if "GENERATION_FAILED" in e.get("cpp", "")]

    print(f"Math failures ({len(math_fails)}):")
    for s in math_fails:
        print(f"  {s}")
    print(f"\nCode failures ({len(code_fails)}):")
    for s in code_fails:
        print(f"  {s}")


def cmd_category(db: dict, cat: str):
    matches = [e for e in db.values() if e["category"].lower() == cat.lower()]
    if not matches:
        all_cats = sorted(set(e["category"] for e in db.values()))
        print(f"Category '{cat}' not found. Available: {all_cats}")
        return
    print(f"{len(matches)} topics in '{cat}':")
    for e in sorted(matches, key=lambda x: x["id"]):
        ok = "✓" if e.get("description") != "GENERATION_FAILED" else "✗"
        print(f"  {ok}  {e['slug']:<40s}  {e['title']}")


def cmd_export(db: dict, slug: str):
    if slug not in db:
        print(f"Slug '{slug}' not found.")
        return
    print(json.dumps(db[slug], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inspect data/db.json")
    parser.add_argument(
        "command", choices=["stats", "show", "failed", "category", "export"]
    )
    parser.add_argument("arg", nargs="?", help="Slug or category name")
    parser.add_argument("--field", help="Show a single field from an entry")
    args = parser.parse_args()

    db = load()

    if args.command == "stats":
        cmd_stats(db)
    elif args.command == "show":
        cmd_show(db, args.arg or "", args.field)
    elif args.command == "failed":
        cmd_failed(db)
    elif args.command == "category":
        cmd_category(db, args.arg or "")
    elif args.command == "export":
        cmd_export(db, args.arg or "")
