from __future__ import annotations

import os
from typing import Any

import requests


class EmbeddingError(Exception):
    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


class DashScopeEmbeddingClient:
    def __init__(self, *, api_key: str | None = None, base_url: str | None = None, model: str | None = None, dim: int | None = None):
        self.api_key = api_key if api_key is not None else os.getenv("OPENAI_API_KEY", "")
        self.base_url = (base_url or os.getenv("OPENAI_BASE_URL") or "https://dashscope.aliyuncs.com/compatible-mode/v1").rstrip("/")
        self.model = model or os.getenv("EMBEDDING_MODEL") or "text-embedding-v4"
        self.dim = int(dim or os.getenv("EMBEDDING_DIM") or 1024)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if not self.api_key:
            raise EmbeddingError("EMBEDDING_API_ERROR", "OPENAI_API_KEY is required for embeddings")
        all_embeddings: list[list[float]] = []
        for start in range(0, len(texts), 10):
            batch = texts[start : start + 10]
            try:
                response = requests.post(
                    f"{self.base_url}/embeddings",
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json={"model": self.model, "input": batch},
                    timeout=30,
                )
                response.raise_for_status()
                payload: dict[str, Any] = response.json()
            except requests.RequestException as error:
                raise EmbeddingError("EMBEDDING_API_ERROR", str(error)) from error
            except ValueError as error:
                raise EmbeddingError("EMBEDDING_API_ERROR", "Embedding response was not JSON") from error

            data = payload.get("data")
            if not isinstance(data, list):
                raise EmbeddingError("EMBEDDING_API_ERROR", "Embedding response missing data")
            data = sorted(data, key=lambda item: item.get("index", 0))
            for item in data:
                embedding = item.get("embedding")
                if not isinstance(embedding, list):
                    raise EmbeddingError("EMBEDDING_API_ERROR", "Embedding item missing vector")
                all_embeddings.append([float(value) for value in embedding])
        return all_embeddings

    def embed_query(self, text: str) -> list[float]:
        embeddings = self.embed_texts([text])
        if not embeddings:
            raise EmbeddingError("EMBEDDING_API_ERROR", "Embedding response was empty")
        return embeddings[0]
