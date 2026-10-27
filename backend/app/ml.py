from __future__ import annotations

import hashlib
import itertools
import logging
import re
from collections.abc import Sequence
from typing import Protocol

import numpy as np

from .config import Settings

logger = logging.getLogger(__name__)


class Embedder(Protocol):
    name: str
    dimension: int
    degraded: bool

    def encode(self, texts: Sequence[str]) -> np.ndarray: ...


def _normalise(matrix: np.ndarray) -> np.ndarray:
    if matrix.size == 0:
        return matrix
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return (matrix / norms).astype(np.float32)


class FastEmbedder:
    degraded = False

    def __init__(self, model_name: str, cache_dir: str | None = None):
        from fastembed import TextEmbedding

        self._model = TextEmbedding(model_name=model_name, cache_dir=cache_dir)
        self.name = f"fastembed:{model_name}"
        warmup = self._encode_raw(["warmup"])
        self.dimension = int(warmup.shape[1])

    def _encode_raw(self, texts: Sequence[str]) -> np.ndarray:
        vectors = list(self._model.embed(list(texts), batch_size=32))
        if not vectors:
            return np.zeros((0, self.dimension if hasattr(self, "dimension") else 384), dtype=np.float32)
        return np.asarray(vectors, dtype=np.float32)

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dimension), dtype=np.float32)
        return _normalise(self._encode_raw(texts))


class SentenceTransformerEmbedder:
    degraded = False

    def __init__(self, model_name: str, cache_dir: str | None = None):
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name, cache_folder=cache_dir)
        self.name = f"sentence-transformers:{model_name}"
        self.dimension = int(self._model.get_sentence_embedding_dimension())

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dimension), dtype=np.float32)
        vectors = self._model.encode(
            list(texts),
            batch_size=32,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return np.asarray(vectors, dtype=np.float32)


class HashingEmbedder:
    """Deterministic, dependency-free fallback for tests and degraded mode.

    It is intentionally lexical: useful for smoke tests and CI, not a substitute
    for a semantic model.
    """

    degraded = True
    dimension = 384

    def __init__(self) -> None:
        self.name = "hash:tf-idf-ish"

    @staticmethod
    def _tokens(text: str) -> list[str]:
        words = re.findall(r"[a-z0-9+#.]{2,}", text.lower())
        bigrams = [f"{a}_{b}" for a, b in itertools.pairwise(words)]
        return words + bigrams

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        matrix = np.zeros((len(texts), self.dimension), dtype=np.float32)
        for row, text in enumerate(texts):
            for token in self._tokens(text):
                digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
                index = int.from_bytes(digest[:4], "big") % self.dimension
                sign = 1.0 if digest[4] & 1 else -1.0
                matrix[row, index] += sign
        return _normalise(matrix)


def build_embedder(settings: Settings) -> Embedder:
    backend = settings.embedder_backend
    if backend == "hash":
        return HashingEmbedder()

    if backend in {"auto", "fastembed"}:
        try:
            return FastEmbedder(settings.fastembed_model, settings.embedder_cache_dir)
        except Exception as exc:
            logger.warning("fastembed unavailable: %s", exc)
            if backend == "fastembed":
                raise

    if backend in {"auto", "sentence-transformers"}:
        try:
            return SentenceTransformerEmbedder(settings.model_name, settings.embedder_cache_dir)
        except Exception as exc:
            logger.warning("sentence-transformers unavailable: %s", exc)
            if backend == "sentence-transformers":
                raise

    logger.warning("Falling back to the lexical hash embedder; semantic scoring is degraded.")
    return HashingEmbedder()


def cosine_similarity(matrix: np.ndarray, vector: np.ndarray) -> np.ndarray:
    if matrix.size == 0:
        return np.zeros((0,), dtype=np.float32)
    return np.asarray(matrix @ vector, dtype=np.float32).reshape(-1)
