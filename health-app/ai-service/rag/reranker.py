from __future__ import annotations

import re

GOAL_SYNONYMS = {
    "fat_loss": ["fat_loss", "weight_loss", "weight", "calorie", "calories", "fat", "management"],
    "weight_loss": ["fat_loss", "weight_loss", "weight", "calorie", "calories", "fat", "management"],
    "muscle_gain": ["muscle_gain", "strength", "resistance", "muscle", "hypertrophy"],
    "endurance": ["endurance", "aerobic", "cardio", "stamina"],
    "general_fitness": ["general", "fitness", "health", "activity"],
}

INJURY_SYNONYMS = {
    "knee_discomfort": ["knee", "joint", "low impact", "pain", "discomfort"],
    "knee": ["knee", "joint", "low impact", "pain", "discomfort"],
    "back_pain": ["back", "spine", "pain", "mobility"],
}


def _contains_any(text: str, values: list[str]) -> int:
    lowered = text.lower()
    return sum(1 for value in values if value and value.lower() in lowered)


def _personal_score(chunk, user_context: dict) -> float:
    text = " ".join([chunk.text, chunk.title, " ".join(chunk.topics)]).lower()
    score = 0
    goal = str(user_context.get("goal") or "")
    score += _contains_any(text, GOAL_SYNONYMS.get(goal, [goal]))
    injuries = str(user_context.get("injuries") or "")
    injury_keys = re.split(r"[,;\s]+", injuries)
    for injury in injury_keys:
        score += _contains_any(text, INJURY_SYNONYMS.get(injury, [injury])) * 2
    equipment = user_context.get("equipment") or []
    if isinstance(equipment, list):
        score += _contains_any(text, [str(item) for item in equipment])
    return min(1.0, score / 6)


def rerank_chunks(chunks: list, *, query: str, tier: str, user_context: dict, limit: int = 5) -> list:
    is_pro = tier.upper() == "PRO"
    for chunk in chunks:
        chunk.authority_score = min(1.0, max(0.0, float(chunk.authority_level or 3) / 5))
        chunk.personal_score = _personal_score(chunk, user_context) if is_pro else 0
        if is_pro:
            score = 0.65 * chunk.vector_score + 0.15 * chunk.keyword_score + 0.10 * chunk.authority_score + 0.10 * chunk.personal_score
        else:
            score = 0.75 * chunk.vector_score + 0.15 * chunk.keyword_score + 0.10 * chunk.authority_score
        chunk.rerank_score = min(1.0, max(0.0, score))
    return sorted(chunks, key=lambda item: item.rerank_score, reverse=True)[:limit]
