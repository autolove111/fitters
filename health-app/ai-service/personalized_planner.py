from __future__ import annotations

from typing import Any

from backend_client import BackendClient
from fitness_rag import build_personalized_rag_documents, retrieve_fitness_guidance


def _avg(values: list[float]) -> float:
    return round(sum(values) / len(values), 1) if values else 0


def _profile_text(profile: dict[str, Any]) -> str:
    equipment = profile.get("equipment") or []
    return " ".join(
        str(value)
        for value in [
            profile.get("goal", ""),
            profile.get("fitnessLevel", ""),
            profile.get("injuries", ""),
            profile.get("preferredWorkoutTime", ""),
            " ".join(equipment) if isinstance(equipment, list) else equipment,
        ]
        if value
    )


def _risk_flags(profile: dict[str, Any], stats: dict[str, Any], history: list[dict[str, Any]]) -> list[str]:
    flags: list[str] = []
    injuries = str(profile.get("injuries") or "").strip()
    if injuries:
        flags.append(f"Reported limitation: {injuries}. Keep impact low and stop if pain increases.")

    sleep_hours = [float(item.get("sleepHours") or 0) for item in history if item.get("sleepHours")]
    avg_sleep = _avg(sleep_hours)
    if avg_sleep and avg_sleep < 7:
        flags.append(f"Recent average sleep is {avg_sleep}h, so intensity should stay moderate.")

    completed = int(stats.get("completedMinutes") or 0)
    if completed >= 60:
        flags.append("Today already has substantial training volume; prioritize recovery or mobility.")

    return flags


def _build_trend_analysis(history: list[dict[str, Any]], profile: dict[str, Any]) -> dict[str, Any]:
    recent = history[-30:] if len(history) > 30 else history
    if not recent:
        return {
            "coachSummary": "数据还不够，Pro 会在连续记录后给出更像私人教练的趋势判断。",
            "metrics": [],
            "chart": [],
            "windowDays": 0,
        }

    workout_values = [float(item.get("workoutMinutes") or 0) for item in recent]
    sleep_values = [float(item.get("sleepHours") or 0) for item in recent]
    diet_values = [float(item.get("dietCalories") or 0) for item in recent]
    avg_workout = _avg(workout_values)
    avg_sleep = _avg([value for value in sleep_values if value])
    avg_diet = _avg([value for value in diet_values if value])
    active_days = sum(1 for value in workout_values if value >= 20)
    sleep_good_days = sum(1 for value in sleep_values if value >= 7)
    diet_target_days = sum(1 for value in diet_values if 1700 <= value <= 2200)
    goal = profile.get("goal") or "general_fitness"

    chart = []
    for index, item in enumerate(recent):
        raw_date = str(item.get("date") or "")
        label = raw_date[5:] if len(raw_date) >= 10 else f"D{index + 1}"
        chart.append(
            {
                "label": label,
                "workoutMinutes": round(float(item.get("workoutMinutes") or 0), 1),
                "sleepHours": round(float(item.get("sleepHours") or 0), 1),
                "dietCalories": round(float(item.get("dietCalories") or 0), 1),
            }
        )

    if avg_sleep and avg_sleep < 7:
        coach_summary = "你的训练有连续性，但睡眠恢复偏弱。Pro 建议先稳住恢复，再逐步加训练量。"
    elif active_days >= max(3, len(recent) // 2):
        coach_summary = f"最近 {len(recent)} 天运动节奏不错，适合围绕{goal}做更细的周期安排。"
    else:
        coach_summary = "近期运动间隔偏散，Pro 会优先帮你建立稳定可坚持的训练节奏。"

    return {
        "coachSummary": coach_summary,
        "metrics": [
            {"label": "活跃训练日", "value": f"{active_days}/{len(recent)} 天", "tone": "good" if active_days >= 4 else "warn"},
            {"label": "平均运动", "value": f"{avg_workout} 分钟/天", "tone": "good" if avg_workout >= 25 else "warn"},
            {"label": "睡眠达标", "value": f"{sleep_good_days}/{len(recent)} 天", "tone": "good" if sleep_good_days >= 4 else "warn"},
            {"label": "饮食稳定", "value": f"{diet_target_days}/{len(recent)} 天", "tone": "good" if diet_target_days >= 4 else "warn"},
        ],
        "chart": chart,
        "windowDays": len(recent),
        "averages": {
            "workoutMinutes": avg_workout,
            "sleepHours": avg_sleep,
            "dietCalories": avg_diet,
        },
    }


def _customization_blocks(profile: dict[str, Any], history: list[dict[str, Any]], risk_flags: list[str]) -> list[dict[str, str]]:
    equipment = profile.get("equipment") or []
    equipment_text = ", ".join(equipment) if isinstance(equipment, list) and equipment else "徒手"
    goal = profile.get("goal") or "general_fitness"
    level = profile.get("fitnessLevel") or "beginner"
    avg_workout = _avg([float(item.get("workoutMinutes") or 0) for item in history])
    return [
        {
            "title": "按你的目标调训练重点",
            "text": f"本次计划围绕 {goal}，不是通用模板；主训练会优先匹配你的目标和当前训练水平。",
        },
        {
            "title": "按你的器械改动作",
            "text": f"动作会优先使用 {equipment_text}，避免给出你现场做不了的器械安排。",
        },
        {
            "title": "按你的历史控制强度",
            "text": f"最近平均运动 {avg_workout} 分钟/天，计划会按 {level} 节奏推进，避免突然加量。",
        },
        {
            "title": "按你的风险做避让",
            "text": "已结合你的伤痛/恢复记录做低冲击调整。" if risk_flags else "当前未记录明显伤痛，仍保留热身和恢复提醒。",
        },
    ]


def build_fallback_personalized_plan(
    request_data: dict[str, Any],
    stats: dict[str, Any],
    history: list[dict[str, Any]],
) -> dict[str, Any]:
    profile = request_data.get("profile") or {}
    membership_tier = (request_data.get("membership") or {}).get("tier") or "FREE"
    is_pro = membership_tier == "PRO"
    citation_limit = int(request_data.get("citationLimit") or (8 if membership_tier == "PRO" else 2))
    query = (
        f"{_profile_text(profile)} safe weekly aerobic strength plan"
        if is_pro
        else "general adult safe daily aerobic strength plan"
    )
    citations = retrieve_fitness_guidance(query, limit=citation_limit)
    risk_flags = _risk_flags(profile, stats, history) if is_pro else [
        "General safety: keep intensity comfortable and stop if pain increases."
    ]

    avg_workout = _avg([float(item.get("workoutMinutes") or 0) for item in history])
    avg_sleep = _avg([float(item.get("sleepHours") or 0) for item in history])
    avg_calories = _avg([float(item.get("dietCalories") or 0) for item in history])
    goal = (profile.get("goal") or "general_fitness") if is_pro else "general_fitness"
    level = (profile.get("fitnessLevel") or "beginner") if is_pro else "beginner"
    preferred_time = (profile.get("preferredWorkoutTime") or "evening") if is_pro else "today"
    equipment = profile.get("equipment") or []
    equipment_text = ", ".join(equipment) if is_pro and isinstance(equipment, list) and equipment else "bodyweight"

    base_minutes = 35 if membership_tier == "PRO" else 25
    if risk_flags:
        base_minutes = min(base_minutes, 30)

    items = [
        {
            "stage": "Warm-up",
            "activity": "Joint mobility and easy walk",
            "minutes": 6,
            "intensity": "low",
            "notes": "Prepare knees, hips, shoulders, and breathing before the main set.",
        },
        {
            "stage": "Main training",
            "activity": f"{equipment_text} circuit for {goal}",
            "minutes": max(12, base_minutes - 12),
            "intensity": "moderate" if not risk_flags else "low-to-moderate",
            "notes": f"Match the {level} level; keep reps smooth and leave 2-3 reps in reserve.",
        },
        {
            "stage": "Cool-down",
            "activity": "Stretching and breathing reset",
            "minutes": 6,
            "intensity": "low",
            "notes": "Reduce soreness and record perceived exertion after training.",
        },
    ]

    personal_insights = [
        f"Recent average workout: {avg_workout} min/day." if is_pro else "Free mode uses the shared fitness knowledge base for a general daily plan.",
        f"Recent average sleep: {avg_sleep} h/day." if is_pro and avg_sleep else "The plan stays conservative and suitable for broad users.",
    ]
    if membership_tier == "PRO":
        personal_insights.append(f"Recent average diet intake: {avg_calories} kcal/day.")
        personal_insights.append("Pro mode uses longer history and more RAG citations for explainability.")

    plan = {
        "title": "Personalized AI Fitness Plan",
        "membershipTier": membership_tier,
        "knowledgeBaseMode": "PERSONAL_RAG" if is_pro else "GENERAL_RAG",
        "knowledgeBaseLabel": "专属RAG知识库：通用资料 + 个人画像 + 30天记录" if is_pro else "通用RAG知识库：权威健身资料",
        "summary": f"Use a {base_minutes}-minute {preferred_time} session tailored to {goal}.",
        "personalInsights": personal_insights,
        "riskFlags": risk_flags,
        "basis": [
            "User fitness profile" if is_pro else "General adult fitness guidance",
            f"Recent {request_data.get('historyDays', 7)}-day health records" if is_pro else "Shared public guidance library",
            "RAG guidance from WHO, CDC, and ACSM",
        ],
        "citations": citations,
        "items": items,
        "tips": [
            "Keep pain below 3/10 and reduce range of motion if discomfort appears.",
            "Log completion and perceived exertion so tomorrow's plan can adapt.",
        ],
        "upgradeHint": ""
        if membership_tier == "PRO"
        else "Upgrade to Pro to unlock 30-day trend analysis and richer RAG citations.",
    }

    if is_pro and request_data.get("includeTrendAnalysis"):
        plan["personalKnowledge"] = build_personalized_rag_documents(profile, stats, history)
        plan["customizationBlocks"] = _customization_blocks(profile, history, risk_flags)
        plan["trendAnalysis"] = _build_trend_analysis(history, profile)

    return plan


def build_personalized_workout_plan(request_data: dict[str, Any], authorization: str) -> dict[str, Any]:
    client = BackendClient(authorization)
    history_days = int(request_data.get("historyDays") or 7)
    stats = client.get("/api/stats/today")
    history = client.get("/api/stats/history", params={"days": history_days})
    if not isinstance(history, list):
        history = []
    return build_fallback_personalized_plan(request_data, stats if isinstance(stats, dict) else {}, history)
