import json
import os
from typing import Any

from backend_client import BackendClient
from schemas import NextDayWorkoutPlan

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


def _fetch_user_data(client: BackendClient, days: int = 7) -> dict:
    """获取用户数据用于生成训练计划"""
    data = {}
    try:
        data["today"] = client.get("/api/stats/today")
    except Exception:
        data["today"] = {}
    try:
        data["weekly"] = client.get("/api/stats/weekly")
    except Exception:
        data["weekly"] = []
    try:
        data["goals"] = client.get("/api/goals")
    except Exception:
        data["goals"] = []
    try:
        data["workouts"] = client.get("/api/workouts")
    except Exception:
        data["workouts"] = []
    return data


def _generate_plan_with_openai(user_data: dict, request_data: dict) -> dict:
    """使用 OpenAI 兼容 API 生成训练计划"""
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")
    model_name = os.getenv("OPENAI_MODEL", "qwen3-14b")

    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    client = OpenAI(api_key=api_key, base_url=base_url)

    system_prompt = """你是一名专业的运动规划助手。请根据用户数据生成训练计划。

你必须严格按照以下JSON格式输出，不要输出任何其他内容：

{
  "personal_analysis": {
    "body_status": "身体状态评估",
    "recent_training_load": "近期训练负荷分析",
    "sleep_quality": "睡眠质量评估",
    "recovery_status": "恢复状态评估",
    "summary": "综合分析结论"
  },
  "guidance": {
    "warmup": [
      {"name": "动作名称", "sets": 1, "reps": "30秒", "rest_seconds": 15, "notes": "注意事项"}
    ],
    "main_workout": [
      {"name": "动作名称", "sets": 3, "reps": "12次", "rest_seconds": 60, "notes": "动作要领"}
    ],
    "cooldown": [
      {"name": "动作名称", "sets": 1, "reps": "30秒", "rest_seconds": 0, "notes": "拉伸要点"}
    ],
    "tips": ["建议1", "建议2", "建议3"]
  }
}

要求：
1. 热身至少2-3个动作
2. 主要训练至少4-6个动作
3. 拉伸至少2-3个动作
4. 额外建议至少3条
5. 结合用户的睡眠、已完成运动量调整强度
6. 每个动作的reps要写清楚，如"12次"或"30秒"
"""

    user_prompt = f"""用户数据：
- 今日数据：{json.dumps(user_data.get('today', {}), ensure_ascii=False)}
- 本周趋势：{json.dumps(user_data.get('weekly', []), ensure_ascii=False)}
- 运动目标：{json.dumps(user_data.get('goals', []), ensure_ascii=False)}

请生成今日训练计划。"""

    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.3,
        max_tokens=2000,
        response_format={"type": "json_object"},
        extra_body={"enable_thinking": False}  # 阿里云 qwen3 模型要求
    )

    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("模型返回空内容")

    # 解析 JSON
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"模型返回的JSON格式错误: {e}")

    # 验证并返回
    plan = NextDayWorkoutPlan.model_validate(parsed)
    return plan.model_dump()


def build_today_workout_plan(request_data: dict[str, Any], authorization: str) -> dict[str, Any]:
    client = BackendClient(authorization)
    days = int(request_data.get("days") or 7)

    # 获取用户数据
    user_data = _fetch_user_data(client, days)

    # 生成训练计划
    return _generate_plan_with_openai(user_data, request_data)
