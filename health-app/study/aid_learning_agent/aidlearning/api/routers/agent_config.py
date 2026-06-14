#!/usr/bin/env python
"""
Agent 配置 API - 为数据驱动的 UI 提供 Agent 元数据。
"""

from fastapi import APIRouter

router = APIRouter()

# Agent 注册表 - Agent UI 元数据的唯一数据源
AGENT_REGISTRY = {
    "solve": {
        "icon": "HelpCircle",
        "color": "blue",
        "label_key": "Problem Solved",
    },
    "question": {
        "icon": "FileText",
        "color": "purple",
        "label_key": "Question Generated",
    },
    "research": {
        "icon": "Search",
        "color": "emerald",
        "label_key": "Research Report",
    },
}


@router.get("/agents")
async def get_agent_config():
    """
    获取 Agent UI 配置。

    Returns:
        Agent 类型到 UI 元数据（图标、颜色、标签键）的映射字典
    """
    return AGENT_REGISTRY


@router.get("/agents/{agent_type}")
async def get_single_agent_config(agent_type: str):
    """
    获取指定 Agent 的 UI 配置。

    Args:
        agent_type: Agent 类型（solve、question、research 等）

    Returns:
        Agent UI 元数据，未找到时返回 404
    """
    if agent_type in AGENT_REGISTRY:
        return AGENT_REGISTRY[agent_type]
    return {"error": f"Agent type '{agent_type}' not found"}
