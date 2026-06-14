from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from .embedding_client import DashScopeEmbeddingClient
from .generator import generate_plan
from .ingestion import ingest_sources
from .reranker import rerank_chunks
from .retriever import retrieve_chunks
from .sources import load_sources
from .vector_store import SQLiteVectorStore

PIPELINE_NAME = "EMBEDDING_VECTOR_RAG"
PROVIDER_NAME = "dashscope-compatible"


def default_sources_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "rag_sources"


def default_store_path() -> Path:
    return Path(os.getenv("RAG_STORE_PATH") or Path(__file__).resolve().parent.parent / "data" / "fitness_rag.sqlite")


def build_user_context(
    request_data: dict[str, Any],
    stats: dict[str, Any],
    history: list[dict[str, Any]],
) -> dict[str, Any]:
    profile = request_data.get("profile") or {}
    history_window = history[-30:] if len(history) > 30 else history
    workout_values = [float(item.get("workoutMinutes") or 0) for item in history_window]
    sleep_values = [float(item.get("sleepHours") or 0) for item in history_window if item.get("sleepHours")]
    avg_workout = round(sum(workout_values) / len(workout_values), 1) if workout_values else 0
    avg_sleep = round(sum(sleep_values) / len(sleep_values), 1) if sleep_values else 0
    return {
        "goal": profile.get("goal") or "general_fitness",
        "fitnessLevel": profile.get("fitnessLevel") or "beginner",
        "injuries": profile.get("injuries") or "",
        "equipment": profile.get("equipment") or [],
        "preferredWorkoutTime": profile.get("preferredWorkoutTime") or "today",
        "availableMinutes": request_data.get("availableMinutes") or (35 if (request_data.get("membership") or {}).get("tier") == "PRO" else 25),
        "historyDays": len(history_window),
        "todayCompletedMinutes": stats.get("completedMinutes") or 0,
        "todaySteps": stats.get("steps") or 0,
        "historySummary": f"Average workout {avg_workout} min/day; average sleep {avg_sleep} h/day across {len(history_window)} days.",
    }


def build_query(user_context: dict[str, Any], tier: str) -> str:
    if tier == "PRO":
        equipment = user_context.get("equipment") or []
        equipment_text = " ".join(equipment) if isinstance(equipment, list) else str(equipment)
        return " ".join(
            str(value)
            for value in [
                user_context.get("goal"),
                user_context.get("fitnessLevel"),
                user_context.get("injuries"),
                equipment_text,
                "safe personalized workout plan low impact strength aerobic recovery",
            ]
            if value
        )
    return "general adult safe daily aerobic strength workout plan"


def ensure_index(store: SQLiteVectorStore, embedder: DashScopeEmbeddingClient, sources_dir: Path | None = None) -> None:
    sources = load_sources(sources_dir or default_sources_dir())
    if not sources:
        return
    ingest_sources(sources, store, embedder)


def build_citations(chunks: list[Any], limit: int) -> list[dict[str, Any]]:
    citations: list[dict[str, Any]] = []
    for chunk in chunks[:limit]:
        citations.append(
            {
                "chunkId": chunk.chunk_id,
                "source": chunk.source,
                "title": chunk.title,
                "url": chunk.url,
                "authorityLevel": chunk.authority_level,
                "relevanceScore": round(chunk.rerank_score or chunk.vector_score or 0, 4),
                "vectorScore": round(chunk.vector_score, 4),
                "keywordScore": round(chunk.keyword_score, 4),
                "rerankScore": round(chunk.rerank_score, 4),
                "excerptChunk": chunk.text[:260],
            }
        )
    return citations


def run_personalized_rag_plan(
    request_data: dict[str, Any],
    stats: dict[str, Any],
    history: list[dict[str, Any]],
    *,
    store_path: str | Path | None = None,
    sources_dir: str | Path | None = None,
) -> dict[str, Any]:
    start = time.time()
    tier = ((request_data.get("membership") or {}).get("tier") or "FREE").upper()
    is_pro = tier == "PRO"
    user_context = build_user_context(request_data, stats, history)
    embedder = DashScopeEmbeddingClient()
    store = SQLiteVectorStore(store_path or default_store_path(), embedding_model=embedder.model, embedding_dim=embedder.dim)

    ensure_index(store, embedder, Path(sources_dir) if sources_dir else None)
    query = build_query(user_context, tier)
    retrieved = retrieve_chunks(
        query,
        store,
        embedder,
        vector_limit=8 if is_pro else 4,
        keyword_limit=12 if is_pro else 6,
    )
    if not retrieved:
        from .retriever import RetrievalError

        raise RetrievalError("NO_CHUNKS_FOUND", "RAG index did not return chunks")

    reranked = rerank_chunks(
        retrieved,
        query=query,
        tier=tier,
        user_context=user_context,
        limit=6 if is_pro else 3,
    )
    plan = generate_plan(
        [chunk.to_citation_dict(include_text=True) for chunk in reranked],
        user_context=user_context,
        tier=tier,
    )
    citations = build_citations(reranked, 8 if is_pro else 3)
    plan["citations"] = citations
    plan["ragMetadata"] = {
        "generationMode": "LLM",
        "ragPipeline": PIPELINE_NAME,
        "llmProvider": PROVIDER_NAME,
        "llmModel": os.getenv("OPENAI_MODEL") or "qwen3-14b",
        "embeddingModel": embedder.model,
        "embeddingDim": embedder.dim,
        "retrievedChunks": len(retrieved),
        "rerankedChunks": len(reranked),
        "fallbackReason": None,
        "latencyMs": int((time.time() - start) * 1000),
        "citations": citations,
    }
    return plan
