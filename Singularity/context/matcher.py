"""
context/matcher.py
──────────────────
The Librarian's Search Engine — migrated to google-genai SDK.

Primary path  : Configurable Google embedding model via google-genai Client.
Fallback path : TF-IDF cosine similarity (runs offline, zero API cost).

OPTIMIZATION: KB vectors are precomputed ONCE at module load time.
Every request only needs 1 embed call (the query) + 1 matrix multiply.
"""

from __future__ import annotations

import os
import math
import logging
from typing import Optional

import numpy as np

from dotenv import load_dotenv
load_dotenv()

from context.samples import SCAM_SAMPLES

logger = logging.getLogger(__name__)

try:
    from google import genai
    _GENAI_AVAILABLE = True
except ImportError:
    _GENAI_AVAILABLE = False
    logger.warning("google-genai not installed — using TF-IDF fallback.")

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-005")


# ── TF-IDF fallback (precomputed at startup) ──────────────────────────────────

def _tokenize(text: str) -> list[str]:
    import re
    return re.findall(r"\w+", text.lower(), flags=re.UNICODE)


def _tfidf_vectors(docs: list[str]) -> list[dict[str, float]]:
    N = len(docs)
    tokenized = [_tokenize(d) for d in docs]
    df: dict[str, int] = {}
    for tokens in tokenized:
        for t in set(tokens):
            df[t] = df.get(t, 0) + 1
    vectors = []
    for tokens in tokenized:
        tf: dict[str, float] = {}
        for t in tokens:
            tf[t] = tf.get(t, 0) + 1
        vec = {
            t: (count / len(tokens)) * (math.log((N + 1) / (df.get(t, 0) + 1)) + 1)
            for t, count in tf.items()
        }
        vectors.append(vec)
    return vectors


def _cosine(a: dict, b: dict) -> float:
    keys = set(a) | set(b)
    dot  = sum(a.get(k, 0) * b.get(k, 0) for k in keys)
    na   = math.sqrt(sum(v * v for v in a.values()))
    nb   = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


_KB_CONTENTS      = [s["content"] for s in SCAM_SAMPLES]
_KB_TFIDF_VECTORS = _tfidf_vectors(_KB_CONTENTS)
_KB_DOCUMENT_FREQUENCY: dict[str, int] = {}
for _document in _KB_CONTENTS:
    for _token in set(_tokenize(_document)):
        _KB_DOCUMENT_FREQUENCY[_token] = _KB_DOCUMENT_FREQUENCY.get(_token, 0) + 1
logger.info("TF-IDF: precomputed %d KB vectors at startup.", len(_KB_TFIDF_VECTORS))


def _tfidf_match(email_body: str) -> tuple[dict, float]:
    tokens = _tokenize(email_body)
    counts: dict[str, int] = {}
    for token in tokens:
        counts[token] = counts.get(token, 0) + 1
    query_vec = {
        token: (count / len(tokens)) * (
            math.log((len(_KB_CONTENTS) + 1) / (_KB_DOCUMENT_FREQUENCY.get(token, 0) + 1)) + 1
        )
        for token, count in counts.items()
    }

    best_sample = SCAM_SAMPLES[0]
    best_raw    = 0.0
    for i, sample in enumerate(SCAM_SAMPLES):
        score = _cosine(query_vec, _KB_TFIDF_VECTORS[i])
        if score > best_raw:
            best_raw    = score
            best_sample = sample

    return best_sample, round(min(1.0, max(0.0, best_raw)), 4)


# ── Google embedding engine (preloaded KB matrix) ─────────────────────────────

def _get_client() -> "genai.Client":
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set.")
    return genai.Client(api_key=api_key)


def _embed(client: "genai.Client", text: str) -> np.ndarray:
    result = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text,
    )
    # Handle both single-embedding and batch response shapes
    embeddings = getattr(result, "embeddings", None)
    if embeddings:
        vec = np.array(embeddings[0].values, dtype=np.float32)
    else:
        vec = np.array(result.embedding.values, dtype=np.float32)
    norm = np.linalg.norm(vec)
    return vec / norm if norm else vec


_KB_EMBEDDING_MATRIX: Optional[np.ndarray] = None


def _maybe_preload_embeddings() -> None:
    global _KB_EMBEDDING_MATRIX
    api_key = os.getenv("GEMINI_API_KEY")
    if not (_GENAI_AVAILABLE and api_key):
        return
    try:
        client = _get_client()
        logger.info("Preloading %d KB embeddings via %s", len(SCAM_SAMPLES), EMBEDDING_MODEL)
        vecs = [_embed(client, s["content"]) for s in SCAM_SAMPLES]
        _KB_EMBEDDING_MATRIX = np.stack(vecs)
        logger.info("KB embedding matrix ready: %s", _KB_EMBEDDING_MATRIX.shape)
    except Exception as exc:
        logger.warning("Could not preload embeddings (%s) — will use TF-IDF.", exc)


_maybe_preload_embeddings()


def _embedding_match(email_body: str) -> tuple[dict, float]:
    client    = _get_client()
    query_vec = _embed(client, email_body)
    scores    = _KB_EMBEDDING_MATRIX @ query_vec
    best_idx  = int(np.argmax(scores))
    best_score = float(scores[best_idx])
    return SCAM_SAMPLES[best_idx], round(min(1.0, max(0.0, best_score)), 4)


# ── Public API ────────────────────────────────────────────────────────────────

def find_context_match(email_body: str) -> tuple[dict, float]:
    if _GENAI_AVAILABLE and _KB_EMBEDDING_MATRIX is not None:
        try:
            return _embedding_match(email_body)
        except Exception as exc:
            logger.warning("Embedding match failed (%s) — falling back to TF-IDF.", exc)
    return _tfidf_match(email_body)


# ── CLI test ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    test_msg = " ".join(sys.argv[1:]) or (
        "Your electricity will be disconnected at 9:30 PM. "
        "Call 9876543210 to avoid cut."
    )
    matched, score = find_context_match(test_msg)
    print(f"\nPattern : {matched['pattern']}")
    print(f"Score   : {score:.2%}")
    print(f"Category: {matched['category']}  [{matched['severity']}]")
