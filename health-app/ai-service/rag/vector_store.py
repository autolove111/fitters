from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .ingestion import RAGChunk


@dataclass
class RetrievedChunk:
    chunk_id: str
    source: str
    title: str
    url: str
    authority_level: int
    topics: list[str]
    text: str
    embedding_model: str
    embedding_dim: int
    vector_score: float = 0
    keyword_score: float = 0
    authority_score: float = 0
    personal_score: float = 0
    rerank_score: float = 0
    retrieval_sources: list[str] | None = None

    def to_citation_dict(self, *, include_text: bool = False) -> dict[str, Any]:
        payload = {
            "chunkId": self.chunk_id,
            "source": self.source,
            "title": self.title,
            "url": self.url,
            "authorityLevel": self.authority_level,
            "relevanceScore": self.rerank_score or self.vector_score,
            "vectorScore": self.vector_score,
            "keywordScore": self.keyword_score,
            "rerankScore": self.rerank_score,
            "excerptChunk": self.text[:260],
        }
        if include_text:
            payload["text"] = self.text
        return payload


class SQLiteVectorStore:
    def __init__(self, path: str | Path, *, embedding_model: str = "text-embedding-v4", embedding_dim: int = 1024):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.embedding_model = embedding_model
        self.embedding_dim = int(embedding_dim)
        self._init_schema()

    def _connect(self):
        return sqlite3.connect(self.path)

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS rag_chunks (
                    chunk_id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT,
                    authority_level INTEGER DEFAULT 3,
                    topics TEXT,
                    chunk_index INTEGER,
                    text TEXT NOT NULL,
                    estimated_tokens INTEGER,
                    embedding_json TEXT NOT NULL,
                    embedding_model TEXT NOT NULL,
                    embedding_dim INTEGER NOT NULL,
                    source_path TEXT NOT NULL,
                    source_doc_hash TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_rag_source_path ON rag_chunks(source_path)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_rag_hash ON rag_chunks(content_hash)")

    def get_document_hash(self, source_path: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT source_doc_hash FROM rag_chunks WHERE source_path = ? LIMIT 1",
                (source_path,),
            ).fetchone()
        return str(row[0]) if row else None

    def replace_document_chunks(self, source_path: str, source_doc_hash: str, chunks: list[RAGChunk], embeddings: list[list[float]]) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings length mismatch")
        with self._connect() as conn:
            conn.execute("DELETE FROM rag_chunks WHERE source_path = ?", (source_path,))
            for chunk, embedding in zip(chunks, embeddings):
                conn.execute(
                    """
                    INSERT INTO rag_chunks (
                        chunk_id, source, title, url, authority_level, topics, chunk_index, text,
                        estimated_tokens, embedding_json, embedding_model, embedding_dim,
                        source_path, source_doc_hash, content_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        chunk.chunk_id,
                        chunk.source,
                        chunk.title,
                        chunk.url,
                        chunk.authority_level,
                        json.dumps(chunk.topics, ensure_ascii=False),
                        chunk.chunk_index,
                        chunk.text,
                        chunk.estimated_tokens,
                        json.dumps([float(value) for value in embedding]),
                        self.embedding_model,
                        len(embedding),
                        source_path,
                        source_doc_hash,
                        chunk.content_hash,
                    ),
                )

    def _load_rows(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT chunk_id, source, title, url, authority_level, topics, text,
                       embedding_json, embedding_model, embedding_dim
                FROM rag_chunks
                WHERE embedding_model = ?
                """,
                (self.embedding_model,),
            ).fetchall()
        return [dict(row) for row in rows]

    def count(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) FROM rag_chunks").fetchone()
        return int(row[0] or 0)

    def all_chunks(self) -> list[RetrievedChunk]:
        rows = self._load_rows()
        return [
            RetrievedChunk(
                chunk_id=row["chunk_id"],
                source=row["source"],
                title=row["title"],
                url=row["url"] or "",
                authority_level=int(row["authority_level"] or 3),
                topics=json.loads(row["topics"] or "[]"),
                text=row["text"],
                embedding_model=row["embedding_model"],
                embedding_dim=int(row["embedding_dim"]),
                authority_score=min(1.0, max(0.0, float(row["authority_level"] or 3) / 5)),
                retrieval_sources=[],
            )
            for row in rows
        ]

    def search(self, query_embedding: list[float], limit: int = 5) -> list[RetrievedChunk]:
        rows = self._load_rows()
        if not rows:
            return []
        vectors = np.array([json.loads(row["embedding_json"]) for row in rows], dtype=np.float32)
        query = np.array(query_embedding, dtype=np.float32)
        if vectors.shape[1] != query.shape[0]:
            return []
        vector_norm = np.linalg.norm(vectors, axis=1, keepdims=True)
        query_norm = np.linalg.norm(query)
        if query_norm == 0:
            return []
        scores = (vectors / np.maximum(vector_norm, 1e-12)) @ (query / query_norm)
        order = np.argsort(scores)[::-1][:limit]
        results: list[RetrievedChunk] = []
        for index in order:
            row = rows[int(index)]
            score = float(scores[int(index)])
            results.append(
                RetrievedChunk(
                    chunk_id=row["chunk_id"],
                    source=row["source"],
                    title=row["title"],
                    url=row["url"] or "",
                    authority_level=int(row["authority_level"] or 3),
                    topics=json.loads(row["topics"] or "[]"),
                    text=row["text"],
                    embedding_model=row["embedding_model"],
                    embedding_dim=int(row["embedding_dim"]),
                    vector_score=max(0.0, min(1.0, score)),
                    authority_score=min(1.0, max(0.0, float(row["authority_level"] or 3) / 5)),
                    retrieval_sources=["vector"],
                )
            )
        return results
