"""测验历史加载器 —— 在同一会话中展示先前的测验项目。

供 :class:`QuestionPipeline` 使用，以便 Explore 阶段可以说明哪些主题
已被测试过、学习者答错了哪些，以及下一轮应如何避免重复 / 可选地针对薄弱环节。

单个公共入口：

* :func:`load_session_quiz_history` —— 异步，接受 ``session_id`` 和上限，
  返回按时间顺序排列的 :class:`~aidlearning.agents.question.pipeline.QuizHistoryEntry` 列表。

数据源：``notebook_entries`` 表（由 ``POST /sessions/{id}/quiz-results`` 填充）。
*不*查询消息 —— 消息是自由文本，需要脆弱的解析。

失败时关闭：任何错误返回空列表（因此管线简单地将该会话视为未询问过测验）。
"""

from __future__ import annotations

import logging
from typing import Any

from aidlearning.agents.question.pipeline import QuizHistoryEntry

logger = logging.getLogger(__name__)

DEFAULT_MAX_ENTRIES = 30


async def load_session_quiz_history(
    session_id: str,
    *,
    max_entries: int = DEFAULT_MAX_ENTRIES,
) -> list[QuizHistoryEntry]:
    """按时间顺序返回 ``session_id`` 的先前测验项目。

    "时间顺序"意味着返回列表中最旧的在前，即使底层表按 DESC 排序以进行分页
    —— 顺序对 LLM 提示词很重要（它从上到下读取为"这是我们目前涵盖的内容"）。

    笔记本条目上的布尔 ``is_correct`` 字段默认为 0，即使未提交答案也是如此；
    我们将空 ``user_answer`` 视为"未回答"并为其显示 ``is_correct=None``，
    以便探索提示词可以渲染"未知"而不是误导性的"错误"。
    """
    if not session_id or max_entries <= 0:
        return []
    try:
        from aidlearning.services.session.sqlite_store import get_sqlite_session_store

        store = get_sqlite_session_store()
        result = await store.list_notebook_entries(
            session_id=session_id,
            limit=max(1, int(max_entries)),
            offset=0,
        )
    except Exception:
        logger.warning("Failed to load quiz history for session %s", session_id, exc_info=True)
        return []

    items: list[dict[str, Any]] = list(result.get("items") or [])
    # 存储返回 DESC，但具有相同 ``created_at`` 的行（单次 upsert 调用
    # 以相同时间戳写入所有行）按插入顺序返回 —— 因此简单的 reverse()
    # 仍会翻转它们。显式按 (created_at ASC, id ASC) 排序，以便提示词
    # 确定性地从最早读到最新。
    items.sort(key=lambda r: (float(r.get("created_at") or 0.0), int(r.get("id") or 0)))

    entries: list[QuizHistoryEntry] = []
    for raw in items:
        if not isinstance(raw, dict):
            continue
        question = str(raw.get("question") or "").strip()
        if not question:
            continue
        user_answer = str(raw.get("user_answer") or "").strip()
        correct_answer = str(raw.get("correct_answer") or "").strip()
        # 数据库列是默认值为 0 的 0/1 INTEGER —— 我们无法仅从 is_correct
        # 区分"答错"和"尚未回答"。user_answer 字段是"是否尝试过"的权威来源。
        if not user_answer:
            is_correct: bool | None = None
        else:
            is_correct = bool(raw.get("is_correct"))
        entries.append(
            QuizHistoryEntry(
                question=question,
                question_type=str(raw.get("question_type") or "").strip(),
                correct_answer=correct_answer,
                user_answer=user_answer,
                is_correct=is_correct,
                turn_id=str(raw.get("turn_id") or "").strip(),
            )
        )
    return entries


__all__ = ["DEFAULT_MAX_ENTRIES", "load_session_quiz_history"]
