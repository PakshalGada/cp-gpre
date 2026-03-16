import argparse
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

KB_DIR = Path("../data/knowledgeBase")
INPUT_PATH = KB_DIR / "corpus_clean.json"
OUTPUT_PATH = KB_DIR / "chunks.json"


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    title: str
    url: str
    source: str
    category: str
    difficulty: str
    heading: str
    chunk_idx: int
    has_code: bool
    word_count: int
    text: str

    def to_dict(self) -> dict:
        return asdict(self)


_ABBREV = {
    "e.g",
    "i.e",
    "etc",
    "vs",
    "fig",
    "eq",
    "approx",
    "O",
    "n",
    "log",
    "sqrt",
    "max",
    "min",
}


def split_sentences(text: str) -> list[str]:
    """
    Split text into sentences using punctuation rules.
    Respects abbreviations so "O(n log n). Next…" splits correctly.
    """
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)

    sentences = []
    buf = []
    i, n = 0, len(text)

    while i < n:
        ch = text[i]
        buf.append(ch)

        if ch in ".!?" and i + 1 < n:
            next_ch = text[i + 1] if i + 1 < n else " "

            if next_ch in (" ", "\n"):
                # Check for abbreviation
                before = "".join(buf[:-1]).rstrip().split()
                last_word = before[-1].strip("()[]") if before else ""

                if last_word in _ABBREV:
                    i += 1
                    continue

                rest = text[i + 2 :].lstrip()
                if rest and rest[0].islower():
                    i += 1
                    continue

                sentence = "".join(buf).strip()
                if sentence:
                    sentences.append(sentence)
                buf = []

        i += 1

    remainder = "".join(buf).strip()
    if remainder:
        sentences.append(remainder)

    return [s for s in sentences if s]


def extract_code_blocks(text: str) -> tuple[str, list[str]]:
    """
    Pull fenced code blocks out of text.
    Replace each with [[CODE_0]], [[CODE_1]] … placeholders.
    Returns (text_with_placeholders, [code_block_strings]).
    """
    code_blocks = []

    def replace(match):
        idx = len(code_blocks)
        code_blocks.append(match.group(0))
        return f"\n[[CODE_{idx}]]\n"

    result = re.sub(r"```[\s\S]*?```", replace, text)
    return result, code_blocks


def restore_code_blocks(text: str, code_blocks: list[str]) -> tuple[str, bool]:
    """Put code blocks back. Returns (restored_text, has_code)."""
    has_code = False
    for i, block in enumerate(code_blocks):
        placeholder = f"[[CODE_{i}]]"
        if placeholder in text:
            text = text.replace(placeholder, f"\n{block}\n")
            has_code = True
    return text, has_code


def split_into_sections(text: str) -> list[tuple[str, str]]:
    """
    Split markdown text into (heading, body) pairs.
    Returns [("", intro_text), ("## Heading", section_body), …]
    """
    heading_re = re.compile(r"^(#{1,4})\s+(.+)$", re.MULTILINE)
    positions = [
        (m.start(), m.group(0), m.group(2).strip()) for m in heading_re.finditer(text)
    ]

    if not positions:
        return [("", text)]

    sections = []

    if positions[0][0] > 0:
        pre = text[: positions[0][0]].strip()
        if pre:
            sections.append(("", pre))

    positions.append((len(text), "", "__END__"))

    for idx, (pos, heading_line, heading_title) in enumerate(positions[:-1]):
        next_pos = positions[idx + 1][0]
        body = text[pos:next_pos]
        body = re.sub(r"^#{1,4}\s+.+\n?", "", body, count=1).strip()
        if body:
            sections.append((heading_title, body))

    return sections


def build_windows(
    sentences: list[str],
    max_words: int,
    overlap: int,
) -> list[str]:
    """
    Accumulate sentences into overlapping windows.

      - Keep adding sentences until word count >= max_words
      - Emit the window as a chunk
      - Drop sentences from the front until we've removed
        (max_words - overlap) words
      - Continue from there

    This gives us chunks of ~max_words words that share ~overlap
    words with their neighbours.
    """
    if not sentences:
        return []

    chunks = []
    window = []
    wwords = 0

    for sentence in sentences:
        sw = len(sentence.split())
        window.append(sentence)
        wwords += sw

        if wwords >= max_words:
            chunks.append(" ".join(window))

            target_drop = wwords - overlap
            dropped = 0
            while window and dropped < target_drop:
                dropped += len(window[0].split())
                window.pop(0)
            wwords -= dropped

    if window:
        chunks.append(" ".join(window))

    return chunks


class Chunker:
    def __init__(
        self,
        max_words: int = 350,
        overlap: int = 50,
        min_words: int = 40,
    ):
        self.max_words = max_words
        self.overlap = overlap
        self.min_words = min_words

    def chunk_doc(self, doc: dict) -> list[Chunk]:
        """Turn one corpus doc into a list of Chunk objects."""
        text = doc.get("text", "")
        chunks = []
        idx = 0

        for heading, body in split_into_sections(text):
            body_no_code, code_blocks = extract_code_blocks(body)

            sentences = split_sentences(body_no_code)
            windows = build_windows(sentences, self.max_words, self.overlap)

            for raw_window in windows:
                restored, has_code = restore_code_blocks(raw_window, code_blocks)

                cleaned = re.sub(r"\s{3,}", "\n\n", restored).strip()

                word_count = len(cleaned.split())
                if word_count < self.min_words:
                    continue

                chunk = Chunk(
                    chunk_id=f"{doc['doc_id']}__{idx}",
                    doc_id=doc["doc_id"],
                    title=doc.get("title", ""),
                    url=doc.get("url", ""),
                    source=doc.get("source", ""),
                    category=doc.get("category", "misc"),
                    difficulty=doc.get("difficulty", "unknown"),
                    heading=heading,
                    chunk_idx=idx,
                    has_code=has_code,
                    word_count=word_count,
                    text=cleaned,
                )
                chunks.append(chunk)
                idx += 1

        return chunks


def print_stats(chunks: list[Chunk]) -> None:
    total_words = sum(c.word_count for c in chunks)
    with_code = sum(1 for c in chunks if c.has_code)
    by_source = Counter(c.source for c in chunks)
    by_difficulty = Counter(c.difficulty for c in chunks)
    word_counts = [c.word_count for c in chunks]
    avg_words = total_words // max(len(chunks), 1)
    min_words = min(word_counts)
    max_words_val = max(word_counts)

    print(f"\n  ╔════════════════════════════════════════╗")
    print(f"  ║  Total chunks  : {len(chunks):<6,}                ║")
    print(f"  ║  Total words   : {total_words:<10,}          ║")
    print(f"  ║  Avg words     : {avg_words:<6}                ║")
    print(f"  ║  Min / Max     : {min_words} / {max_words_val:<6}           ║")
    print(f"  ║  With code     : {with_code:<6,}                ║")
    print(f"  ╚════════════════════════════════════════╝")

    print(f"\n  By source:")
    for src, n in by_source.most_common():
        bar = "▓" * (n * 25 // max(by_source.values()))
        print(f"    {src:<25s}  {bar:<25s}  {n:,}")

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
            bar = "▓" * (n * 25 // max(by_difficulty.values()))
            print(f"    {d:<25s}  {bar:<25s}  {n:,}")


def main(
    input_path: Path = INPUT_PATH,
    output_path: Path = OUTPUT_PATH,
    max_words: int = 350,
    overlap: int = 50,
    min_words: int = 40,
) -> list[Chunk]:

    if not input_path.exists():
        print(f"  ✗  Not found: {input_path}")
        print(f"     Run clean.py first:  python data/clean.py")
        return []

    print(f"\n  Loading {input_path} …")
    with open(input_path, encoding="utf-8") as f:
        raw = json.load(f)

    docs = [d for d in raw if not d.get("__meta__")]
    print(f"  {len(docs)} docs loaded")

    print(f"\n  Chunking  (max_words={max_words}, overlap={overlap}) …")

    chunker = Chunker(max_words=max_words, overlap=overlap, min_words=min_words)
    all_chunks: list[Chunk] = []

    for i, doc in enumerate(docs):
        chunks = chunker.chunk_doc(doc)
        all_chunks.extend(chunks)

        if (i + 1) % 100 == 0 or (i + 1) == len(docs):
            print(f"  {i + 1:>5}/{len(docs)}  chunks so far: {len(all_chunks):,}")

    print_stats(all_chunks)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    serialised = [c.to_dict() for c in all_chunks]
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(serialised, f, ensure_ascii=False, indent=2)

    size_mb = output_path.stat().st_size / 1e6
    print(f"\n  ✓  Saved → {output_path}  ({size_mb:.1f} MB)")
    print(f"\n  Next step: python core/embed.py")

    return all_chunks


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="cp-gpre chunker")
    p.add_argument("--input", default=str(INPUT_PATH))
    p.add_argument("--output", default=str(OUTPUT_PATH))
    p.add_argument(
        "--max-words",
        default=350,
        type=int,
        help="Target chunk size in words (default: 350)",
    )
    p.add_argument(
        "--overlap",
        default=50,
        type=int,
        help="Overlap between chunks in words (default: 50)",
    )
    p.add_argument(
        "--min-words",
        default=40,
        type=int,
        help="Drop chunks shorter than this (default: 40)",
    )
    args = p.parse_args()

    main(
        input_path=Path(args.input),
        output_path=Path(args.output),
        max_words=args.max_words,
        overlap=args.overlap,
        min_words=args.min_words,
    )
