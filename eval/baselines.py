from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.ml import FastEmbedder, HashingEmbedder, cosine_similarity


class TfidfBaseline:
    def __init__(self) -> None:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity as sklearn_cosine

        self.vectorizer = TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 2),
            sublinear_tf=True,
            max_features=50_000,
        )
        self.cosine = sklearn_cosine

    def fit(self, texts: list[str]) -> TfidfBaseline:
        self.vectorizer.fit(texts)
        return self

    def score_pair(self, resume: str, jd: str) -> float:
        matrix = self.vectorizer.transform([resume, jd])
        return float(self.cosine(matrix[0], matrix[1])[0, 0])


class EmbeddingBaseline:
    def __init__(self, kind: str = "fastembed") -> None:
        self.embedder = (
            FastEmbedder("sentence-transformers/all-MiniLM-L6-v2")
            if kind == "fastembed"
            else HashingEmbedder()
        )

    def score_pair(self, resume: str, jd: str) -> float:
        vectors = self.embedder.encode([resume, jd])
        return float(cosine_similarity(vectors[:1], vectors[1])[0])


class CrossEncoderBaseline:
    def __init__(self, model_name: str = "BAAI/bge-reranker-base") -> None:
        from sentence_transformers import CrossEncoder

        self.model = CrossEncoder(model_name)

    def score_pair(self, resume: str, jd: str) -> float:
        score = self.model.predict([(jd, resume)])[0]
        return float(score)


class MatcherBaseline:
    """The production local pipeline, including PII redaction before embeddings."""

    def __init__(self) -> None:
        from app.ml import FastEmbedder
        from app.services.matcher import Calibrator, RoleMatcher
        from app.services.nlp_analyzer import NLPAnalyzer
        from app.services.taxonomy import get_roles, get_taxonomy

        taxonomy = get_taxonomy()
        self.nlp = NLPAnalyzer(taxonomy)
        self.matcher = RoleMatcher(
            taxonomy,
            get_roles(),
            FastEmbedder("sentence-transformers/all-MiniLM-L6-v2"),
            Calibrator(),
        )

    def score_pair(self, resume: str, jd: str) -> float:
        lines = tuple(line for line in resume.splitlines() if line.strip())
        nlp = self.nlp.analyze(resume, lines)
        result = self.matcher.match(resume, lines, nlp, "Software Engineer", jd)
        return float(result.score)


class OpenCodeBaseline:
    def __init__(self) -> None:
        from app.config import Settings
        from app.services.llm_scorer import LLMScorer
        from app.services.nlp_analyzer import NLPAnalyzer
        from app.services.taxonomy import get_taxonomy

        self.settings = Settings()
        if not self.settings.llm_configured:
            raise RuntimeError(
                "Set LLM_ENABLED=true and OPENCODE_API_KEY to run this baseline."
            )
        self.scorer = LLMScorer(self.settings)
        self.nlp = NLPAnalyzer(get_taxonomy())

    async def score_pair(self, resume: str, jd: str) -> float:
        lines = tuple(line for line in resume.splitlines() if line.strip())
        result = self.nlp.analyze(resume, lines)
        outcome = await self.scorer.score(
            resume_text=resume,
            lines=lines,
            target_role="Target role",
            role_description=jd,
            skills=result.skills,
            jd_text=jd,
        )
        if outcome is None:
            return 0.0
        return outcome.score


def build_baseline(name: str, pairs: list[dict]):
    if name == "tfidf":
        corpus = []
        for pair in pairs:
            corpus.extend([pair["resume_text"], pair["jd_text"]])
        return TfidfBaseline().fit(corpus)
    if name == "hash":
        return EmbeddingBaseline("hash")
    if name == "minilm":
        return EmbeddingBaseline("fastembed")
    if name == "matcher":
        return MatcherBaseline()
    if name == "cross-encoder":
        return CrossEncoderBaseline()
    if name == "opencode":
        return OpenCodeBaseline()
    raise ValueError(f"Unknown baseline: {name}")


def predict_sync(baseline, pairs: list[dict]) -> list[float]:
    return [
        float(baseline.score_pair(pair["resume_text"], pair["jd_text"]))
        for pair in pairs
    ]


async def predict_async(baseline, pairs: list[dict]) -> list[float]:
    return [
        float(await baseline.score_pair(pair["resume_text"], pair["jd_text"]))
        for pair in pairs
    ]
