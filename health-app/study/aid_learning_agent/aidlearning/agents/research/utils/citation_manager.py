#!/usr/bin/env python
"""
CitationManager - 引用管理系统
负责从工具调用中提取引用信息并管理引用 JSON 文件
"""

import asyncio
from datetime import datetime
import html
import json
from pathlib import Path
from typing import Any

from aidlearning.services.path_service import get_path_service
from aidlearning.utils.json_parser import parse_json_response


class CitationManager:
    """具有全局 ID 管理的引用管理器"""

    def __init__(self, research_id: str, cache_dir: Path | None = None):
        """
        初始化引用管理器

        Args:
            research_id: 研究任务 ID
            cache_dir: 缓存目录路径，为 None 时使用默认路径
        """
        self.research_id = research_id
        if cache_dir is None:
            cache_dir = get_path_service().get_task_workspace("deep_research", research_id)
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.citations_file = self.cache_dir / "citations.json"
        self._citations: dict[str, dict[str, Any]] = {}

        # 全局引用 ID 计数器
        self._plan_counter = 0  # 用于 PLAN-XX 格式（规划阶段）
        self._block_counters: dict[str, int] = {}  # 用于 CIT-X-XX 格式（研究阶段）

        # 引用编号映射（citation_id -> 文内引用的 ref_number）
        self._ref_number_map: dict[str, int] = {}

        # 并行模式下线程安全操作的锁
        self._lock = asyncio.Lock()

        self._load_citations()

    def generate_plan_citation_id(self) -> str:
        """
        为规划阶段生成新的引用 ID（PLAN-XX 格式）

        Returns:
            PLAN-XX 格式的引用 ID
        """
        self._plan_counter += 1
        return f"PLAN-{self._plan_counter:02d}"

    def generate_research_citation_id(self, block_id: str) -> str:
        """
        为研究阶段生成新的引用 ID（CIT-X-XX 格式）

        Args:
            block_id: 块 ID（如 "block_3"）

        Returns:
            CIT-X-XX 格式的引用 ID
        """
        # 从 block_id 中提取块编号
        block_num = 0
        try:
            if block_id and "_" in block_id:
                block_num = int(block_id.split("_")[1])
        except (ValueError, IndexError):
            block_num = 0

        # 递增此块的计数器
        block_key = str(block_num)
        if block_key not in self._block_counters:
            self._block_counters[block_key] = 0
        self._block_counters[block_key] += 1

        return f"CIT-{block_num}-{self._block_counters[block_key]:02d}"

    def get_next_citation_id(self, stage: str = "research", block_id: str = "") -> str:
        """
        获取下一个可用的引用 ID

        Args:
            stage: "planning" 或 "research"
            block_id: 块 ID（研究阶段必需）

        Returns:
            下一个可用的引用 ID
        """
        if stage == "planning":
            return self.generate_plan_citation_id()
        return self.generate_research_citation_id(block_id)

    def citation_exists(self, citation_id: str) -> bool:
        """
        检查引用 ID 是否已存在

        Args:
            citation_id: 要检查的引用 ID

        Returns:
            引用存在返回 True，否则返回 False
        """
        return citation_id in self._citations

    def _load_citations(self):
        """从 JSON 文件加载引用信息并恢复计数器"""
        if self.citations_file.exists():
            try:
                with open(self.citations_file, encoding="utf-8") as f:
                    data = json.load(f)
                    self._citations = data.get("citations", {})

                    # 首先尝试从保存的状态恢复计数器
                    counters = data.get("counters", {})
                    if counters:
                        self._plan_counter = counters.get("plan_counter", 0)
                        self._block_counters = counters.get("block_counters", {})
                    else:
                        # 回退：从现有引用恢复计数器
                        self._restore_counters_from_citations()
            except Exception as e:
                print(f"⚠️ Failed to load citation file: {e}")
                self._citations = {}
        else:
            self._citations = {}

    def _restore_counters_from_citations(self):
        """从现有引用恢复引用计数器以避免 ID 冲突"""
        for citation_id in self._citations.keys():
            if citation_id.startswith("PLAN-"):
                try:
                    num = int(citation_id.replace("PLAN-", ""))
                    self._plan_counter = max(self._plan_counter, num)
                except ValueError:
                    pass
            elif citation_id.startswith("CIT-"):
                try:
                    parts = citation_id.replace("CIT-", "").split("-")
                    if len(parts) == 2:
                        block_num = parts[0]
                        seq_num = int(parts[1])
                        if block_num not in self._block_counters:
                            self._block_counters[block_num] = 0
                        self._block_counters[block_num] = max(
                            self._block_counters[block_num], seq_num
                        )
                except (ValueError, IndexError):
                    pass

    def _save_citations(self):
        """将引用信息保存为 JSON 文件"""
        try:
            data = {
                "research_id": self.research_id,
                "updated_at": datetime.now().isoformat(),
                "citations": self._citations,
                "counters": {
                    "plan_counter": self._plan_counter,
                    "block_counters": self._block_counters,
                },
            }
            with open(self.citations_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Failed to save citation file: {e}")

    def validate_citation_references(self, text: str) -> dict[str, Any]:
        """
        验证文本中的引用引用并识别无效引用

        Args:
            text: 包含引用引用的文本，如 [[CIT-X-XX]]

        Returns:
            包含验证结果的字典：
            {
                "valid_citations": [...],
                "invalid_citations": [...],
                "is_valid": bool
            }
        """
        import re

        # 查找文本中所有引用引用
        pattern = r"\[\[([A-Z]+-\d+-?\d*)\]\]"
        found_refs = re.findall(pattern, text)

        valid = []
        invalid = []

        for ref in found_refs:
            if self.citation_exists(ref):
                valid.append(ref)
            else:
                invalid.append(ref)

        return {
            "valid_citations": valid,
            "invalid_citations": invalid,
            "is_valid": len(invalid) == 0,
            "total_found": len(found_refs),
        }

    def fix_invalid_citations(self, text: str) -> str:
        """
        移除或标记文本中的无效引用引用

        Args:
            text: 包含引用引用的文本

        Returns:
            已移除或标记无效引用的文本
        """
        import re

        pattern = r"\[\[([A-Z]+-\d+-?\d*)\]\]\(#ref-[a-z]+-\d+-?\d*\)"

        def replace_invalid(match):
            citation_id = match.group(1)
            if self.citation_exists(citation_id):
                return match.group(0)  # 保留有效引用
            return ""  # 移除无效引用

        return re.sub(pattern, replace_invalid, text)

    def add_citation(
        self,
        citation_id: str,
        tool_type: str,
        tool_trace: Any,
        raw_answer: str,  # 原始答案 JSON 字符串
        tool_metadata: dict[str, Any] | None = None,
    ) -> bool:
        """
        添加引用信息

        Args:
            citation_id: 引用 ID
            tool_type: 工具类型
            tool_trace: ToolTrace 对象
            raw_answer: 原始答案（JSON 字符串）
            tool_metadata: 此调用的结构化 ToolResult.metadata（可用时）。
                提取器优先使用此字段而非重新解析 ``raw_answer``，
                因为工具消息现在携带文本答案而非 JSON 负载。

        Returns:
            添加是否成功
        """
        try:
            tool_type_lower = tool_type.lower()

            if tool_type_lower in ("rag", "rag_naive", "rag_hybrid"):
                citation_info = self._extract_rag_citation(
                    citation_id, "rag", raw_answer, tool_trace
                )
            elif tool_type_lower == "web_search":
                citation_info = self._extract_web_citation(
                    citation_id, tool_type, raw_answer, tool_trace, tool_metadata
                )
            elif tool_type_lower == "paper_search":
                citation_info = self._extract_paper_citation(
                    citation_id, tool_type, raw_answer, tool_trace, tool_metadata
                )
            elif tool_type_lower == "run_code":
                citation_info = self._extract_code_citation(citation_id, tool_type, tool_trace)
            else:
                # 未知工具类型，使用通用格式
                citation_info = self._extract_generic_citation(citation_id, tool_type, tool_trace)

            if citation_info:
                self._citations[citation_id] = citation_info
                self._save_citations()
                return True
            return False
        except Exception as e:
            print(f"⚠️ Failed to add citation (citation_id={citation_id}): {e}")
            return False

    def _extract_rag_citation(
        self, citation_id: str, tool_type: str, raw_answer: str, tool_trace: Any
    ) -> dict[str, Any]:
        """为 RAG 检索提取引用信息，包含源文档"""
        citation_info = {
            "citation_id": citation_id,
            "tool_type": tool_type,
            "query": tool_trace.query,
            "summary": tool_trace.summary,
            "timestamp": tool_trace.timestamp,
            "sources": [],  # 源文档列表
        }

        try:
            # 解析 raw_answer 以提取源信息
            answer_data = parse_json_response(raw_answer)

            # 如果可用则提取源文档
            # RAG 响应中的常见字段：chunks、documents、sources、context
            sources = []

            # 尝试不同的源文档字段名
            for field_name in ["chunks", "documents", "sources", "context", "retrieved_docs"]:
                if field_name in answer_data:
                    source_list = answer_data[field_name]
                    if isinstance(source_list, list):
                        for i, doc in enumerate(source_list[:5]):  # Limit to 5 sources
                            source_info = {}
                            if isinstance(doc, dict):
                                source_info["title"] = doc.get("title", doc.get("doc_title", ""))
                                source_info["content_preview"] = doc.get(
                                    "content", doc.get("text", "")
                                )[:200]
                                source_info["source_file"] = doc.get(
                                    "source", doc.get("file_path", doc.get("filename", ""))
                                )
                                source_info["page"] = doc.get("page", doc.get("page_number", ""))
                                source_info["chunk_id"] = doc.get("chunk_id", doc.get("id", i))
                                source_info["score"] = doc.get("score", doc.get("similarity", ""))
                            elif isinstance(doc, str):
                                source_info["content_preview"] = doc[:200]
                            if source_info:
                                sources.append(source_info)
                    break

            # 同时提取 kb_name（如果可用）
            citation_info["kb_name"] = answer_data.get("kb_name", "")
            citation_info["sources"] = sources
            citation_info["total_sources"] = len(sources)

        except (json.JSONDecodeError, Exception) as e:
            # 如果解析失败，仍返回基本引用信息
            print(f"⚠️ Failed to parse RAG source info: {e}")

        return citation_info

    def _extract_web_citation(
        self,
        citation_id: str,
        tool_type: str,
        raw_answer: str,
        tool_trace: Any,
        tool_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """为网页搜索提取引用信息，包含 URL。

        优先使用结构化的 ``ToolResult.metadata``（携带提供商的
        ``citations``/``results`` 列表），因为 ``raw_answer`` 是呈现给
        LLM 的文本答案，而非 JSON 负载。
        """
        citation_info = {
            "citation_id": citation_id,
            "tool_type": tool_type,
            "query": tool_trace.query,
            "summary": tool_trace.summary,
            "timestamp": tool_trace.timestamp,
            "web_sources": [],
        }

        web_sources: list[dict[str, Any]] = []

        candidate_lists: list[Any] = []
        if isinstance(tool_metadata, dict):
            for field_name in ("citations", "results", "web_results", "search_results", "urls"):
                value = tool_metadata.get(field_name)
                if isinstance(value, list) and value:
                    candidate_lists.append(value)
                    break

        if not candidate_lists:
            try:
                answer_data = parse_json_response(raw_answer)
                if isinstance(answer_data, dict):
                    for field_name in (
                        "citations",
                        "results",
                        "web_results",
                        "search_results",
                        "urls",
                    ):
                        value = answer_data.get(field_name)
                        if isinstance(value, list) and value:
                            candidate_lists.append(value)
                            break
            except (json.JSONDecodeError, Exception):
                pass

        for result_list in candidate_lists:
            for result in result_list:
                if not isinstance(result, dict):
                    continue
                url = result.get("url") or result.get("link") or ""
                if not url:
                    continue
                snippet = result.get("snippet") or result.get("description") or ""
                web_sources.append(
                    {
                        "title": result.get("title", ""),
                        "url": url,
                        "snippet": snippet[:200],
                        "domain": result.get("domain", ""),
                    }
                )

        citation_info["web_sources"] = web_sources
        citation_info["total_sources"] = len(web_sources)
        return citation_info

    def _extract_paper_citation(
        self,
        citation_id: str,
        tool_type: str,
        raw_answer: str,
        tool_trace: Any,
        tool_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """为论文搜索提取引用信息 - 支持多篇论文。

        优先使用 ``tool_metadata['papers']``（由 ``PaperSearchToolWrapper`` 设置），
        因为工具消息的 ``content`` 是 Markdown 列表而非 JSON 负载。
        """
        citation_info = {
            "citation_id": citation_id,
            "tool_type": tool_type,
            "query": tool_trace.query,
            "summary": tool_trace.summary,
            "timestamp": tool_trace.timestamp,
            "papers": [],
        }

        try:
            papers: list[Any] = []
            if isinstance(tool_metadata, dict):
                meta_papers = tool_metadata.get("papers")
                if isinstance(meta_papers, list):
                    papers = meta_papers
            if not papers:
                answer_data = parse_json_response(raw_answer)
                if isinstance(answer_data, dict):
                    papers = answer_data.get("papers", []) or []

            if not papers:
                return citation_info

            # 处理所有论文（最多 5 篇以保证实用性）
            processed_papers = []
            for paper in papers[:5]:
                # 格式化作者
                authors = paper.get("authors", [])
                author_str = ", ".join(authors[:3])  # 最多显示 3 位作者
                if len(authors) > 3:
                    author_str += " et al."

                paper_info = {
                    "title": paper.get("title", ""),
                    "authors": author_str,
                    "authors_list": authors,
                    "year": paper.get("year", ""),
                    "url": paper.get("url", ""),
                    "arxiv_id": paper.get("arxiv_id", ""),
                    "abstract": paper.get("abstract", "")[:300],  # 截断摘要
                    "doi": paper.get("doi", ""),
                    "venue": paper.get("venue", paper.get("journal", "")),
                }
                processed_papers.append(paper_info)

            citation_info["papers"] = processed_papers
            citation_info["total_papers"] = len(processed_papers)

            if processed_papers:
                primary = processed_papers[0]
                citation_info["title"] = primary["title"]
                citation_info["authors"] = primary["authors"]
                citation_info["authors_list"] = primary["authors_list"]
                citation_info["year"] = primary["year"]
                citation_info["url"] = primary["url"]
                citation_info["arxiv_id"] = primary["arxiv_id"]

            return citation_info
        except Exception as e:
            print(f"⚠️ Failed to parse paper citation: {e}")
            # 仍返回基本引用信息
            return citation_info

    def _extract_code_citation(
        self, citation_id: str, tool_type: str, tool_trace: Any
    ) -> dict[str, Any]:
        """为代码执行提取引用信息"""
        return {
            "citation_id": citation_id,
            "tool_type": tool_type,
            "query": tool_trace.query,  # 代码内容
            "summary": tool_trace.summary,
            "timestamp": tool_trace.timestamp,
        }

    def _extract_generic_citation(
        self, citation_id: str, tool_type: str, tool_trace: Any
    ) -> dict[str, Any]:
        """提取通用引用信息（未知工具类型）"""
        return {
            "citation_id": citation_id,
            "tool_type": tool_type,
            "query": tool_trace.query,
            "summary": tool_trace.summary,
            "timestamp": tool_trace.timestamp,
        }

    def get_citation(self, citation_id: str) -> dict[str, Any] | None:
        """获取指定引用 ID 的引用信息"""
        return self._citations.get(citation_id)

    def get_all_citations(self) -> dict[str, dict[str, Any]]:
        """获取所有引用信息"""
        return self._citations.copy()

    def get_citations_file_path(self) -> Path:
        """获取引用 JSON 文件路径"""
        return self.citations_file

    def format_citation_for_report(self, citation_id: str) -> str | None:
        """将 ``citation_id`` 的参考列表条目渲染为 HTML。

        输出可能包含 ``<em>``、``<a>`` 和 ``<br>`` 标签。所有用户控制的字段
        在此方法内部进行 HTML 转义，以便调用方可以直接将结果放入页面而无需额外的转义步骤。
        """
        citation = self.get_citation(citation_id)
        if not citation:
            return None

        tool_type = citation.get("tool_type", "").lower()

        if tool_type == "paper_search":
            return self._format_paper_search_apa(citation)

        if tool_type in ("rag", "rag_naive", "rag_hybrid"):
            query = html.escape(str(citation.get("query", "")))
            kb_name = citation.get("kb_name", "")
            sources = citation.get("sources", []) or []

            parts = [f"RAG: {query}"]
            if kb_name:
                parts.append(f"[KB: {html.escape(str(kb_name))}]")
            source_titles = [
                html.escape(str(s.get("title") or s.get("source_file") or ""))
                for s in sources[:3]
                if s
            ]
            source_titles = [t for t in source_titles if t]
            if source_titles:
                parts.append(f"[Sources: {', '.join(source_titles)}]")
            return " ".join(parts)

        if tool_type == "web_search":
            return self._format_web_search_with_links(citation)

        tool_type_display = {"run_code": "Code Execution"}.get(tool_type, tool_type)
        query = html.escape(str(citation.get("query", "")))
        return f"{html.escape(str(tool_type_display))}: {query}"

    def _format_paper_search_apa(self, citation: dict[str, Any]) -> str | None:
        """将 paper_search 引用中的每篇论文渲染为单独的 APA 格式条目，
        以 ``<br>`` 连接。

        使用的 APA 格式：``Authors (Year). *Title*. arXiv. <url>``。
        缺失的字段会被跳过，不留多余标点。
        """
        papers: list[dict[str, Any]] = list(citation.get("papers") or [])
        if not papers:
            # 仅携带顶层字段的引用的回退处理。
            fallback = {
                "title": citation.get("title", ""),
                "authors": citation.get("authors", ""),
                "year": citation.get("year", ""),
                "url": citation.get("url", ""),
                "arxiv_id": citation.get("arxiv_id", ""),
            }
            if any(fallback.values()):
                papers = [fallback]
        entries: list[str] = []
        for paper in papers:
            entry = self._format_one_apa(paper)
            if entry:
                entries.append(entry)
        if not entries:
            return None
        return "<br>".join(entries)

    @staticmethod
    def _format_one_apa(paper: dict[str, Any]) -> str | None:
        authors_raw = paper.get("authors") or paper.get("authors_list") or ""
        if isinstance(authors_raw, list):
            authors = ", ".join(str(a) for a in authors_raw[:3] if a)
            if len(authors_raw) > 3:
                authors += " et al."
        else:
            authors = str(authors_raw).strip()
        year = str(paper.get("year") or "").strip()
        title = str(paper.get("title") or "").strip()
        url = str(paper.get("url") or "").strip()
        arxiv_id = str(paper.get("arxiv_id") or "").strip()
        if not (title or authors):
            return None
        if not url and arxiv_id:
            url = f"https://arxiv.org/abs/{arxiv_id}"

        pieces: list[str] = []
        if authors:
            pieces.append(html.escape(authors))
        if year:
            pieces.append(f"({html.escape(year)}).")
        elif pieces:
            pieces[-1] = pieces[-1] + "."
        if title:
            pieces.append(f"<em>{html.escape(title)}</em>.")
        pieces.append("arXiv.")
        if url:
            safe_url = html.escape(url, quote=True)
            pieces.append(f'<a href="{safe_url}">{html.escape(url)}</a>')
        return " ".join(pieces)

    @staticmethod
    def _format_web_search_with_links(citation: dict[str, Any]) -> str:
        query = str(citation.get("query") or "").strip()
        web_sources = citation.get("web_sources") or []
        head = "Web Search"
        if query:
            head = f"Web Search: {html.escape(query)}"
        link_items: list[str] = []
        for source in web_sources:
            url = str(source.get("url") or "").strip()
            if not url:
                continue
            safe_url = html.escape(url, quote=True)
            title = str(source.get("title") or "").strip() or url
            link_items.append(f'<a href="{safe_url}">{html.escape(title)}</a>')
        if not link_items:
            return head
        return head + "<br>" + "<br>".join(link_items)

    # ========== Reference Number Mapping Methods ==========

    def _get_citation_dedup_key(self, citation: dict, paper: dict = None) -> str:
        """
        Generate unique key for citation deduplication

        Deduplication is ONLY applied to paper_search citations where the same paper
        (title + first author) is cited multiple times. All other citation types
        get unique ref_numbers based on their citation_id.

        Args:
            citation: The citation dict
            paper: Optional paper dict for paper_search citations

        Returns:
            Unique string key for deduplication
        """
        tool_type = citation.get("tool_type", "").lower()
        citation_id = citation.get("citation_id", "")

        if tool_type == "paper_search" and paper:
            # For papers: use title + first author (normalized) - allow dedup for same paper
            title = paper.get("title", "").lower().strip()
            authors = paper.get("authors", "").lower().strip()
            # Extract first author if multiple
            first_author = authors.split(",")[0].strip() if authors else ""
            if title:  # Only dedup if we have a title
                return f"paper:{title}|{first_author}"
            # No title? Use citation_id to ensure unique
            return f"unique:{citation_id}"
        elif tool_type == "paper_search":
            # Fallback for paper_search without paper dict
            title = citation.get("title", "").lower().strip()
            authors = citation.get("authors", "").lower().strip()
            first_author = authors.split(",")[0].strip() if authors else ""
            if title:  # Only dedup if we have a title
                return f"paper:{title}|{first_author}"
            return f"unique:{citation_id}"
        else:
            # For RAG/web_search/etc: each citation gets unique ref_number
            # Use citation_id to ensure each citation is unique
            return f"unique:{citation_id}"

    def _extract_citation_sort_key(self, citation_id: str) -> tuple:
        """
        Extract numeric sort key from citation ID for ordering

        Args:
            citation_id: Citation ID (e.g., "PLAN-01", "CIT-1-02")

        Returns:
            Tuple for sorting (stage, block_num, seq_num)
        """
        try:
            if citation_id.startswith("PLAN-"):
                # PLAN-XX format: put at the beginning
                num = int(citation_id.replace("PLAN-", ""))
                return (0, 0, num)
            # CIT-X-XX format
            parts = citation_id.replace("CIT-", "").split("-")
            if len(parts) == 2:
                return (1, int(parts[0]), int(parts[1]))
        except (ValueError, IndexError):
            pass
        return (999, 999, 999)

    def build_ref_number_map(self) -> dict[str, int]:
        """
        Build citation_id to reference number mapping with deduplication.
        This is the single source of truth for ref_number assignment.

        Returns:
            Dictionary mapping citation_id to reference number (1-based)
        """
        if not self._citations:
            self._ref_number_map = {}
            return self._ref_number_map

        # Sort all citation IDs by their numeric parts
        sorted_citation_ids = sorted(self._citations.keys(), key=self._extract_citation_sort_key)

        # Track seen dedup keys and their assigned ref_numbers
        seen_keys: dict[str, int] = {}
        ref_idx = 0
        ref_map: dict[str, int] = {}

        for citation_id in sorted_citation_ids:
            citation = self._citations.get(citation_id)
            if not citation:
                continue

            tool_type = citation.get("tool_type", "").lower()

            if tool_type == "paper_search":
                # paper_search may have multiple papers - each paper gets a separate ref_number
                papers = citation.get("papers", [])
                if papers:
                    for paper_idx, paper in enumerate(papers):
                        # Check for duplicate using dedup key
                        dedup_key = self._get_citation_dedup_key(citation, paper)

                        if dedup_key in seen_keys:
                            # Map to existing ref_number
                            existing_ref = seen_keys[dedup_key]
                            if paper_idx == 0:
                                ref_map[citation_id] = existing_ref
                            ref_map[f"{citation_id}-{paper_idx + 1}"] = existing_ref
                        else:
                            # New unique citation
                            ref_idx += 1
                            seen_keys[dedup_key] = ref_idx
                            if paper_idx == 0:
                                ref_map[citation_id] = ref_idx
                            ref_map[f"{citation_id}-{paper_idx + 1}"] = ref_idx
                else:
                    # Paper search without papers array
                    dedup_key = self._get_citation_dedup_key(citation)
                    if dedup_key in seen_keys:
                        ref_map[citation_id] = seen_keys[dedup_key]
                    else:
                        ref_idx += 1
                        seen_keys[dedup_key] = ref_idx
                        ref_map[citation_id] = ref_idx
            else:
                # Non-paper citations
                dedup_key = self._get_citation_dedup_key(citation)
                if dedup_key in seen_keys:
                    ref_map[citation_id] = seen_keys[dedup_key]
                else:
                    ref_idx += 1
                    seen_keys[dedup_key] = ref_idx
                    ref_map[citation_id] = ref_idx

        self._ref_number_map = ref_map
        return ref_map

    def get_ref_number(self, citation_id: str) -> int:
        """
        Get the reference number for a citation ID.
        If the map hasn't been built yet, build it first.

        Args:
            citation_id: Citation ID

        Returns:
            Reference number (1-based), or 0 if not found
        """
        if not self._ref_number_map:
            self.build_ref_number_map()
        return self._ref_number_map.get(citation_id, 0)

    def get_ref_number_map(self) -> dict[str, int]:
        """
        Get the full reference number map.
        If the map hasn't been built yet, build it first.

        Returns:
            Dictionary mapping citation_id to reference number
        """
        if not self._ref_number_map:
            self.build_ref_number_map()
        return self._ref_number_map.copy()

    # ========== Async thread-safe methods for parallel mode ==========

    async def generate_plan_citation_id_async(self) -> str:
        """
        Thread-safe async version of generate_plan_citation_id for parallel mode

        Returns:
            Citation ID in PLAN-XX format
        """
        async with self._lock:
            return self.generate_plan_citation_id()

    async def generate_research_citation_id_async(self, block_id: str) -> str:
        """
        Thread-safe async version of generate_research_citation_id for parallel mode

        Args:
            block_id: Block ID (e.g., "block_3")

        Returns:
            Citation ID in CIT-X-XX format
        """
        async with self._lock:
            return self.generate_research_citation_id(block_id)

    async def get_next_citation_id_async(self, stage: str = "research", block_id: str = "") -> str:
        """
        Thread-safe async version of get_next_citation_id for parallel mode

        Args:
            stage: "planning" or "research"
            block_id: Block ID (required for research stage)

        Returns:
            Next available citation ID
        """
        async with self._lock:
            return self.get_next_citation_id(stage, block_id)

    async def add_citation_async(
        self,
        citation_id: str,
        tool_type: str,
        tool_trace: Any,
        raw_answer: str,
        tool_metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Thread-safe async version of :meth:`add_citation`."""
        async with self._lock:
            return self.add_citation(citation_id, tool_type, tool_trace, raw_answer, tool_metadata)


__all__ = ["CitationManager"]
