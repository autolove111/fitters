#!/usr/bin/env python
"""
ChatAgent — 对话 Agent（轻量级多轮对话）

【调用链路位置】chat.py → ChatAgent.process()

核心流程：
  1. truncate_history()  — 截断历史消息（token 限制）
  2. retrieve_context()  — 可选：RAG 知识库检索 / 联网搜索
  3. build_messages()    — 组装 system prompt + 历史 + 当前消息
  4. generate_stream()   — 流式调用 LLM（通过 BaseAgent.stream_llm()）

返回值：AsyncGenerator，逐 chunk 返回 {"type": "chunk", "content": "..."} 和最终 {"type": "complete", ...}
"""

from typing import Any, AsyncGenerator

from deeptutor.agents.base_agent import BaseAgent
from deeptutor.runtime.registry.tool_registry import get_tool_registry
from deeptutor.services.prompt.language import append_language_directive


class ChatAgent(BaseAgent):
    """
    对话 Agent — 继承 BaseAgent，提供多轮对话能力。

    功能：
    - 对话历史管理（token 限制截断）
    - RAG 知识库检索增强
    - 联网搜索增强
    - 流式响应生成（通过 BaseAgent.stream_llm()）
    """

    # 历史消息的默认 token 上限
    DEFAULT_MAX_HISTORY_TOKENS = 4000

    def __init__(
        self,
        language: str = "zh",
        config: dict[str, Any] | None = None,
        max_history_tokens: int | None = None,
        **kwargs,
    ):
        """
        初始化 ChatAgent。

        流程：
          1. 调用 BaseAgent.__init__() 加载 LLM 配置、Prompt 模板
          2. 设置历史消息 token 上限
          3. 获取工具注册表（用于 RAG/搜索等工具调用）

        Args:
            language: 语言设置（'zh' | 'en'），影响 prompt 加载和语言指令
            config: 可选配置字典
            max_history_tokens: 历史消息最大 token 数
            **kwargs: 传递给 BaseAgent 的额外参数（api_key, base_url 等）
        """
        super().__init__(
            module_name="chat",
            agent_name="chat_agent",
            language=language,
            config=config,
            **kwargs,
        )

        # 设置历史 token 上限：优先用传入值 → 配置文件值 → 默认值
        self.max_history_tokens = max_history_tokens or self.agent_config.get(
            "max_history_tokens", self.DEFAULT_MAX_HISTORY_TOKENS
        )
        self._tool_registry = get_tool_registry()

        self.logger.info(f"ChatAgent initialized: model={self.model}, base_url={self.base_url}")

    def count_tokens(self, text: str) -> int:
        """
        统计文本的 token 数量。

        优先使用 tiktoken（cl100k_base 编码，适用于 GPT-4/GPT-3.5），
        不可用时回退到粗略估算（每 4 个字符 ≈ 1 个 token）。

        Args:
            text: 待统计的文本

        Returns:
            估算的 token 数量
        """
        try:
            import tiktoken

            encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))
        except ImportError:
            return len(text) // 4

    def truncate_history(
        self,
        history: list[dict[str, str]],
        max_tokens: int | None = None,
    ) -> list[dict[str, str]]:
        """
        截断对话历史，使其总 token 数不超过上限。

        策略：从最新消息向前累加 token，超过上限时丢弃最早的消息。
        保证最近的对话上下文优先保留。

        Args:
            history: 消息列表，每条包含 'role' 和 'content'
            max_tokens: token 上限（默认使用 self.max_history_tokens）

        Returns:
            截断后的消息列表
        """
        max_tokens = max_tokens or self.max_history_tokens

        if not history:
            return []

        # 统计每条消息的 token 数
        message_tokens = []
        for msg in history:
            content = msg.get("content", "")
            tokens = self.count_tokens(content)
            message_tokens.append((msg, tokens))

        # 从最新消息向前累加，超过上限时停止
        truncated = []
        total_tokens = 0

        for msg, tokens in reversed(message_tokens):
            if total_tokens + tokens > max_tokens:
                break
            truncated.insert(0, msg)
            total_tokens += tokens

        if len(truncated) < len(history):
            self.logger.info(
                f"Truncated history from {len(history)} to {len(truncated)} messages "
                f"({total_tokens} tokens)"
            )

        return truncated

    def format_history_for_prompt(self, history: list[dict[str, str]]) -> str:
        """
        将对话历史格式化为字符串（用于拼接到 prompt 中）。

        格式：每条消息一行，前缀为 "User:" 或 "Assistant:"，
        消息之间用空行分隔。

        Args:
            history: 消息列表

        Returns:
            格式化后的历史字符串
        """
        if not history:
            return ""

        lines = []
        for msg in history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            prefix = "User" if role == "user" else "Assistant"
            lines.append(f"{prefix}: {content}")

        return "\n\n".join(lines)

    async def retrieve_context(
        self,
        message: str,
        kb_name: str | None = None,
        enable_rag: bool = False,
        enable_web_search: bool = False,
    ) -> tuple[str, dict[str, Any]]:
        """
        检索上下文 — 可选的 RAG 知识库检索和联网搜索。

        通过 tool_registry 执行 "rag" 或 "web_search" 工具，
        将检索结果拼接为 context 字符串，连同来源信息一起返回。
        检索失败不会中断流程，仅记录 warning 日志。

        Args:
            message: 用户消息（作为检索查询）
            kb_name: 知识库名称（RAG 时必填）
            enable_rag: 是否启用 RAG 检索
            enable_web_search: 是否启用联网搜索

        Returns:
            (context字符串, sources字典)
            context 拼接了所有检索结果，sources 记录来源信息用于前端展示
        """
        context_parts = []
        sources = {"rag": [], "web": []}

        # RAG 检索：从知识库中检索相关内容
        if enable_rag and kb_name:
            try:
                self.logger.info(f"RAG search: {message[:50]}...")
                rag_result = await self._tool_registry.execute(
                    "rag",
                    query=message,
                    kb_name=kb_name,
                    mode="hybrid",
                )
                rag_answer = rag_result.content
                if rag_answer:
                    context_parts.append(f"[Knowledge Base: {kb_name}]\n{rag_answer}")
                    sources["rag"].append(
                        {
                            "kb_name": kb_name,
                            "content": rag_answer[:500] + "..."
                            if len(rag_answer) > 500
                            else rag_answer,
                        }
                    )
                    self.logger.info(f"RAG retrieved {len(rag_answer)} chars")
            except Exception as e:
                self.logger.warning(f"RAG search failed: {e}")

        # 联网搜索：从互联网搜索相关信息
        if enable_web_search:
            try:
                self.logger.info(f"Web search: {message[:50]}...")
                web_result = await self._tool_registry.execute(
                    "web_search",
                    query=message,
                    verbose=False,
                )
                web_answer = web_result.content
                web_citations = web_result.sources

                if web_answer:
                    context_parts.append(f"[Web Search Results]\n{web_answer}")
                    sources["web"] = web_citations[:5]
                    self.logger.info(
                        f"Web search returned {len(web_answer)} chars, "
                        f"{len(web_citations)} citations"
                    )
            except Exception as e:
                self.logger.warning(f"Web search failed: {e}")

        context = "\n\n".join(context_parts)
        return context, sources

    def build_messages(
        self,
        message: str,
        history: list[dict[str, str]],
        context: str = "",
    ) -> list[dict[str, str]]:
        """
        组装 LLM 请求的 messages 数组。

        结构：[system_prompt + 语言指令 + 检索上下文, ...历史消息..., 当前用户消息]

        Args:
            message: 当前用户消息
            history: 截断后的对话历史
            context: 检索到的上下文（RAG/搜索结果）

        Returns:
            符合 OpenAI API 格式的 messages 列表
        """
        messages = []

        # 构建 system prompt：基础 prompt + 语言指令 + 检索上下文
        system_parts = [
            append_language_directive(
                self.get_prompt("system", "You are a helpful AI assistant."),
                self.language,
            )
        ]
        if context:
            context_template = self.get_prompt("context_template", "Reference context:\n{context}")
            system_parts.append(context_template.format(context=context))
        messages.append({"role": "system", "content": "\n\n".join(system_parts)})

        # 添加对话历史
        for msg in history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in ("user", "assistant"):
                messages.append({"role": role, "content": content})

        # 添加当前用户消息
        messages.append({"role": "user", "content": message})

        return messages

    async def generate_stream(
        self,
        messages: list[dict[str, Any]],
        attachments: list[Any] | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        流式生成回复 — 调用 BaseAgent.stream_llm()。

        从 messages 中提取 system_prompt 和 user_prompt，
        然后调用 stream_llm() 进行流式 LLM 调用。
        stream_llm() 内部调用 factory.stream()，再路由到具体 Provider。

        Args:
            messages: 组装好的 messages 数组
            attachments: 可选的图片/文件附件（多模态输入）

        Yields:
            响应文本片段（逐 chunk）
        """
        # 从 messages 中提取 system prompt
        system_prompt = ""
        user_prompt = ""
        for msg in messages:
            if msg.get("role") == "system":
                system_prompt = msg.get("content", "")
                break

        # 提取最后一条用户消息
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                user_prompt = content if isinstance(content, str) else str(content)
                break

        # 调用 BaseAgent.stream_llm()，逐 chunk yield
        async for chunk in self.stream_llm(
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            messages=messages,
            stage="chat_stream",
            attachments=attachments,
        ):
            yield chunk

    async def generate(self, messages: list[dict[str, str]]) -> str:
        """
        非流式生成回复 — 等待完整响应返回。

        内部使用 llm_stream() 收集所有 chunk 后拼接为完整字符串。
        调用 _track_tokens() 记录 token 用量。

        Args:
            messages: 组装好的 messages 数组

        Returns:
            完整的响应文本
        """
        # 从 messages 中提取 system prompt
        system_prompt = ""
        user_prompt = ""
        for msg in messages:
            if msg.get("role") == "system":
                system_prompt = msg.get("content", "")
                break

        # 提取最后一条用户消息
        for msg in reversed(messages):
            if msg.get("role") == "user":
                user_prompt = msg.get("content", "")
                break

        from deeptutor.services.llm import stream as llm_stream

        # 通过流式接口收集所有 chunk
        _chunks: list[str] = []
        async for _c in llm_stream(
            prompt=user_prompt,
            system_prompt=system_prompt,
            model=self.get_model(),
            api_key=self.api_key,
            base_url=self.base_url,
            messages=messages,
            temperature=self.get_temperature(),
        ):
            _chunks.append(_c)
        response = "".join(_chunks)

        # 记录 token 用量
        self._track_tokens(
            model=self.get_model(),
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response=response,
            stage="chat",
        )

        return response

    async def process(
        self,
        message: str,
        history: list[dict[str, str]] | None = None,
        kb_name: str | None = None,
        enable_rag: bool = False,
        enable_web_search: bool = False,
        stream: bool = False,
        attachments: list[Any] | None = None,
    ) -> dict[str, Any] | AsyncGenerator[dict[str, Any], None]:
        """
        【主入口】处理一条用户消息的完整流程。

        调用链：
          1. truncate_history()  — 截断历史消息（token 限制）
          2. retrieve_context()  — RAG/搜索检索上下文
          3. build_messages()    — 组装 messages 数组
          4. generate_stream()   — 流式调用 LLM

        Args:
            message: 用户消息
            history: 对话历史（会被截断）
            kb_name: 知识库名称（RAG 时使用）
            enable_rag: 是否启用 RAG 检索
            enable_web_search: 是否启用联网搜索
            stream: 是否流式返回（chat.py 中为 True）
            attachments: 图片/文件附件（多模态输入）

        Returns:
            stream=True: AsyncGenerator，逐 chunk 返回 {"type": "chunk", "content": "..."},
                         最终返回 {"type": "complete", "response": "...", "sources": {...}}
            stream=False: dict，包含 "response", "sources", "truncated_history"
        """
        history = history or []

        # 步骤1: 截断历史消息，控制 token 用量
        truncated_history = self.truncate_history(history)

        # 步骤2: 检索上下文（RAG / 联网搜索）
        context, sources = await self.retrieve_context(
            message=message,
            kb_name=kb_name,
            enable_rag=enable_rag,
            enable_web_search=enable_web_search,
        )

        # 步骤3: 组装 messages 数组
        messages = self.build_messages(
            message=message,
            history=truncated_history,
            context=context,
        )

        if stream:
            # 步骤4a: 流式返回 — 返回 AsyncGenerator
            async def stream_generator():
                full_response = ""
                async for chunk in self.generate_stream(messages, attachments=attachments):
                    full_response += chunk
                    yield {"type": "chunk", "content": chunk}

                yield {
                    "type": "complete",
                    "response": full_response,
                    "sources": sources,
                    "truncated_history": truncated_history,
                }

            return stream_generator()
        else:
            # 步骤4b: 非流式返回 — 等待完整响应
            response = await self.generate(messages)

            return {
                "response": response,
                "sources": sources,
                "truncated_history": truncated_history,
            }


__all__ = ["ChatAgent"]
