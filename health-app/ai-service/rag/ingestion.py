from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from .sources import RAGSource, markdown_to_plain_text


@dataclass(frozen=True)
class RAGChunk:
    chunk_id: str
    source: str
    title: str
    url: str
    authority_level: int
    topics: list[str]
    chunk_index: int
    text: str
    estimated_tokens: int
    content_hash: str
    source_path: str
    source_doc_hash: str


def clean_markdown_text(text: str) -> str:
    return markdown_to_plain_text(text)


def estimate_tokens(text: str) -> int:
    word_like = re.findall(r"[A-Za-z0-9]+(?:[-+/][A-Za-z0-9]+)*|[\u4e00-\u9fff]", text)
    return max(1, len(word_like))


def _sentences(text: str) -> list[str]:
    pieces = re.split(r"(?<=[.!?。！？])\s+", text)
    return [piece.strip() for piece in pieces if piece.strip()]


def _chunk_id(source: RAGSource, text: str, index: int) -> tuple[str, str]:
    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    source_slug = re.sub(r"[^a-z0-9]+", "_", source.source.lower()).strip("_") or "source"
    return f"{source_slug}_{index}_{content_hash[:8]}", content_hash


def build_chunks(
    sources: list[RAGSource],
    *,
    chunk_size: int = 256,
    chunk_overlap: int = 48,
) -> list[RAGChunk]:
    chunks: list[RAGChunk] = []
    for source in sources:
        sentences = _sentences(clean_markdown_text(source.text))
        current: list[str] = []
        current_tokens = 0
        source_chunks: list[str] = []
        for sentence in sentences:
            sentence_tokens = estimate_tokens(sentence)
            if current and current_tokens + sentence_tokens > chunk_size:
                source_chunks.append(" ".join(current).strip())
                overlap: list[str] = []
                overlap_tokens = 0
                for previous in reversed(current):
                    previous_tokens = estimate_tokens(previous)
                    if overlap_tokens + previous_tokens > chunk_overlap:
                        break
                    overlap.insert(0, previous)
                    overlap_tokens += previous_tokens
                current = overlap[:]
                current_tokens = overlap_tokens
            current.append(sentence)
            current_tokens += sentence_tokens
        if current:
            source_chunks.append(" ".join(current).strip())

        for index, text in enumerate(source_chunks):
            chunk_id, content_hash = _chunk_id(source, text, index)
            chunks.append(
                RAGChunk(
                    chunk_id=chunk_id,
                    source=source.source,
                    title=source.title,
                    url=source.url,
                    authority_level=source.authority_level,
                    topics=source.topics,
                    chunk_index=index,
                    text=text,
                    estimated_tokens=estimate_tokens(text),
                    content_hash=content_hash,
                    source_path=source.source_path,
                    source_doc_hash=source.source_doc_hash,
                )
            )
    return chunks


def ingest_sources(sources, store, embedder) -> int:
    total = 0
    for source in sources:
        existing_hash = store.get_document_hash(source.source_path)
        if existing_hash == source.source_doc_hash:
            continue
        chunks = build_chunks([source])
        embeddings = embedder.embed_texts([chunk.text for chunk in chunks])
        store.replace_document_chunks(source.source_path, source.source_doc_hash, chunks, embeddings)
        total += len(chunks)
    return total
