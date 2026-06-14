from personalized_planner import build_fallback_personalized_plan


def test_free_personalized_plan_contains_upgrade_hint_and_limited_citations():
    plan = build_fallback_personalized_plan(
        {
            "membership": {"tier": "FREE"},
            "citationLimit": 2,
            "profile": {
                "goal": "fat_loss",
                "fitnessLevel": "beginner",
                "injuries": "knee discomfort",
                "equipment": ["yoga mat"],
                "preferredWorkoutTime": "evening",
            },
            "historyDays": 7,
        },
        stats={"completedMinutes": 10, "avgSleepQuality": 60, "steps": 3500},
        history=[{"workoutMinutes": 10, "sleepHours": 6.2, "dietCalories": 2200}],
    )

    assert plan["membershipTier"] == "FREE"
    assert plan["knowledgeBaseMode"] == "GENERAL_RAG"
    assert len(plan["citations"]) <= 2
    assert plan["upgradeHint"]
    assert "personalKnowledge" not in plan
    assert "customizationBlocks" not in plan
    assert "bodyweight" in plan["items"][1]["activity"]


def test_pro_personalized_plan_has_deeper_explanation_and_no_upgrade_hint():
    history = [
        {
            "date": f"2026-05-{16 + index:02d}" if index < 16 else f"2026-06-{index - 15:02d}",
            "workoutMinutes": 20 + (index % 5) * 8,
            "sleepHours": 6.4 + (index % 4) * 0.4,
            "dietCalories": 1850 + (index % 6) * 70,
        }
        for index in range(30)
    ]

    plan = build_fallback_personalized_plan(
        {
            "membership": {"tier": "PRO"},
            "citationLimit": 8,
            "includeTrendAnalysis": True,
            "profile": {
                "goal": "muscle_gain",
                "fitnessLevel": "intermediate",
                "injuries": "",
                "equipment": ["dumbbell"],
                "preferredWorkoutTime": "morning",
            },
            "historyDays": 30,
        },
        stats={"completedMinutes": 35, "avgSleepQuality": 82, "steps": 8200},
        history=history,
    )

    assert plan["membershipTier"] == "PRO"
    assert plan["knowledgeBaseMode"] == "PERSONAL_RAG"
    assert plan["upgradeHint"] == ""
    assert plan["personalInsights"]
    assert plan["personalKnowledge"]
    assert plan["customizationBlocks"]
    assert any(item["source"] == "个人画像RAG" for item in plan["personalKnowledge"])
    assert "dumbbell" in plan["items"][1]["activity"]
    assert len(plan["citations"]) >= 5
    assert plan["trendAnalysis"]["chart"]
    assert plan["trendAnalysis"]["windowDays"] == 30
    assert len(plan["trendAnalysis"]["chart"]) == 30
    assert plan["trendAnalysis"]["coachSummary"]
