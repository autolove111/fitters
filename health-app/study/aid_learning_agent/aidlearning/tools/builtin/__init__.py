"""内置工具实现和元数据。"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from aidlearning.tools.protocol import BaseTool, ToolDefinition, ToolParameter, ToolResult
from aidlearning.tools.prompting import load_prompt_hints

logger = logging.getLogger(__name__)


class _PromptHintsMixin:
    """内置工具共享的提示提示加载器。"""

    def get_prompt_hints(self, language: str = "en"):
        return load_prompt_hints(self.name, language=language)


class BrainstormTool(_PromptHintsMixin, BaseTool):
    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="brainstorm",
            description="Broadly explore multiple possibilities for a topic and give a short rationale for each.",
            parameters=[
                ToolParameter(
                    name="topic",
                    type="string",
                    description="The topic, goal, or problem to brainstorm about.",
                ),
                ToolParameter(
                    name="context",
                    type="string",
                    description="Optional supporting context, constraints, or background.",
                    required=False,
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        from aidlearning.tools.builtin.brainstorm import brainstorm

        result = await brainstorm(
            topic=kwargs.get("topic", ""),
            context=kwargs.get("context", ""),
            api_key=kwargs.get("api_key"),
            base_url=kwargs.get("base_url"),
            model=kwargs.get("model"),
            max_tokens=kwargs.get("max_tokens"),
            temperature=kwargs.get("temperature"),
        )
        return ToolResult(content=result.get("answer", ""), metadata=result)


class RAGTool(_PromptHintsMixin, BaseTool):
    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="rag",
            description=(
                "Retrieve relevant passages from one of the knowledge bases the "
                "user attached to this turn. Call once per knowledge base you "
                "want to consult; the system runs them in parallel."
            ),
            parameters=[
                ToolParameter(name="query", type="string", description="Search query."),
                ToolParameter(
                    name="kb_name",
                    type="string",
                    description="Knowledge base to search. Must be one of the attached knowledge bases.",
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        from aidlearning.tools.builtin.rag_tool import rag_search

        query = str(kwargs.get("query") or "").strip()
        if not query:
            raise ValueError("RAG query must be a non-empty string.")
        kb_name = str(kwargs.get("kb_name") or "").strip()
        if not kb_name:
            raise ValueError("RAG requires an explicit kb_name.")
        event_sink = kwargs.get("event_sink")
        extra_kwargs = {
            key: value
            for key, value in kwargs.items()
            if key not in {"query", "kb_name", "event_sink"}
        }

        result = await rag_search(
            query=query,
            kb_name=kb_name,
            event_sink=event_sink,
            **extra_kwargs,
        )
        content = result.get("answer") or result.get("content", "")
        return ToolResult(
            content=content,
            sources=[{"type": "rag", "query": query, "kb_name": kb_name}],
            metadata=result,
        )


class WebSearchTool(_PromptHintsMixin, BaseTool):
    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="web_search",
            description="Search the web and return summarised results with citations.",
            parameters=[
                ToolParameter(name="query", type="string", description="Search query."),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        from aidlearning.tools.builtin.web_search import web_search

        query = kwargs.get("query", "")
        output_dir = kwargs.get("output_dir")
        verbose = kwargs.get("verbose", False)
        result = await asyncio.to_thread(
            web_search,
            query=query,
            output_dir=output_dir,
            verbose=verbose,
        )

        if isinstance(result, dict):
            answer = result.get("answer", "")
            citations = result.get("citations", [])
        else:
            answer = str(result)
            citations = []

        return ToolResult(
            content=answer,
            sources=[
                {"type": "web", "url": citation.get("url", ""), "title": citation.get("title", "")}
                for citation in citations
            ],
            metadata=result if isinstance(result, dict) else {"raw": answer},
        )


class CodeExecutionTool(_PromptHintsMixin, BaseTool):
    _CODEGEN_SYSTEM_PROMPT = """You are a Python code generator.

Convert the user's natural-language request into executable Python code only.

Rules:
- Output only Python code, with no markdown fences or explanation.
- Prefer standard library plus these common packages when useful: math, numpy, pandas, matplotlib, scipy, sympy.
- Print the final answer to stdout.
- Save plots or generated files to the current working directory.
- Keep the code focused on the requested computation or verification task.
"""

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="code_execution",
            description="Turn a natural-language computation request into Python, run it in a restricted Python worker, and return the result.",
            parameters=[
                ToolParameter(
                    name="intent",
                    type="string",
                    description="Natural-language description of the computation or verification task.",
                ),
                ToolParameter(
                    name="code",
                    type="string",
                    description="Optional raw Python code to execute directly.",
                    required=False,
                ),
                ToolParameter(
                    name="timeout",
                    type="integer",
                    description="Max execution time in seconds.",
                    required=False,
                    default=30,
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        from aidlearning.tools.builtin.code_executor import run_code

        code = str(kwargs.get("code") or "").strip()
        intent = str(kwargs.get("intent") or kwargs.get("query") or "").strip()
        timeout = int(kwargs.get("timeout", 30) or 30)
        workspace_dir = kwargs.get("workspace_dir")
        feature = kwargs.get("feature")
        task_id = kwargs.get("task_id")
        session_id = kwargs.get("session_id")
        turn_id = kwargs.get("turn_id")

        if not code:
            if not intent:
                raise ValueError("code_execution requires either 'intent' or 'code'")
            code = await self._generate_code(intent)

        result = await run_code(
            language="python",
            code=code,
            timeout=timeout,
            workspace_dir=workspace_dir,
            feature=feature,
            task_id=task_id,
            session_id=session_id,
            turn_id=turn_id,
        )
        stdout = result.get("stdout", "")
        stderr = result.get("stderr", "")
        exit_code = result.get("exit_code", 1)
        artifacts = result.get("artifacts", [])

        parts: list[str] = []
        if stdout:
            parts.append(stdout.strip())
        if stderr:
            label = "Error" if exit_code else "Stderr"
            parts.append(f"{label}:\n{stderr.strip()}")
        if artifacts:
            parts.append(f"Artifacts: {', '.join(str(item) for item in artifacts)}")
        if not parts:
            parts.append("Execution completed with no output.")

        metadata = {**result, "code": code, "intent": intent}
        return ToolResult(
            content="\n\n".join(parts),
            success=exit_code == 0,
            sources=[{"type": "code", "file": artifact} for artifact in artifacts],
            metadata=metadata,
        )

    async def _generate_code(self, intent: str) -> str:
        from aidlearning.services.llm import complete, get_token_limit_kwargs
        from aidlearning.services.llm.config import get_llm_config

        llm_config = get_llm_config()
        completion_kwargs: dict[str, Any] = {"temperature": 0.0}
        if getattr(llm_config, "model", None):
            completion_kwargs.update(get_token_limit_kwargs(llm_config.model, 1200))

        response = await complete(
            prompt=intent,
            system_prompt=self._CODEGEN_SYSTEM_PROMPT,
            model=llm_config.model,
            api_key=llm_config.api_key,
            base_url=llm_config.base_url,
            api_version=getattr(llm_config, "api_version", None),
            binding=getattr(llm_config, "binding", None),
            **completion_kwargs,
        )
        code = self._strip_markdown_fences(response)
        if not code.strip():
            raise ValueError("LLM returned empty code for code_execution")
        return code

    @staticmethod
    def _strip_markdown_fences(content: str) -> str:
        cleaned = content.strip()
        if not cleaned.startswith("```"):
            return cleaned

        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()


class ReasonTool(_PromptHintsMixin, BaseTool):
    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="reason",
            description=(
                "Perform deep reasoning on a complex sub-problem using a dedicated LLM call. "
                "Use when the current context is insufficient for a confident answer."
            ),
            parameters=[
                ToolParameter(
                    name="query",
                    type="string",
                    description="The sub-problem to reason about.",
                ),
                ToolParameter(
                    name="context",
                    type="string",
                    description="Supporting context for reasoning.",
                    required=False,
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        from aidlearning.tools.builtin.reason import reason

        result = await reason(
            query=kwargs.get("query", ""),
            context=kwargs.get("context", ""),
            api_key=kwargs.get("api_key"),
            base_url=kwargs.get("base_url"),
            model=kwargs.get("model"),
            max_tokens=kwargs.get("max_tokens"),
            temperature=kwargs.get("temperature"),
        )
        return ToolResult(content=result.get("answer", ""), metadata=result)


class PaperSearchToolWrapper(_PromptHintsMixin, BaseTool):
    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="paper_search",
            description="Search arXiv preprints by keyword and return concise metadata.",
            parameters=[
                ToolParameter(name="query", type="string", description="Search query."),
                ToolParameter(
                    name="max_results",
                    type="integer",
                    description="Maximum papers to return.",
                    required=False,
                    default=3,
                ),
                ToolParameter(
                    name="years_limit",
                    type="integer",
                    description="Only include preprints from the last N years.",
                    required=False,
                    default=3,
                ),
                ToolParameter(
                    name="sort_by",
                    type="string",
                    description="Sort by relevance or submission date.",
                    required=False,
                    default="relevance",
                    enum=["relevance", "date"],
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        from aidlearning.tools.builtin.paper_search_tool import ArxivSearchTool

        try:
            papers = await ArxivSearchTool().search_papers(
                query=kwargs.get("query", ""),
                max_results=kwargs.get("max_results", 3),
                years_limit=kwargs.get("years_limit", 3),
                sort_by=kwargs.get("sort_by", "relevance"),
            )
        except Exception:
            return ToolResult(
                content="arXiv search is temporarily unavailable (rate-limited or network error). Please try again later.",
                sources=[],
                metadata={"provider": "arxiv", "papers": [], "error": True},
            )
        if not papers:
            return ToolResult(
                content="No arXiv preprints found for this query.",
                sources=[],
                metadata={"provider": "arxiv", "papers": []},
            )

        lines: list[str] = []
        for paper in papers:
            lines.append(f"**{paper['title']}** ({paper.get('year', '?')})")
            lines.append(f"Authors: {', '.join(paper.get('authors', []))}")
            lines.append(f"arXiv: {paper.get('arxiv_id', '')}")
            lines.append(f"URL: {paper.get('url', '')}")
            lines.append(f"Abstract: {paper.get('abstract', '')[:400]}")
            lines.append("")

        return ToolResult(
            content="\n".join(lines),
            sources=[
                {
                    "type": "paper",
                    "provider": "arxiv",
                    "url": paper.get("url", ""),
                    "title": paper.get("title", ""),
                    "arxiv_id": paper.get("arxiv_id", ""),
                }
                for paper in papers
            ],
            metadata={"provider": "arxiv", "papers": papers},
        )


class ReadSourceTool(_PromptHintsMixin, BaseTool):
    """通过清单 ID 加载附加的 Space 源的完整文本。

    当轮次有任何非图片的附加源（笔记本记录、书籍引用、历史会话、题库条目或文档附件）时，
    聊天管道会自动启用此工具。每轮的完整文本载荷以 ``{source_id: str}`` 的形式
    携带在 ``context.metadata["source_index"]`` 中，由 ``_augment_tool_kwargs``
    注入到工具调用中。工具本身保持无状态。
    """

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="read_source",
            description=(
                "Load the full text of one attached source by id. Use ONLY when "
                "the preview shown in the Attached Sources manifest is "
                "insufficient to answer the user's question. The id must be "
                "copied verbatim from the manifest — do not invent ids. Do not "
                "call this on every source 'just in case'."
            ),
            parameters=[
                ToolParameter(
                    name="source_id",
                    type="string",
                    description=(
                        "The source identifier from the Attached Sources "
                        "manifest. Begins with one of: nb- (notebook record), "
                        "bk- (book reference), hs- (history session), qb- "
                        "(question-bank entry), at- (document attachment)."
                    ),
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        source_id = str(kwargs.get("source_id") or "").strip()
        if not source_id:
            return ToolResult(
                content="Error: source_id is required.",
                success=False,
            )
        source_index = kwargs.get("source_index")
        if not isinstance(source_index, dict) or not source_index:
            return ToolResult(
                content=("Error: no attached sources are available for this turn."),
                success=False,
            )
        full_text = source_index.get(source_id)
        if not full_text:
            available = ", ".join(sorted(source_index.keys()))
            return ToolResult(
                content=(
                    f"Error: unknown source_id {source_id!r}. "
                    f"Valid ids for this turn: {available or '(none)'}."
                ),
                success=False,
            )
        return ToolResult(
            content=str(full_text),
            metadata={"source_id": source_id, "char_count": len(str(full_text))},
        )


class ReadMemoryTool(_PromptHintsMixin, BaseTool):
    """读取当前用户的记忆，支持可选的语义搜索。

    不带查询时，返回完整的 L3 拼接内容（向后兼容）。
    带查询时，在中期（SQLite）和长期（L2/L3 Markdown）记忆中执行语义搜索。
    """

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="read_memory",
            description=(
                "Read the user's persistent memory: recent learning summary, "
                "user profile, knowledge scope, and explicit preferences. "
                "Optionally pass a query to search for relevant memories "
                "semantically. Without a query, returns all memory."
            ),
            parameters=[
                ToolParameter(
                    name="query",
                    type="string",
                    description="Optional search query for relevant memory entries.",
                    required=False,
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        from aidlearning.memory import get_memory_store

        query = str(kwargs.get("query") or "").strip()
        store = get_memory_store()

        if query:
            text = await store.retrieve_memory(query=query)
        else:
            text = store.read_l3_concat()

        return ToolResult(
            content=text,
            metadata={"char_count": len(text)},
        )


class WriteMemoryTool(_PromptHintsMixin, BaseTool):
    """将明确的用户偏好持久化到 L3 ``preferences.md``。

    聊天模式下唯一写入记忆的工具。其他记忆文档由用户通过记忆工作台手动更新。
    此工具用于用户*明确*表达偏好的场景 —— 仅在自然时复述给用户，
    然后用实质内容调用此工具。
    """

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="write_memory",
            description=(
                "Save an explicit user preference (writing style, language "
                "choice, depth, format) to long-term memory. Call ONLY when "
                "the user clearly states a preference — never speculate."
            ),
            parameters=[
                ToolParameter(
                    name="op",
                    type="string",
                    description="`add` for a new preference, `edit` to revise an existing one.",
                    enum=["add", "edit"],
                    required=True,
                ),
                ToolParameter(
                    name="text",
                    type="string",
                    description="The preference, in the user's own words where possible. ≤ 240 chars.",
                    required=True,
                ),
                ToolParameter(
                    name="target_id",
                    type="string",
                    description="Existing entry id (form `m_xxx`). Required for `edit`.",
                    required=False,
                ),
                ToolParameter(
                    name="reason",
                    type="string",
                    description="Optional one-line note shown in the Memory workbench.",
                    required=False,
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        from aidlearning.memory import get_memory_store
        from aidlearning.memory.shared.trace import TraceEvent

        op = str(kwargs.get("op") or "").strip().lower()
        text = str(kwargs.get("text") or "").strip()
        target_id = kwargs.get("target_id")
        reason = kwargs.get("reason")

        if op not in {"add", "edit"}:
            return ToolResult(
                content=f"Error: op must be 'add' or 'edit', got {op!r}.", success=False
            )
        if not text:
            return ToolResult(
                content="Error: text is required and must be non-empty.", success=False
            )

        store = get_memory_store()
        # Emit an L1 trace so the preference's footnote points at a real event.
        event = TraceEvent.new(
            "chat",
            "preference_stated",
            {"op": op, "text": text, "target_id": target_id, "reason": reason},
        )
        await store.emit(event)

        report = await store.write_preference(
            op=op,  # type: ignore[arg-type]
            text=text,
            target_id=str(target_id).strip() if target_id else None,
            reason=str(reason).strip() if reason else None,
            trace_id=event.id,
        )
        if not report.accepted:
            return ToolResult(
                content=f"write_memory rejected: {report.reason}",
                success=False,
                metadata={"op": op},
            )
        entry_id = report.results[0].entry_id if report.results else None
        return ToolResult(
            content=f"preference {op}ed (entry={entry_id or target_id}).",
            metadata={"op": op, "entry_id": entry_id or target_id},
        )


class WebFetchTool(_PromptHintsMixin, BaseTool):
    """获取特定 URL 并返回可读的 Markdown。

    实际的获取/提取/安全逻辑位于 ``aidlearning.tools.web_fetch`` 中，
    使此包装器不包含网络代码 —— 更容易对 BaseTool 样板进行单元测试，
    无需启动 httpx 模拟。
    """

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="web_fetch",
            description=(
                "Fetch a specific URL and extract readable content as "
                "markdown. Use this when the user shares a specific link; "
                "use `web_search` for general topic searches."
            ),
            parameters=[
                ToolParameter(
                    name="url",
                    type="string",
                    description="Full http:// or https:// URL.",
                ),
                ToolParameter(
                    name="max_chars",
                    type="integer",
                    description="Cap on the extracted text length; defaults to 50000.",
                    required=False,
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        from aidlearning.tools.builtin.web_fetch import (
            DEFAULT_MAX_CHARS,
            fetch_url_as_markdown,
        )

        url = str(kwargs.get("url") or "").strip()
        if not url:
            return ToolResult(content="Error: url is required.", success=False)
        try:
            max_chars = int(kwargs.get("max_chars") or DEFAULT_MAX_CHARS)
        except (TypeError, ValueError):
            max_chars = DEFAULT_MAX_CHARS
        outcome = await fetch_url_as_markdown(url, max_chars=max_chars)
        if not outcome.ok:
            return ToolResult(
                content=outcome.error or "Fetch failed.",
                success=False,
                metadata={"url": url},
            )
        return ToolResult(
            content=outcome.markdown,
            sources=[{"type": "web", "url": outcome.url, "title": outcome.title}],
            metadata={
                "url": outcome.url,
                "title": outcome.title,
                "char_count": len(outcome.markdown),
                "truncated": outcome.truncated,
            },
        )


class GithubTool(_PromptHintsMixin, BaseTool):
    """通过 `gh` 进行只读 GitHub 查询。始终自动挂载；
    当服务器未安装 CLI 时，底层调用会优雅地报告"gh 不可用"。"""

    _ALLOWED_QUERY_TYPES = ("pr", "issue", "run", "repo", "api")

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="github",
            description=(
                "Read-only queries against GitHub PRs / issues / repos / "
                "CI runs via the gh CLI. This tool cannot write — no "
                "comments, no closes, no merges."
            ),
            parameters=[
                ToolParameter(
                    name="query_type",
                    type="string",
                    description=("One of 'pr', 'issue', 'run', 'repo', 'api'."),
                    enum=list(_ALLOWED_QUERY_TYPES := ("pr", "issue", "run", "repo", "api")),
                ),
                ToolParameter(
                    name="target",
                    type="string",
                    description=(
                        "owner/repo[#number] or full URL for pr/issue; "
                        "owner/repo for run/repo; gh-api relative path "
                        "for api."
                    ),
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        from aidlearning.tools.builtin.github_query import run_github_query

        outcome = await run_github_query(
            query_type=str(kwargs.get("query_type") or ""),
            target=str(kwargs.get("target") or ""),
        )
        if not outcome.ok:
            return ToolResult(
                content=outcome.error,
                success=False,
                metadata={"query_type": outcome.query_type, "target": outcome.target},
            )
        return ToolResult(
            content=outcome.output,
            sources=[
                {
                    "type": "github",
                    "query_type": outcome.query_type,
                    "target": outcome.target,
                }
            ],
            metadata={
                "query_type": outcome.query_type,
                "target": outcome.target,
            },
        )


class AskUserTool(_PromptHintsMixin, BaseTool):
    """在循环中途暂停轮次以向用户提出澄清问题。

    返回携带结构化问题载荷的 ``pause_for_user``。
    聊天管道在此调用后暂停智能体循环，将问题+选项作为卡片显示在聊天 UI 中，
    并**等待同一轮次中的用户回复**。当回复到达时，循环恢复，
    用户的答案被替换到此工具的结果体中 —— 因此后续迭代会看到
    "User answered: <text>" 作为匹配的 ``role=tool`` 内容并可以据此行动。
    用户也可以随时通过编辑器的停止按钮中止等待（取消整个轮次）。
    """

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="ask_user",
            description=(
                "Pause the conversation to ask the user 1-3 clarifying "
                "questions in one batch. The frontend renders all "
                "questions on a single card with tabs the user can "
                "switch between; the user answers each, then submits "
                "once. The turn does NOT end — when the answers arrive "
                "the agentic loop resumes with them as this tool's "
                "result. Use sparingly: only when intent is genuinely "
                "ambiguous and progress without clarification is unsafe."
            ),
            parameters=[
                ToolParameter(
                    name="questions",
                    type="array",
                    description=(
                        "1-3 questions to ask in one card. Each item: "
                        "{prompt: 'question text', options?: ['A','B'], "
                        "id?: 'stable-id', allow_free_text?: true, "
                        "placeholder?: 'hint for free input'}. Each "
                        "question may have its own option chips; the "
                        "user can also type freely."
                    ),
                    required=False,
                    items={
                        "type": "object",
                        "properties": {
                            "prompt": {"type": "string"},
                            "options": {"type": "array", "items": {"type": "string"}},
                            "id": {"type": "string"},
                            "allow_free_text": {"type": "boolean"},
                            "placeholder": {"type": "string"},
                        },
                    },
                ),
                ToolParameter(
                    name="intro",
                    type="string",
                    description=(
                        "Optional one-line lead-in shown above the "
                        "questions (e.g. 'To tailor the research, please "
                        "answer:')."
                    ),
                    required=False,
                ),
                # Legacy single-question shape — still accepted; the tool
                # auto-wraps it into a one-element ``questions`` list so
                # older prompts keep working unchanged.
                ToolParameter(
                    name="question",
                    type="string",
                    description=(
                        "Legacy single-question shorthand. Prefer "
                        "``questions``. If supplied alone, wrapped into "
                        "one question with ``options``."
                    ),
                    required=False,
                ),
                ToolParameter(
                    name="options",
                    type="array",
                    description=(
                        "Legacy option list paired with ``question``. "
                        "Ignored when ``questions`` is provided."
                    ),
                    required=False,
                    items={"type": "string"},
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        from aidlearning.tools.builtin.ask_user import build_ask_user_payload

        payload, err = build_ask_user_payload(
            questions=kwargs.get("questions"),
            intro=kwargs.get("intro"),
            question=kwargs.get("question"),
            options=kwargs.get("options"),
        )
        if payload is None:
            return ToolResult(content=err or "Invalid ask_user arguments.", success=False)

        payload_dict = payload.to_dict()
        prompts = ", ".join(q.prompt for q in payload.questions)
        return ToolResult(
            # The placeholder content is overwritten by the pipeline
            # once the user's reply arrives; the model never sees this
            # literal string on a normal flow. It only surfaces if the
            # runtime crashes mid-pause (in which case the LLM at least
            # gets a coherent log entry).
            content=f"[awaiting user reply to: {prompts}]",
            metadata={"ask_user": payload_dict},
            pause_for_user=payload_dict,
        )


class SessionSearchTool(_PromptHintsMixin, BaseTool):
    """搜索过去的对话历史（中期记忆）。

    使用 SQLite FTS5 全文搜索查找来自先前会话的相关消息。
    支持关键词搜索和可选的时间过滤。
    这是"我们上周讨论了什么？"类型查询的主要工具。
    """

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="session_search",
            description=(
                "Search past conversation history for relevant discussions. "
                "Use this when the user asks about something they talked about "
                "before, like 'what did we discuss last week' or 'find the "
                "conversation about limit definitions'. Returns matching "
                "messages with session titles and timestamps."
            ),
            parameters=[
                ToolParameter(
                    name="query",
                    type="string",
                    description="Search keywords. Multiple words are OR-matched.",
                    required=True,
                ),
                ToolParameter(
                    name="days",
                    type="integer",
                    description="Only search messages from the last N days. Omit for all time.",
                    required=False,
                ),
                ToolParameter(
                    name="session_id",
                    type="string",
                    description="Restrict search to a specific session ID.",
                    required=False,
                ),
                ToolParameter(
                    name="limit",
                    type="integer",
                    description="Max results to return. Default 20.",
                    required=False,
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        import time as _time
        from datetime import timedelta

        from aidlearning.services.session.sqlite_store import get_sqlite_session_store

        query = str(kwargs.get("query") or "").strip()
        if not query:
            return ToolResult(content="Error: query is required.", success=False)

        days = kwargs.get("days")
        session_id = kwargs.get("session_id")
        limit = int(kwargs.get("limit") or 20)

        since: float | None = None
        if days:
            since = (_time.time() - timedelta(days=int(days)).total_seconds())

        store = get_sqlite_session_store()
        results = await store.search_messages(
            query,
            session_id=session_id,
            since=since,
            limit=limit,
        )

        if not results:
            return ToolResult(
                content=f"No messages found matching '{query}'.",
                metadata={"query": query, "count": 0},
            )

        # Format results as readable markdown
        lines: list[str] = [f"Found {len(results)} messages matching '{query}':\n"]
        from datetime import datetime, timezone

        for r in results:
            ts = datetime.fromtimestamp(r["created_at"], tz=timezone.utc)
            date_str = ts.strftime("%Y-%m-%d %H:%M")
            session_title = r.get("session_title") or r["session_id"]
            role = r["role"].capitalize()
            content = r["content"][:200] + ("..." if len(r["content"]) > 200 else "")
            lines.append(
                f"[{date_str}] **{session_title}** — {role}: {content}"
            )

        return ToolResult(
            content="\n".join(lines),
            metadata={"query": query, "count": len(results)},
        )


BUILTIN_TOOL_TYPES: tuple[type[BaseTool], ...] = (
    BrainstormTool,
    RAGTool,
    WebSearchTool,
    CodeExecutionTool,
    ReasonTool,
    PaperSearchToolWrapper,
    ReadSourceTool,
    ReadMemoryTool,
    WriteMemoryTool,
    WebFetchTool,
    GithubTool,
    AskUserTool,
    SessionSearchTool,
)

# Tools whose implementation is parked while we redesign them. NOT loaded
# into the runtime registry — the chat agent cannot invoke these — but the
# settings page surfaces them with a "Coming soon" badge so users see the
# capability is on the roadmap. Re-add to ``BUILTIN_TOOL_TYPES`` when ready
# to ship.
COMING_SOON_TOOL_TYPES: tuple[type[BaseTool], ...] = ()

BUILTIN_TOOL_NAMES: tuple[str, ...] = tuple(tool_type().name for tool_type in BUILTIN_TOOL_TYPES)

COMING_SOON_TOOL_NAMES: tuple[str, ...] = tuple(
    tool_type().name for tool_type in COMING_SOON_TOOL_TYPES
)

# Tools the user can switch on/off from /settings/tools ("体验增强" /
# Experience Enhancement). Everything else in BUILTIN_TOOL_NAMES is mounted
# automatically by the chat pipeline under per-tool context gates and is
# locked-on from the user's perspective. Ordering here is the canonical
# display order for the settings page.
USER_TOGGLEABLE_TOOL_NAMES: tuple[str, ...] = (
    "brainstorm",
    "web_search",
    "paper_search",
    "code_execution",
    "reason",
)

TOOL_ALIASES: dict[str, tuple[str, dict[str, Any]]] = {
    "rag_hybrid": ("rag", {"mode": "hybrid"}),
    "rag_naive": ("rag", {"mode": "naive"}),
    "rag_search": ("rag", {}),
    "code_execute": ("code_execution", {}),
    "run_code": ("code_execution", {}),
}

__all__ = [
    "BUILTIN_TOOL_NAMES",
    "BUILTIN_TOOL_TYPES",
    "COMING_SOON_TOOL_NAMES",
    "COMING_SOON_TOOL_TYPES",
    "TOOL_ALIASES",
    "USER_TOGGLEABLE_TOOL_NAMES",
    "AskUserTool",
    "BrainstormTool",
    "CodeExecutionTool",
    "GithubTool",
    "PaperSearchToolWrapper",
    "RAGTool",
    "ReadMemoryTool",
    "ReadSourceTool",
    "ReasonTool",
    "SessionSearchTool",
    "WebFetchTool",
    "WebSearchTool",
    "WriteMemoryTool",
]
