import json
import os
from typing import Any

from backend_client import BackendClient
from schemas import NextDayWorkoutPlan

try:
    from langchain.agents import create_agent
    from langchain.agents.structured_output import ToolStrategy
    from langchain.tools import tool
    from langchain_openai import ChatOpenAI
except Exception:  # pragma: no cover
    create_agent = None
    ToolStrategy = None
    tool = None
    ChatOpenAI = None


def _coerce_plan_from_content(content: Any) -> dict[str, Any] | None:
    if not content:
        return None

    if isinstance(content, str):
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            return None
        return NextDayWorkoutPlan.model_validate(parsed).model_dump()

    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(item.get("text", ""))
        joined = "".join(text_parts).strip()
        if not joined:
            return None
        try:
            parsed = json.loads(joined)
        except json.JSONDecodeError:
            return None
        return NextDayWorkoutPlan.model_validate(parsed).model_dump()

    return None


def _build_tools(client: BackendClient, days: int):
    @tool
    def get_today_stats() -> dict:
        """Get today's workout, sleep, and diet summary for the current user."""
        return client.get("/api/stats/today")

    @tool
    def get_weekly_stats() -> list[dict]:
        """Get the current user's workout, sleep, and diet trend for the last 7 days."""
        return client.get("/api/stats/weekly")

    @tool
    def get_history_stats() -> list[dict]:
        """Get the current user's historical workout, sleep, and diet stats for recent days."""
        return client.get("/api/stats/history", params={"days": days})

    @tool
    def get_workout_goals() -> list[dict]:
        """Get the current user's workout-related goal settings."""
        return client.get("/api/goals")

    @tool
    def get_recent_workouts() -> list[dict]:
        """Get the current user's workout records."""
        return client.get("/api/workouts")

    return [
        get_today_stats,
        get_weekly_stats,
        get_history_stats,
        get_workout_goals,
        get_recent_workouts,
    ]


def _langchain_plan(request_data: dict[str, Any], authorization: str) -> dict[str, Any]:
    model_name = os.getenv("OPENAI_MODEL")
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")
    if not all([create_agent, ToolStrategy, tool, ChatOpenAI, model_name, api_key]):
        raise RuntimeError("LLM is not configured: create_agent, model, or API key is missing")

    days = int(request_data.get("days") or 7)
    client = BackendClient(authorization)
    tools = _build_tools(client, days)

    model = ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=0.3,
        extra_body={"enable_thinking": False},
    )

    agent = create_agent(
        model=model,
        tools=tools,
        response_format=ToolStrategy(NextDayWorkoutPlan),
        system_prompt=(
            "你是一名专业、克制、以安全为先的运动规划助手。"
            "你需要先使用可用工具获取用户今天的状态、近7天或最近若干天的趋势、运动目标和近期运动记录，"
            "再生成今日剩余时段可执行的训练计划。"
            "计划必须具体、可执行，强度要结合睡眠和已完成运动量，避免夸张承诺。"
            "输出必须严格符合结构化字段要求。"
        ),
    )

    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "请为我生成今日训练计划。"
                        f"额外偏好如下：{json.dumps(request_data, ensure_ascii=False)}。"
                        "请先调用必要工具读取数据，再返回最终计划。"
                    ),
                }
            ]
        }
    )

    structured = result.get("structured_response")
    if structured is None:
        messages = result.get("messages") or []
        if messages:
            parsed = _coerce_plan_from_content(getattr(messages[-1], "content", None))
            if parsed is not None:
                return parsed
        raise RuntimeError(f"Model returned no structured_response: {result}")
    if isinstance(structured, NextDayWorkoutPlan):
        return structured.model_dump()
    if hasattr(structured, "model_dump"):
        return structured.model_dump()
    if isinstance(structured, dict):
        return structured
    raise RuntimeError(f"Unsupported structured_response type: {type(structured).__name__}")


def build_today_workout_plan(request_data: dict[str, Any], authorization: str) -> dict[str, Any]:
    return _langchain_plan(request_data, authorization)
