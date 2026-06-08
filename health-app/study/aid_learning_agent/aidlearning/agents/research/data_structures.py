#!/usr/bin/env python
"""
DR-in-KG 2.0 核心数据结构
包含：TopicBlock、ToolTrace、DynamicTopicQueue
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime
import difflib
from enum import Enum
import json
from pathlib import Path
import re
from typing import Any

from aidlearning.utils.json_parser import parse_json_response

# :meth:`DynamicTopicQueue.find_similar` 使用的默认模糊匹配阈值。
# 0.85 可可靠地捕获近乎重复的标题（大小写/标点/单词重排），
# 同时让真正不同的子主题通过。
DEFAULT_TOPIC_SIMILARITY_THRESHOLD = 0.85
_TOPIC_TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)
_TOPIC_STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "by",
    "for",
    "from",
    "in",
    "into",
    "of",
    "on",
    "or",
    "the",
    "to",
    "vs",
    "with",
}


class TopicStatus(Enum):
    """主题块状态枚举"""

    PENDING = "pending"  # 待研究
    RESEARCHING = "researching"  # 研究中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 失败


class ToolType(Enum):
    """工具类型枚举"""

    RAG = "rag"
    PAPER_SEARCH = "paper_search"
    RUN_CODE = "run_code"
    WEB_SEARCH = "web_search"


# raw_answer 的默认最大大小 (50KB)
DEFAULT_RAW_ANSWER_MAX_SIZE = 50 * 1024


@dataclass
class ToolTrace:
    """
    工具追踪 - 记录单次工具调用的完整循环
    """

    tool_id: str  # 唯一标识符（如 "tool_1"、"tool_2"）
    citation_id: str  # 引用 ID（用于报告引用和锚点，如 CIT-1-01）
    tool_type: str  # 工具类型（rag、web_search 等）
    query: str  # 发出的查询语句
    raw_answer: str  # 工具返回的原始详细结果（可能被截断）
    summary: str  # Note Agent 生成的核心摘要
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    raw_answer_truncated: bool = field(default=False)  # raw_answer 是否被截断
    raw_answer_original_size: int = field(default=0)  # 截断前的原始大小

    def __post_init__(self):
        """后初始化，处理 raw_answer 大小限制"""
        if self.raw_answer_original_size == 0:
            self.raw_answer_original_size = len(self.raw_answer)

        # 需要时截断
        if len(self.raw_answer) > DEFAULT_RAW_ANSWER_MAX_SIZE:
            self.raw_answer = self._truncate_raw_answer(
                self.raw_answer, DEFAULT_RAW_ANSWER_MAX_SIZE
            )
            self.raw_answer_truncated = True

    @staticmethod
    def _truncate_raw_answer(raw_answer: str, max_size: int) -> str:
        """
        截断 raw_answer，同时尽量保留有效的 JSON 结构

        Args:
            raw_answer: 原始答案字符串
            max_size: 最大大小（字节）

        Returns:
            截断后的字符串
        """
        if len(raw_answer) <= max_size:
            return raw_answer

        # 尝试解析为 JSON 并智能截断
        data = parse_json_response(raw_answer, fallback=None)
        if isinstance(data, dict):
            content_fields = ["answer", "content", "text", "chunks", "documents"]
            for field_name in content_fields:
                if field_name in data:
                    if isinstance(data[field_name], str) and len(data[field_name]) > max_size // 2:
                        data[field_name] = data[field_name][: max_size // 2] + "... [truncated]"
                    elif isinstance(data[field_name], list):
                        data[field_name] = data[field_name][:3]
                        if data[field_name]:
                            data[field_name].append({"note": "... additional items truncated"})

            try:
                truncated = json.dumps(data, ensure_ascii=False)
                if len(truncated) <= max_size:
                    return truncated
            except (TypeError, ValueError):
                pass

        # 回退：带标记的简单截断
        truncation_marker = "\n... [content truncated, original size: {} bytes]".format(
            len(raw_answer)
        )
        return raw_answer[: max_size - len(truncation_marker)] + truncation_marker

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToolTrace":
        """从字典创建"""
        return cls(**data)

    @classmethod
    def create_with_size_limit(
        cls,
        tool_id: str,
        citation_id: str,
        tool_type: str,
        query: str,
        raw_answer: str,
        summary: str,
        max_size: int = DEFAULT_RAW_ANSWER_MAX_SIZE,
    ) -> "ToolTrace":
        """
        创建带有显式大小限制的 ToolTrace

        Args:
            tool_id: 工具 ID
            citation_id: 引用 ID
            tool_type: 工具类型
            query: 查询字符串
            raw_answer: 原始答案（需要时会被截断）
            summary: 摘要
            max_size: raw_answer 的最大大小

        Returns:
            ToolTrace 实例
        """
        original_size = len(raw_answer)
        truncated = len(raw_answer) > max_size

        if truncated:
            raw_answer = cls._truncate_raw_answer(raw_answer, max_size)

        return cls(
            tool_id=tool_id,
            citation_id=citation_id,
            tool_type=tool_type,
            query=query,
            raw_answer=raw_answer,
            summary=summary,
            raw_answer_truncated=truncated,
            raw_answer_original_size=original_size,
        )


@dataclass
class TopicBlock:
    """
    主题块 - 队列中的最小调度单元
    """

    block_id: str  # 唯一标识符（如 "block_1"、"block_2"）
    sub_topic: str  # 子主题名称
    overview: str  # 主题概述/背景
    status: TopicStatus = TopicStatus.PENDING  # 主题状态
    tool_traces: list[ToolTrace] = field(default_factory=list)  # 工具调用追踪列表
    iteration_count: int = 0  # 当前迭代次数
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)  # 额外元数据

    def add_tool_trace(self, trace: ToolTrace) -> None:
        """添加工具追踪"""
        self.tool_traces.append(trace)
        self.updated_at = datetime.now().isoformat()

    def get_latest_trace(self) -> ToolTrace | None:
        """获取最新的工具追踪"""
        return self.tool_traces[-1] if self.tool_traces else None

    def get_all_summaries(self) -> str:
        """获取所有工具追踪的拼接摘要"""
        if not self.tool_traces:
            return ""
        return "\n".join([f"[{trace.tool_type}] {trace.summary}" for trace in self.tool_traces])

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        data["status"] = self.status.value
        data["tool_traces"] = [trace.to_dict() for trace in self.tool_traces]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TopicBlock":
        """从字典创建"""
        data_copy = data.copy()
        if isinstance(data_copy.get("status"), str):
            data_copy["status"] = TopicStatus(data_copy["status"])
        if "tool_traces" in data_copy:
            data_copy["tool_traces"] = [
                ToolTrace.from_dict(t) if isinstance(t, dict) else t
                for t in data_copy["tool_traces"]
            ]
        return cls(**data_copy)


class DynamicTopicQueue:
    """
    动态主题队列 - 系统的核心记忆和调度中心
    """

    def __init__(
        self, research_id: str, max_length: int | None = None, state_file: str | None = None
    ):
        """
        初始化队列

        Args:
            research_id: 研究任务 ID
            max_length: 队列最大长度（None 表示无限制）
            state_file: 自动持久化文件路径
        """
        self.research_id = research_id
        self.blocks: list[TopicBlock] = []
        self.block_counter = 0
        self.created_at = datetime.now().isoformat()
        self.max_length = max_length if isinstance(max_length, int) and max_length > 0 else None
        self.state_file = state_file

    def set_state_file(self, filepath: str | None) -> None:
        """设置队列自动持久化文件"""
        self.state_file = filepath
        self._auto_save()

    @staticmethod
    def _normalize_topic(text: str) -> str:
        return re.sub(r"\s+", " ", (text or "").strip().lower())

    @classmethod
    def _topic_tokens(cls, text: str) -> set[str]:
        tokens: set[str] = set()
        for raw in _TOPIC_TOKEN_RE.findall(cls._normalize_topic(text)):
            token = raw.strip()
            if not token or token in _TOPIC_STOPWORDS:
                continue
            # 微型英文词干提取器：足以对齐 "basics" 和 "basic"，
            # 无需添加重量级 NLP 依赖。
            if len(token) > 4 and token.endswith("ies"):
                token = token[:-3] + "y"
            elif len(token) > 3 and token.endswith("s"):
                token = token[:-1]
            tokens.add(token)
        return tokens

    @classmethod
    def _topic_similarity(cls, left: str, right: str) -> float:
        left_norm = cls._normalize_topic(left)
        right_norm = cls._normalize_topic(right)
        if not left_norm or not right_norm:
            return 0.0
        if left_norm == right_norm:
            return 1.0

        sequence_score = difflib.SequenceMatcher(None, left_norm, right_norm).ratio()
        left_tokens = cls._topic_tokens(left_norm)
        right_tokens = cls._topic_tokens(right_norm)
        if not left_tokens or not right_tokens:
            return sequence_score

        overlap = left_tokens & right_tokens
        jaccard = len(overlap) / max(1, len(left_tokens | right_tokens))
        containment = len(overlap) / max(1, min(len(left_tokens), len(right_tokens)))
        token_score = jaccard
        if len(left_tokens) >= 2 and len(right_tokens) >= 2 and jaccard >= 0.5:
            token_score = max(token_score, containment * 0.95)
        return max(sequence_score, token_score)

    def add_block(self, sub_topic: str, overview: str) -> TopicBlock:
        """
        在队列末尾添加新的主题块

        Args:
            sub_topic: 子主题名称
            overview: 主题概述

        Returns:
            创建的 TopicBlock
        """
        if self.max_length and len(self.blocks) >= self.max_length:
            raise RuntimeError(
                f"Queue has reached maximum capacity ({self.max_length}), cannot add new topic."
            )
        self.block_counter += 1
        block_id = f"block_{self.block_counter}"
        block = TopicBlock(block_id=block_id, sub_topic=sub_topic, overview=overview)
        self.blocks.append(block)
        self._auto_save()
        return block

    def has_topic(self, sub_topic: str) -> bool:
        """检查主题是否已存在（不区分大小写，忽略前后空格）"""
        target = self._normalize_topic(sub_topic)
        if not target:
            return False
        return any(self._normalize_topic(b.sub_topic) == target for b in self.blocks)

    def is_full(self) -> bool:
        """当队列已达到配置上限时返回 ``True``。"""
        return self.max_length is not None and len(self.blocks) >= self.max_length

    def find_similar(
        self,
        sub_topic: str,
        *,
        threshold: float = DEFAULT_TOPIC_SIMILARITY_THRESHOLD,
    ) -> TopicBlock | None:
        """返回标题与 ``sub_topic`` 模糊相似的现有块，
        或在没有匹配超过 ``threshold`` 时返回 ``None``。

        用于去重 ``APPEND`` 请求，使 LLM 无法可靠地持续以略有不同的措辞
        提议同一主题。精确规范化匹配始终优先；否则返回超过 ``threshold``
        的最高分块。
        """
        target = self._normalize_topic(sub_topic)
        if not target:
            return None

        best: tuple[float, TopicBlock] | None = None
        for block in self.blocks:
            candidate = self._normalize_topic(block.sub_topic)
            if not candidate:
                continue
            if candidate == target:
                return block
            score = self._topic_similarity(target, candidate)
            if score >= threshold and (best is None or score > best[0]):
                best = (score, block)
        return best[1] if best else None

    def append_child(
        self,
        *,
        parent: TopicBlock | None,
        sub_topic: str,
        overview: str = "",
    ) -> TopicBlock | None:
        """在队列尾部追加新块，可选地在元数据中标记父块的 ID
        以便报告可以重建主题树。

        成功时返回新块，队列已满时返回 ``None``。
        重复检测由调用方负责（需要时先使用 :meth:`find_similar`）。
        """
        if self.is_full():
            return None
        self.block_counter += 1
        block_id = f"block_{self.block_counter}"
        metadata: dict[str, Any] = {}
        if parent is not None:
            metadata["parent_block_id"] = parent.block_id
        block = TopicBlock(
            block_id=block_id,
            sub_topic=sub_topic,
            overview=overview,
            metadata=metadata,
        )
        self.blocks.append(block)
        self._auto_save()
        return block

    def list_topics(self) -> list[str]:
        """列出所有当前主题标题"""
        return [b.sub_topic for b in self.blocks]

    def get_pending_block(self) -> TopicBlock | None:
        """
        获取第一个待处理的主题块

        Returns:
            第一个 PENDING 状态的 TopicBlock，未找到时返回 None
        """
        for block in self.blocks:
            if block.status == TopicStatus.PENDING:
                return block
        return None

    def get_block_by_id(self, block_id: str) -> TopicBlock | None:
        """
        按 ID 获取主题块

        Args:
            block_id: 主题块 ID

        Returns:
            对应的 TopicBlock，未找到时返回 None
        """
        for block in self.blocks:
            if block.block_id == block_id:
                return block
        return None

    def mark_researching(self, block_id: str) -> bool:
        """
        将主题块标记为研究中

        Args:
            block_id: 主题块 ID

        Returns:
            标记是否成功
        """
        block = self.get_block_by_id(block_id)
        if block:
            block.status = TopicStatus.RESEARCHING
            block.updated_at = datetime.now().isoformat()
            self._auto_save()
            return True
        return False

    def mark_completed(self, block_id: str) -> bool:
        """
        将主题块标记为已完成

        Args:
            block_id: 主题块 ID

        Returns:
            标记是否成功
        """
        block = self.get_block_by_id(block_id)
        if block:
            block.status = TopicStatus.COMPLETED
            block.updated_at = datetime.now().isoformat()
            self._auto_save()
            return True
        return False

    def mark_failed(self, block_id: str) -> bool:
        """
        将主题块标记为失败

        Args:
            block_id: 主题块 ID

        Returns:
            标记是否成功
        """
        block = self.get_block_by_id(block_id)
        if block:
            block.status = TopicStatus.FAILED
            block.updated_at = datetime.now().isoformat()
            self._auto_save()
            return True
        return False

    def get_all_completed_blocks(self) -> list[TopicBlock]:
        """获取所有已完成的主题块"""
        return [b for b in self.blocks if b.status == TopicStatus.COMPLETED]

    def get_all_pending_blocks(self) -> list[TopicBlock]:
        """获取所有待处理的主题块"""
        return [b for b in self.blocks if b.status == TopicStatus.PENDING]

    def is_all_completed(self) -> bool:
        """检查所有主题块是否已完成"""
        if not self.blocks:
            return False
        return all(b.status == TopicStatus.COMPLETED for b in self.blocks)

    def get_statistics(self) -> dict[str, Any]:
        """获取队列统计信息"""
        return {
            "total_blocks": len(self.blocks),
            "pending": len(self.get_all_pending_blocks()),
            "researching": len([b for b in self.blocks if b.status == TopicStatus.RESEARCHING]),
            "completed": len(self.get_all_completed_blocks()),
            "failed": len([b for b in self.blocks if b.status == TopicStatus.FAILED]),
            "total_tool_calls": sum(len(b.tool_traces) for b in self.blocks),
        }

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "research_id": self.research_id,
            "created_at": self.created_at,
            "blocks": [b.to_dict() for b in self.blocks],
            "statistics": self.get_statistics(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DynamicTopicQueue":
        """从字典创建"""
        queue = cls(data["research_id"])
        queue.created_at = data.get("created_at", queue.created_at)
        for block_data in data.get("blocks", []):
            block = TopicBlock.from_dict(block_data)
            queue.blocks.append(block)
            # 更新计数器
            if block.block_id.startswith("block_"):
                try:
                    block_num = int(block.block_id.split("_")[1])
                    queue.block_counter = max(queue.block_counter, block_num)
                except (ValueError, IndexError):
                    pass
        return queue

    def save_to_json(self, filepath: str) -> None:
        """将队列保存为 JSON 文件"""
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    def _auto_save(self) -> None:
        """如果设置了 state_file 则自动保存"""
        if self.state_file:
            try:
                self.save_to_json(self.state_file)
            except Exception as exc:
                print(f"⚠️ Failed to save queue progress: {exc}")

    @classmethod
    def load_from_json(cls, filepath: str) -> "DynamicTopicQueue":
        """从 JSON 文件加载队列"""
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)


__all__ = [
    "DynamicTopicQueue",
    "ToolTrace",
    "ToolType",
    "TopicBlock",
    "TopicStatus",
]
