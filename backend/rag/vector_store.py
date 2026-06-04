"""A tiny, dependency-free vector store (bonus: RAG).

Design constraints from the brief: must run on a normal laptop, no GPU, no paid
APIs, no heavy model downloads. So instead of pulling sentence-transformers, we
build a deterministic TF-IDF vectorizer over a small in-memory compliance
knowledge base and retrieve by cosine similarity using only numpy.

This is wired into the Risk agent: when a user asks the AI to *explain* a flag
or a policy, we retrieve the most relevant policy snippet and pass it to the LLM
as additional grounding — demonstrating retrieval-augmented orchestration
without external infrastructure. Easily swapped for a real vector DB
(pgvector / Chroma) in production behind the same `query()` interface.
"""
from __future__ import annotations

import math
import re
from collections import Counter

import numpy as np

# Compliance / policy knowledge base. In production this would be ingested
# documents; here it is curated text that mirrors the seeded risk rules.
KNOWLEDGE_BASE: list[dict] = [
    {
        "id": "CONC-25",
        "title": "Single-Asset Concentration Limit",
        "text": (
            "No single asset may represent more than 25 percent of total "
            "portfolio market value. Concentration breaches increase "
            "idiosyncratic risk and require portfolio manager review and a "
            "rebalancing plan."
        ),
    },
    {
        "id": "NOT-LRG",
        "title": "Large Notional Trade Control",
        "text": (
            "Any single trade with notional value above 500,000 USD must be "
            "escalated to risk for review before settlement. Large notional "
            "trades carry elevated market-impact and liquidity risk."
        ),
    },
    {
        "id": "MOV-10",
        "title": "Sharp Intraday Price Move",
        "text": (
            "Trades executed in assets that moved more than 10 percent intraday "
            "are flagged for volatility review. Sharp moves may indicate news "
            "events, liquidity gaps, or potential mispricing."
        ),
    },
    {
        "id": "RESTRICT-CR",
        "title": "Restricted Asset Class — Crypto",
        "text": (
            "Crypto-asset trades above 250,000 USD are restricted pending "
            "compliance sign-off due to custody, settlement-finality, and "
            "regulatory considerations for digital assets."
        ),
    },
    {
        "id": "REVIEW-FLOW",
        "title": "Trade Review Workflow",
        "text": (
            "Flagged trades enter a review queue. Risk and compliance officers "
            "assess each trade against active risk rules and either approve, "
            "reject, or request additional documentation. All decisions are "
            "audit-logged."
        ),
    },
    {
        "id": "DATA-LEAK",
        "title": "External LLM Data Leakage Policy",
        "text": (
            "Sensitive portfolio, trade, and client data must not be sent to "
            "external LLM providers. Use a local model such as Ollama, send "
            "only the minimal tool output required, and enforce role-based "
            "access control before any tool executes."
        ),
    },
]

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class VectorStore:
    """In-memory TF-IDF index with cosine retrieval."""

    def __init__(self, documents: list[dict]):
        self.documents = documents
        self._build()

    def _build(self) -> None:
        tokenized = [_tokenize(d["text"] + " " + d["title"]) for d in self.documents]
        n_docs = len(tokenized)

        # Vocabulary + inverse document frequency.
        df: Counter = Counter()
        for toks in tokenized:
            df.update(set(toks))
        self.vocab = {term: i for i, term in enumerate(sorted(df))}
        self.idf = np.zeros(len(self.vocab))
        for term, i in self.vocab.items():
            self.idf[i] = math.log((1 + n_docs) / (1 + df[term])) + 1.0

        # Document TF-IDF matrix (L2-normalized rows).
        self.matrix = np.zeros((n_docs, len(self.vocab)))
        for row, toks in enumerate(tokenized):
            self.matrix[row] = self._vectorize(toks)

    def _vectorize(self, tokens: list[str]) -> np.ndarray:
        vec = np.zeros(len(self.vocab))
        if not tokens:
            return vec
        tf = Counter(tokens)
        for term, count in tf.items():
            idx = self.vocab.get(term)
            if idx is not None:
                vec[idx] = (count / len(tokens)) * self.idf[idx]
        norm = np.linalg.norm(vec)
        return vec / norm if norm else vec

    def query(self, text: str, top_k: int = 2, min_score: float = 0.05) -> list[dict]:
        """Return the top_k most relevant documents with similarity scores."""
        q = self._vectorize(_tokenize(text))
        if not np.any(q):
            return []
        scores = self.matrix @ q  # rows already normalized; q normalized
        ranked = np.argsort(scores)[::-1]
        results = []
        for idx in ranked[:top_k]:
            score = float(scores[idx])
            if score < min_score:
                continue
            doc = dict(self.documents[idx])
            doc["score"] = round(score, 4)
            results.append(doc)
        return results


# Module-level singleton (cheap to build, fully deterministic).
store = VectorStore(KNOWLEDGE_BASE)


def retrieve_policy_context(question: str, top_k: int = 2) -> list[dict]:
    """Convenience wrapper used by the risk agent for RAG grounding."""
    return store.query(question, top_k=top_k)
