#!/usr/bin/env python
"""
AidLearning 的常量定义。
"""

from pathlib import Path

# 项目根目录 - 所有路径计算的中心位置
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# 调查智能体的合法工具列表
VALID_INVESTIGATE_TOOLS = ["rag", "web_search", "none"]

# 解题智能体的合法工具列表
VALID_SOLVE_TOOLS = [
    "web_search",
    "code_execution",
    "rag",
    "none",
    "finish",
]

# 标准库日志级别标签。
LOG_LEVEL_TAGS = [
    "DEBUG",
    "INFO",
    "WARNING",
    "ERROR",
    "CRITICAL",
]
