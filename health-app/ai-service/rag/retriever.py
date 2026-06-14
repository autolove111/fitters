from __future__ import annotations

import re

from .vector_store import RetrievedChunk


class RetrievalError(Exception):
    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z0-9_+-]+|[\u4e00-\u9fff]+", text.lower()))


def _keyword_score(query_tokens: set[str], chunk: RetrievedChunk) -> float:
    chunk_tokens = _tokens(" ".join([chunk.text, chunk.title, " ".join(chunk.topics)]))
    if not query_tokens:
        return 0.0
    matches = len(query_tokens.intersection(chunk_tokens))
    topic_bonus = sum(1 for topic in chunk.topics if topic.lower() in query_tokens)
    return min(1.0, (matches + topic_bonus * 2) / max(4, len(query_tokens)))


def retrieve_chunks(query: str, store, embedder, *, vector_limit: int = 5, keyword_limit: int = 8) -> list[RetrievedChunk]:
    query_embedding = embedder.embed_query(query)
    vector_results = store.search(query_embedding, limit=vector_limit)
    query_tokens = _tokens(query)
    keyword_results = []
    for chunk in store.all_chunks():
        score = _keyword_score(query_tokens, chunk)
        if score > 0:
            chunk.keyword_score = score
            chunk.retrieval_sources = ["keyword"]
            keyword_results.append(chunk)
    keyword_results.sort(key=lambda item: (item.keyword_score, item.authority_score), reverse=True)

    merged: dict[str, RetrievedChunk] = {}
    for chunk in vector_results:
        chunk.keyword_score = _keyword_score(query_tokens, chunk)
        chunk.retrieval_sources = list(set((chunk.retrieval_sources or []) + ["vector"]))
        merged[chunk.chunk_id] = chunk
    for chunk in keyword_results[:keyword_limit]:
        if chunk.chunk_id in merged:
            merged[chunk.chunk_id].keyword_score = max(merged[chunk.chunk_id].keyword_score, chunk.keyword_score)
            merged[chunk.chunk_id].retrieval_sources = list(set((merged[chunk.chunk_id].retrieval_sources or []) + ["keyword"]))
        else:
            merged[chunk.chunk_id] = chunk
    return list(merged.values())
