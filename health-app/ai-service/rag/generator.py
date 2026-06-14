from __future__ import annotations

import json
import os
import re
from typing import Any

import requests
from pydantic import BaseModel, Field, ValidationError


class GeneratorError(Exception):
    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


class PlanItem(BaseModel):
    stage: str
    activity: str
    minutes: int = Field(ge=1, le=180)
    intensity: str
    notes: str = ""


class PlanCitation(BaseModel):
    chunkId: str
    source: str
    title: str
    url: str


class WorkoutPlanResult(BaseModel):
    title: str
    summary: str
    items: list[PlanItem]
    personalizationRationale: str = ""
    riskFlags: list[str] = Field(default_factory=list)
    citations: list[PlanCitation] = Field(default_factory=list)


def _extract_json(content: str) -> dict[str, Any]:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, flags=re.S)
    if match:
        return json.loads(match.group(1))
    start = content.find("{")
    end = content.rfind("}")
    if start >= 0 and end > start:
        return json.loads(content[start : end + 1])
    raise json.JSONDecodeError("No JSON object found", content, 0)


def _prompt(reranked_chunks: list[dict[str, Any]], user_context: dict[str, Any], tier: str) -> str:
    guidelines = []
    for index, chunk in enumerate(reranked_chunks, start=1):
        guidelines.append(
            f"[{index}] chunkId={chunk.get('chunkId')} source={chunk.get('source')} title={chunk.get('title')}\n"
            f"{chunk.get('text') or chunk.get('excerptChunk')}"
        )
    return f"""
You are a certified fitness coach. Generate a safe workout plan using only the authoritative guideline chunks.

Authoritative Guidelines:
{chr(10).join(guidelines)}

User Context:
{json.dumps(user_context, ensure_ascii=False)}

Tier: {tier}

Rules:
1. Use warm-up, main training, and cool-down stages.
2. Every recommendation must be grounded in at least one supplied chunk.
3. If injuries or pain are present, prioritize low-impact alternatives and include a safety warning.
4. Return valid JSON only with this exact shape:
{{
  "title": "string",
  "summary": "string",
  "items": [{{"stage": "Warm-up | Main training | Cool-down", "activity": "string", "minutes": 1, "intensity": "low | low-to-moderate | moderate | high", "notes": "string"}}],
  "personalizationRationale": "string",
  "riskFlags": ["string"],
  "citations": [{{"chunkId": "one provided chunkId", "source": "string", "title": "string", "url": "string"}}]
}}
"""


def _repair_citations(plan: dict[str, Any], reranked_chunks: list[dict[str, Any]]) -> dict[str, Any]:
    allowed = {chunk.get("chunkId"): chunk for chunk in reranked_chunks}
    fallback = reranked_chunks[0] if reranked_chunks else {}
    repaired = []
    for citation in plan.get("citations") or []:
        chunk_id = citation.get("chunkId")
        chunk = allowed.get(chunk_id) or fallback
        if not chunk:
            continue
        repaired.append(
            {
                "chunkId": chunk.get("chunkId"),
                "source": chunk.get("source") or citation.get("source") or "",
                "title": chunk.get("title") or citation.get("title") or "",
                "url": chunk.get("url") or citation.get("url") or "",
            }
        )
    if not repaired and fallback:
        repaired.append(
            {
                "chunkId": fallback.get("chunkId"),
                "source": fallback.get("source") or "",
                "title": fallback.get("title") or "",
                "url": fallback.get("url") or "",
            }
        )
    plan["citations"] = repaired
    return plan


def generate_plan(reranked_chunks: list[dict[str, Any]], user_context: dict[str, Any], tier: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = config or {}
    api_key = config.get("api_key") or os.getenv("OPENAI_API_KEY", "")
    base_url = (config.get("base_url") or os.getenv("OPENAI_BASE_URL") or "https://dashscope.aliyuncs.com/compatible-mode/v1").rstrip("/")
    model = config.get("model") or os.getenv("OPENAI_MODEL") or "qwen3-14b"
    timeout_seconds = int(config.get("timeout") or os.getenv("LLM_TIMEOUT_SECONDS") or 90)
    if not api_key:
        raise GeneratorError("LLM_API_ERROR", "OPENAI_API_KEY is required for chat completions")
    try:
        response = requests.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "You return strict JSON for a fitness planning API."},
                    {"role": "user", "content": _prompt(reranked_chunks, user_context, tier)},
                ],
                "temperature": 0.4,
                "enable_thinking": False,
            },
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
    except requests.Timeout as error:
        raise GeneratorError("LLM_TIMEOUT", str(error)) from error
    except (requests.RequestException, KeyError, IndexError, TypeError, ValueError) as error:
        raise GeneratorError("LLM_API_ERROR", str(error)) from error

    try:
        parsed = _extract_json(content)
        parsed = _repair_citations(parsed, reranked_chunks)
        return WorkoutPlanResult.model_validate(parsed).model_dump()
    except (json.JSONDecodeError, ValidationError) as error:
        raise GeneratorError("LLM_PARSE_ERROR", str(error)) from error
