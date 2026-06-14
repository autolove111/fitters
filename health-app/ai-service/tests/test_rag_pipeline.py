import json

import pytest


def test_load_sources_parses_markdown_frontmatter_and_plain_text(tmp_path):
    from rag.sources import load_sources

    source_file = tmp_path / "who_activity.md"
    source_file.write_text(
        """---
source: WHO
title: Adult physical activity
url: https://example.com/who
authority_level: 5
topics:
  - aerobic
  - strength
language: en
---

# Adult activity

Adults should do **150-300 minutes** of moderate activity.
""",
        encoding="utf-8",
    )

    sources = load_sources(tmp_path)

    assert len(sources) == 1
    assert sources[0].source == "WHO"
    assert sources[0].authority_level == 5
    assert sources[0].topics == ["aerobic", "strength"]
    assert "150-300 minutes" in sources[0].text
    assert "**" not in sources[0].text


def test_ingestion_splits_clean_text_and_keeps_units():
    from rag.ingestion import build_chunks, clean_markdown_text
    from rag.sources import RAGSource

    cleaned = clean_markdown_text("Adults need **150-300 minutes/week**. Keep 2+ strength days.")
    assert "150-300 minutes/week" in cleaned
    assert "2+ strength days" in cleaned
    assert "**" not in cleaned

    source = RAGSource(
        source="CDC",
        title="Adult activity",
        url="https://example.com/cdc",
        authority_level=5,
        topics=["aerobic", "strength"],
        language="en",
        source_path="cdc.md",
        source_doc_hash="abc",
        text=("Adults need aerobic activity plus strength work. " * 18).strip(),
    )

    chunks = build_chunks([source], chunk_size=24, chunk_overlap=6)

    assert len(chunks) > 1
    assert all(chunk.text for chunk in chunks)
    assert all(chunk.estimated_tokens > 0 for chunk in chunks)
    assert all(chunk.source_doc_hash == "abc" for chunk in chunks)


def test_vector_store_persists_chunks_and_searches_by_cosine(tmp_path):
    from rag.ingestion import RAGChunk
    from rag.vector_store import SQLiteVectorStore

    store = SQLiteVectorStore(tmp_path / "rag.sqlite")
    chunks = [
        RAGChunk(
            chunk_id="a",
            source="WHO",
            title="Aerobic",
            url="https://example.com/a",
            authority_level=5,
            topics=["aerobic"],
            chunk_index=0,
            text="moderate aerobic activity",
            estimated_tokens=4,
            content_hash="hash-a",
            source_path="a.md",
            source_doc_hash="doc-a",
        ),
        RAGChunk(
            chunk_id="b",
            source="NSCA",
            title="Strength",
            url="https://example.com/b",
            authority_level=4,
            topics=["strength"],
            chunk_index=0,
            text="resistance strength training",
            estimated_tokens=4,
            content_hash="hash-b",
            source_path="b.md",
            source_doc_hash="doc-b",
        ),
    ]
    store.replace_document_chunks("a.md", "doc-a", [chunks[0]], [[1.0, 0.0]])
    store.replace_document_chunks("b.md", "doc-b", [chunks[1]], [[0.0, 1.0]])

    results = store.search([0.9, 0.1], limit=2)

    assert [item.chunk_id for item in results] == ["a", "b"]
    assert results[0].vector_score > results[1].vector_score
    assert results[0].embedding_model


def test_retriever_and_reranker_make_pro_more_personal(tmp_path):
    from rag.ingestion import RAGChunk
    from rag.reranker import rerank_chunks
    from rag.retriever import retrieve_chunks
    from rag.vector_store import SQLiteVectorStore

    class FakeEmbedder:
        model = "fake-embedding"
        dim = 3

        def embed_query(self, _text):
            return [1.0, 0.0, 0.0]

    store = SQLiteVectorStore(tmp_path / "rag.sqlite")
    knee_chunk = RAGChunk(
        chunk_id="knee",
        source="ACSM",
        title="Exercise screening",
        url="https://example.com/knee",
        authority_level=5,
        topics=["injury", "knee", "safety"],
        chunk_index=0,
        text="knee discomfort needs low impact exercise and safety screening",
        estimated_tokens=9,
        content_hash="knee-hash",
        source_path="knee.md",
        source_doc_hash="knee-doc",
    )
    generic_chunk = RAGChunk(
        chunk_id="generic",
        source="WHO",
        title="Adult activity",
        url="https://example.com/generic",
        authority_level=5,
        topics=["aerobic"],
        chunk_index=0,
        text="adults should do moderate aerobic activity every week",
        estimated_tokens=8,
        content_hash="generic-hash",
        source_path="generic.md",
        source_doc_hash="generic-doc",
    )
    store.replace_document_chunks("knee.md", "knee-doc", [knee_chunk], [[0.7, 0.3, 0.0]])
    store.replace_document_chunks("generic.md", "generic-doc", [generic_chunk], [[1.0, 0.0, 0.0]])

    retrieved = retrieve_chunks(
        "knee discomfort fat loss low impact",
        store,
        FakeEmbedder(),
        vector_limit=2,
        keyword_limit=2,
    )
    pro = rerank_chunks(
        retrieved,
        query="knee discomfort fat loss",
        tier="PRO",
        user_context={"goal": "fat_loss", "injuries": "knee_discomfort", "equipment": ["yoga mat"]},
        limit=2,
    )

    assert {item.chunk_id for item in retrieved} == {"knee", "generic"}
    assert pro[0].chunk_id == "knee"
    assert pro[0].personal_score > 0
    assert pro[0].rerank_score <= 1


def test_generator_parses_markdown_json_and_replaces_fake_chunk_id(monkeypatch):
    from rag.generator import generate_plan

    captured_body = {}
    captured_timeout = {}
    reranked_chunks = [
        {
            "chunkId": "real-chunk",
            "source": "WHO",
            "title": "Adult activity",
            "url": "https://example.com/who",
            "text": "Adults need aerobic and strength activity.",
            "authorityLevel": 5,
            "rerankScore": 0.91,
        }
    ]

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": "```json\n"
                            + json.dumps(
                                {
                                    "title": "Plan",
                                    "summary": "Safe daily plan.",
                                    "items": [
                                        {
                                            "stage": "Warm-up",
                                            "activity": "Easy walk",
                                            "minutes": 5,
                                            "intensity": "low",
                                            "notes": "Start easy.",
                                        }
                                    ],
                                    "personalizationRationale": "Uses the cited guidance.",
                                    "riskFlags": ["Stop if pain increases."],
                                    "citations": [
                                        {
                                            "chunkId": "made-up",
                                            "source": "WHO",
                                            "title": "Adult activity",
                                            "url": "https://example.com/who",
                                        }
                                    ],
                                }
                            )
                            + "\n```"
                        }
                    }
                ]
            }

    def fake_post(*_args, **kwargs):
        captured_body.update(kwargs.get("json") or {})
        captured_timeout["value"] = kwargs.get("timeout")
        return FakeResponse()

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    monkeypatch.setenv("OPENAI_MODEL", "qwen3-14b")
    monkeypatch.setattr("rag.generator.requests.post", fake_post)

    plan = generate_plan(
        reranked_chunks=reranked_chunks,
        user_context={"goal": "fat_loss", "historySummary": "active 3 days"},
        tier="PRO",
    )

    assert plan["title"] == "Plan"
    assert plan["citations"][0]["chunkId"] == "real-chunk"
    assert plan["personalizationRationale"]
    assert captured_body["enable_thinking"] is False
    assert captured_body["model"] == "qwen3-14b"
    assert captured_timeout["value"] == 90


def test_personalized_planner_adds_rag_metadata_when_llm_succeeds(monkeypatch):
    import personalized_planner

    def fake_run_personalized_rag_plan(*_args, **_kwargs):
        return {
            "title": "LLM plan",
            "summary": "Generated from RAG.",
            "items": [
                {
                    "stage": "Warm-up",
                    "activity": "Easy walk",
                    "minutes": 5,
                    "intensity": "low",
                    "notes": "Start easy.",
                }
            ],
            "riskFlags": [],
            "citations": [
                {
                    "chunkId": "who-1",
                    "source": "WHO",
                    "title": "Adult activity",
                    "url": "https://example.com/who",
                    "authorityLevel": 5,
                    "relevanceScore": 0.9,
                    "vectorScore": 0.8,
                    "keywordScore": 0.4,
                    "rerankScore": 0.9,
                    "excerptChunk": "Adults need activity.",
                }
            ],
            "ragMetadata": {
                "generationMode": "LLM",
                "ragPipeline": "EMBEDDING_VECTOR_RAG",
                "llmProvider": "dashscope-compatible",
                "llmModel": "qwen3-14b",
                "embeddingModel": "text-embedding-v4",
                "embeddingDim": 1024,
                "retrievedChunks": 8,
                "rerankedChunks": 6,
                "fallbackReason": None,
                "latencyMs": 123,
                "citations": [],
            },
        }

    monkeypatch.setattr(personalized_planner, "run_personalized_rag_plan", fake_run_personalized_rag_plan)

    plan = personalized_planner.build_rag_personalized_plan(
        {
            "membership": {"tier": "PRO"},
            "profile": {"goal": "fat_loss"},
            "historyDays": 30,
        },
        stats={"completedMinutes": 20},
        history=[{"workoutMinutes": 30, "sleepHours": 7.5}],
    )

    assert plan["membershipTier"] == "PRO"
    assert plan["knowledgeBaseMode"] == "PERSONAL_RAG"
    assert plan["ragMetadata"]["generationMode"] == "LLM"
    assert plan["citations"][0]["chunkId"] == "who-1"


def test_personalized_planner_falls_back_with_reason(monkeypatch):
    import personalized_planner
    from rag.embedding_client import EmbeddingError

    def fake_run_personalized_rag_plan(*_args, **_kwargs):
        raise EmbeddingError("EMBEDDING_API_ERROR", "missing api key")

    monkeypatch.setattr(personalized_planner, "run_personalized_rag_plan", fake_run_personalized_rag_plan)

    plan = personalized_planner.build_rag_personalized_plan(
        {"membership": {"tier": "FREE"}, "profile": {}, "historyDays": 7},
        stats={},
        history=[],
    )

    assert plan["ragMetadata"]["generationMode"] == "FALLBACK"
    assert plan["ragMetadata"]["fallbackReason"] == "EMBEDDING_API_ERROR"
    assert plan["items"]
