import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper.resource import cpAlgorithms, cph, usaco

KB_DIR = Path("../data/knowledgeBase")
CORPUS_PATH = KB_DIR / "corpus.json"
RAW_DIR = KB_DIR / "raw"


def _validate(docs: list[dict]) -> None:
    """
    Check every doc has the required fields and sensible content.
    Raises ValueError if anything is wrong.
    """
    required = {"doc_id", "title", "url", "source", "text"}
    errors = []
    seen_ids: set[str] = set()

    for i, doc in enumerate(docs):
        # Missing keys
        for key in required:
            if key not in doc or not doc[key]:
                errors.append(
                    f"doc[{i}] missing/empty '{key}'  (doc_id={doc.get('doc_id')})"
                )

        # Too short
        words = len(doc.get("text", "").split())
        if words < 40:
            errors.append(
                f"doc[{i}] text too short ({words} words)  (doc_id={doc.get('doc_id')})"
            )

        # Duplicate IDs
        did = doc.get("doc_id", "")
        if did in seen_ids:
            errors.append(f"doc[{i}] duplicate doc_id: {did!r}")
        seen_ids.add(did)

    if errors:
        print(f"\n  ✗  {len(errors)} validation errors:")
        for e in errors[:15]:
            print(f"      {e}")
        raise ValueError(f"Corpus validation failed ({len(errors)} errors)")

    print(f"  ✓  All {len(docs)} docs passed validation")


def _print_stats(docs: list[dict]) -> None:
    total_words = sum(len(d["text"].split()) for d in docs)
    with_code = sum(1 for d in docs if "```" in d.get("text", ""))
    by_source = Counter(d["source"] for d in docs)
    by_difficulty = Counter(d.get("difficulty", "unknown") for d in docs)

    print(f"\n  ╔══════════════════════════════════╗")
    print(f"  ║  Total docs   :  {len(docs):<5}           ║")
    print(f"  ║  Total words  :  {total_words:<10,}     ║")
    print(f"  ║  With code    :  {with_code:<5}           ║")
    print(f"  ╚══════════════════════════════════╝")

    print(f"\n  By source:")
    for src, n in by_source.most_common():
        bar = "▓" * (n * 20 // max(by_source.values()))
        print(f"    {src:<22s}  {bar:<20s}  {n}")

    print(f"\n  By difficulty:")
    order = [
        "beginner",
        "intermediate",
        "advanced-intermediate",
        "advanced",
        "expert",
        "unknown",
    ]
    for d in order:
        n = by_difficulty.get(d, 0)
        if n:
            print(f"    {d:<25s}  {n}")


def _save_raw(docs: list[dict]) -> None:
    """Save each doc's text as a .txt file in data/knowledgeBase/raw/<source>/"""
    saved = 0
    for doc in docs:
        source = doc["source"]
        folder = RAW_DIR / source
        folder.mkdir(parents=True, exist_ok=True)

        safe_name = doc["doc_id"].replace("/", "_").replace("\\", "_")[:150]
        file_path = folder / f"{safe_name}.txt"
        file_path.write_text(doc["text"], encoding="utf-8", errors="ignore")
        saved += 1

    print(f"  Raw backups saved to {RAW_DIR}/  ({saved} files)")


SCRAPERS = {
    "cp-algorithms": cpAlgorithms.scrape,
    "usaco": usaco.scrape,
    "cph": cph.scrape,
}


def build(sources: list[str] = None, save_raw: bool = True) -> list[dict]:
    """
    Run the specified scrapers (default: all three) and write corpus.json.

    Args:
        sources  : list of source names to run, e.g. ["cp-algorithms", "cph"]
                   If None, all three scrapers are run.
        save_raw : if True, also save per-doc .txt backups to raw/

    Returns:
        list of all doc dicts
    """
    sources = sources or list(SCRAPERS.keys())

    KB_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 55)
    print("  cp-gpre · Knowledge Base Builder")
    print("=" * 55)

    all_docs: list[dict] = []

    for source in sources:
        if source not in SCRAPERS:
            print(f"\n  Unknown source: {source!r} — skipping")
            print(f"  Valid sources: {list(SCRAPERS.keys())}")
            continue

        print(f"\n── {source} ──────────────────────────────────────")
        try:
            docs = SCRAPERS[source]()
            all_docs.extend(docs)
            print(f"  Collected {len(docs)} docs  (running total: {len(all_docs)})")
        except Exception as e:
            print(f"  ✗  {source} failed: {e}")
            import traceback

            traceback.print_exc()

    if not all_docs:
        print("\n  No docs collected — nothing to save.")
        return []

    print(f"\n── Validation ─────────────────────────────────────")
    _validate(all_docs)

    _print_stats(all_docs)
    if save_raw:
        print(f"\n── Saving raw backups ──────────────────────────────")
        _save_raw(all_docs)
    print(f"\n── Saving corpus.json ──────────────────────────────")

    output = [
        {
            "__meta__": True,
            "built_at": datetime.now(timezone.utc).isoformat(),
            "sources": sources,
            "total": len(all_docs),
        }
    ] + all_docs

    with open(CORPUS_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    size_mb = CORPUS_PATH.stat().st_size / 1e6
    print(f"  Saved → {CORPUS_PATH}  ({size_mb:.1f} MB)")

    print(f"\n{'=' * 55}")
    print(f"  Build complete!")
    print(f"  {len(all_docs)} docs in {CORPUS_PATH}")
    print(f"  Next step: run the chunker on corpus.json")
    print(f"{'=' * 55}\n")

    return all_docs


def _cli():
    p = argparse.ArgumentParser(
        description="cp-gpre knowledge base builder",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m scraper.base                            # run all three
  python -m scraper.base --sources cp-algorithms    # only cp-algorithms
  python -m scraper.base --sources usaco cph        # usaco + cph only
  python -m scraper.base --no-raw                   # skip raw backups
        """,
    )
    p.add_argument(
        "--sources",
        nargs="+",
        choices=list(SCRAPERS.keys()),
        default=None,
        help="Which sources to scrape (default: all)",
    )
    p.add_argument(
        "--no-raw",
        action="store_true",
        help="Skip saving raw .txt backup files",
    )
    args = p.parse_args()
    build(sources=args.sources, save_raw=not args.no_raw)


if __name__ == "__main__":
    _cli()
