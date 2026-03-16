import argparse
import json
import math
import re
from collections import Counter
from pathlib import Path

import numpy as np

KB_DIR = Path("data/knowledgeBase")
INPUT_PATH = KB_DIR / "chunks.json"
STORE_DIR = KB_DIR / "store"


STOPWORDS = {
    "the",
    "a",
    "an",
    "is",
    "it",
    "in",
    "of",
    "to",
    "and",
    "or",
    "for",
    "on",
    "at",
    "by",
    "as",
    "be",
    "we",
    "can",
    "that",
    "this",
    "with",
    "from",
    "are",
    "was",
    "were",
    "has",
    "have",
    "not",
    "but",
    "if",
    "so",
    "its",
    "also",
    "each",
    "then",
    "than",
    "such",
    "will",
    "use",
    "used",
    "let",
    "into",
    "using",
    "note",
    "one",
    "two",
    "first",
    "get",
    "more",
    "may",
    "need",
    "when",
    "which",
    "all",
    "there",
    "how",
    "some",
    "any",
    "now",
    "after",
    "example",
    "given",
    "output",
    "input",
    "set",
    "every",
    "like",
    "case",
    "well",
    "should",
    "what",
    "just",
    "since",
    "while",
    "here",
    "where",
    "same",
    "other",
    "following",
    "above",
    "below",
    "between",
}


def tokenize(text: str) -> list[str]:
    """
    Convert text to a list of clean tokens.

    Steps:
      1. Lowercase
      2. Normalise algorithm complexity:  O(n log n) → o_n_log_n
      3. Split on non-alphanumeric (keep underscores for variable_names)
      4. Remove stopwords and pure numbers
      5. Keep tokens length >= 2
    """
    text = text.lower()

    # Normalise O(n log n) style tokens → keep them as single token
    text = re.sub(
        r"o\(([^)]{1,30})\)",
        lambda m: "o_" + re.sub(r"[^a-z0-9]", "_", m.group(1)),
        text,
    )

    # Split on anything that isn't alphanumeric or underscore
    tokens = re.findall(r"[a-z0-9_]{2,}", text)

    # Remove stopwords and pure numbers
    tokens = [t for t in tokens if t not in STOPWORDS and not t.isdigit()]

    return tokens


def make_ngrams(tokens: list[str], max_n: int = 2) -> list[str]:
    """
    Add bigrams to the token list.
    e.g. ["segment", "tree"] → ["segment", "tree", "segment_tree"]
    """
    ngrams = list(tokens)
    if max_n >= 2:
        for i in range(len(tokens) - 1):
            ngrams.append(f"{tokens[i]}_{tokens[i + 1]}")
    return ngrams


class TFIDFVectorizer:
    """
    Builds a TF-IDF matrix from a list of text strings.

    Usage:
        vec    = TFIDFVectorizer()
        matrix = vec.fit_transform(texts)   # shape (N, vocab_size)
        q_vec  = vec.transform(["binary search"])  # shape (1, vocab_size)
        scores = matrix @ q_vec[0]          # cosine similarities
    """

    def __init__(
        self,
        max_features: int = 20000,
        min_df: int = 2,  # ignore tokens in fewer than N chunks
        max_df_ratio: float = 0.85,  # ignore tokens in more than X% of chunks
    ):
        self.max_features = max_features
        self.min_df = min_df
        self.max_df_ratio = max_df_ratio

        # Set after fit()
        self.vocab: dict[str, int] = {}
        self.idf: np.ndarray = None
        self.n_docs: int = 0

    def fit(self, texts: list[str]) -> "TFIDFVectorizer":
        """Build vocabulary and IDF weights from the corpus."""
        N = len(texts)
        self.n_docs = N

        print(f"  Building vocabulary from {N:,} chunks …")

        # Count document frequency for every token
        df: Counter = Counter()

        for text in texts:
            tokens = make_ngrams(tokenize(text))
            for token in set(tokens):  # set → count each token once per doc
                df[token] += 1

        # Filter by min_df and max_df_ratio
        max_df_abs = int(self.max_df_ratio * N)
        kept = {
            token: count
            for token, count in df.items()
            if self.min_df <= count <= max_df_abs
        }

        print(f"  Raw vocab: {len(df):,}  →  after filtering: {len(kept):,}")

        # Keep top max_features by document frequency
        top_tokens = sorted(kept, key=lambda t: -kept[t])[: self.max_features]

        # Build vocab index: token → column position in matrix
        self.vocab = {token: idx for idx, token in enumerate(top_tokens)}

        # Compute IDF weights
        # idf(t) = log((N + 1) / (df(t) + 1)) + 1
        # +1 smoothing prevents idf = 0 for very common tokens
        idf_arr = np.zeros(len(self.vocab), dtype=np.float32)
        for token, idx in self.vocab.items():
            idf_arr[idx] = math.log((N + 1) / (kept[token] + 1)) + 1.0

        self.idf = idf_arr
        print(f"  Vocabulary size: {len(self.vocab):,}")
        return self

    def transform(self, texts: list[str]) -> np.ndarray:
        """
        Convert texts to a TF-IDF matrix of shape (len(texts), vocab_size).
        Each row is L2-normalised — cosine similarity = dot product.
        """
        if not self.vocab:
            raise RuntimeError("Call fit() before transform()")

        V = len(self.vocab)
        matrix = np.zeros((len(texts), V), dtype=np.float32)

        for row, text in enumerate(texts):
            tokens = make_ngrams(tokenize(text))
            if not tokens:
                continue

            # Term frequency: count / total
            counts = Counter(tokens)
            total = len(tokens)

            for token, count in counts.items():
                if token in self.vocab:
                    col = self.vocab[token]
                    tf = count / total
                    matrix[row, col] = tf * self.idf[col]

        # L2 normalise each row
        # After this: cosine_sim(a, b) = a · b  (just a dot product)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1.0, norms)  # avoid div by zero
        matrix /= norms

        return matrix

    def fit_transform(self, texts: list[str]) -> np.ndarray:
        return self.fit(texts).transform(texts)

    def top_tokens(self, vec: np.ndarray, n: int = 10) -> list[tuple[str, float]]:
        """Return the top n tokens by weight in a vector. For debugging."""
        idx2token = {v: k for k, v in self.vocab.items()}
        top = np.argsort(vec)[::-1][:n]
        return [(idx2token[i], float(vec[i])) for i in top if vec[i] > 0]

    def save(self, store_dir: Path) -> None:
        store_dir.mkdir(parents=True, exist_ok=True)

        with open(store_dir / "vocab.json", "w") as f:
            json.dump(self.vocab, f)

        np.save(str(store_dir / "idf.npy"), self.idf)

        meta = {
            "n_docs": self.n_docs,
            "vocab_size": len(self.vocab),
            "max_features": self.max_features,
            "min_df": self.min_df,
            "max_df_ratio": self.max_df_ratio,
        }
        with open(store_dir / "vectorizer_meta.json", "w") as f:
            json.dump(meta, f, indent=2)

        print(f"  Vectorizer saved → {store_dir}/")

    @classmethod
    def load(cls, store_dir: Path) -> "TFIDFVectorizer":
        with open(store_dir / "vocab.json") as f:
            vocab = json.load(f)
        with open(store_dir / "vectorizer_meta.json") as f:
            meta = json.load(f)

        obj = cls(
            max_features=meta["max_features"],
            min_df=meta["min_df"],
            max_df_ratio=meta["max_df_ratio"],
        )
        obj.vocab = vocab
        obj.idf = np.load(str(store_dir / "idf.npy"))
        obj.n_docs = meta["n_docs"]

        print(f"  Vectorizer loaded: {len(vocab):,} tokens from {store_dir}/")
        return obj


def save_store(
    matrix: np.ndarray,
    chunks: list[dict],
    vectorizer: TFIDFVectorizer,
    store_dir: Path,
) -> None:
    store_dir.mkdir(parents=True, exist_ok=True)

    # Matrix (biggest file)
    np.save(str(store_dir / "matrix.npy"), matrix)
    print(f"  matrix.npy  {matrix.shape}  {matrix.nbytes / 1e6:.1f} MB")

    # Chunk metadata (text + all fields — returned in search results)
    with open(store_dir / "chunks.json", "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)
    print(f"  chunks.json  {len(chunks):,} chunks")

    # Vectorizer (vocab + IDF)
    vectorizer.save(store_dir)

    # Total store size
    total_mb = sum(f.stat().st_size for f in store_dir.iterdir() if f.is_file()) / 1e6
    print(f"  Total store size: {total_mb:.1f} MB")


def load_store(store_dir: Path) -> tuple[np.ndarray, list[dict], TFIDFVectorizer]:
    """Load the full store from disk. Used by search.py."""
    matrix = np.load(str(store_dir / "matrix.npy"))
    vectorizer = TFIDFVectorizer.load(store_dir)

    with open(store_dir / "chunks.json", encoding="utf-8") as f:
        chunks = json.load(f)

    print(f"  Store loaded: {len(chunks):,} chunks  matrix {matrix.shape}")
    return matrix, chunks, vectorizer


def main(
    input_path: Path = INPUT_PATH,
    store_dir: Path = STORE_DIR,
    max_features: int = 20000,
    min_df: int = 2,
) -> None:

    if not input_path.exists():
        print(f"  ✗  Not found: {input_path}")
        print(f"     Run chunker first:  python core/chunker.py")
        return

    print(f"\n  Loading {input_path} …")
    with open(input_path, encoding="utf-8") as f:
        chunks = json.load(f)

    print(f"  {len(chunks):,} chunks loaded")

    texts = [c["text"] for c in chunks]

    # ── Fit + transform ───────────────────────────────────────────────────────
    print(f"\n  Building TF-IDF matrix …")
    vec = TFIDFVectorizer(max_features=max_features, min_df=min_df)
    matrix = vec.fit_transform(texts)

    print(f"\n  Matrix shape  : {matrix.shape}")
    print(f"  Matrix size   : {matrix.nbytes / 1e6:.1f} MB")
    print(f"  Sparsity      : {(matrix == 0).sum() / matrix.size * 100:.1f}% zeros")

    # ── Save ──────────────────────────────────────────────────────────────────
    print(f"\n  Saving store → {store_dir}/ …")
    save_store(matrix, chunks, vec, store_dir)

    # ── Smoke test ────────────────────────────────────────────────────────────
    print(f"\n  Smoke test …")
    test_queries = [
        "binary search sorted array",
        "segment tree range query",
        "dynamic programming knapsack",
        "dijkstra shortest path",
        "suffix array string",
    ]
    for q in test_queries:
        q_vec = vec.transform([q])[0]
        scores = matrix @ q_vec
        top_i = int(np.argmax(scores))
        chunk = chunks[top_i]
        print(f'  [{scores[top_i]:.3f}]  "{q}"')
        print(
            f"           → [{chunk['source']}] "
            f"{chunk['title'][:50]}  |  {chunk['heading'][:35]}"
        )

    print(f"\n  ✓  Done.  Next step: python core/search.py")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="cp-gpre embedder")
    p.add_argument("--input", default=str(INPUT_PATH))
    p.add_argument("--store-dir", default=str(STORE_DIR))
    p.add_argument(
        "--max-features",
        default=20000,
        type=int,
        help="Vocabulary size cap (default: 20000)",
    )
    p.add_argument(
        "--min-df", default=2, type=int, help="Minimum document frequency (default: 2)"
    )
    args = p.parse_args()

    main(
        input_path=Path(args.input),
        store_dir=Path(args.store_dir),
        max_features=args.max_features,
        min_df=args.min_df,
    )
