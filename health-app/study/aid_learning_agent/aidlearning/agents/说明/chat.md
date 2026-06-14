用户消息 (WebSocket)
    │
    ▼
┌─ API 层 ─────────────────────────────────────────────┐
│  api/routers/chat.py          ← WebSocket 入口        │
│    ├─ api/routers/auth.py     ← WebSocket 鉴权        │
│    ├─ services/llm/config.py  ← 读取 LLM 配置         │
│    └─ agents/chat/session_manager.py ← 会话管理        │
│         └─ services/session/base_session_manager.py    │
│              └─ services/path_service.py (JSON 持久化)  │
└───────────────────────────────────────────────────────┘
    │
    ▼
┌─ Agent 层 ────────────────────────────────────────────┐
│  agents/chat/chat_agent.py    ← ChatAgent.process()   │
│    │                                                   │
│    ├─ 1. truncate_history()   ← 截断历史（tiktoken）    │
│    │                                                   │
│    ├─ 2. retrieve_context()   ← 检索上下文              │
│    │    ├─ tools/rag_tool.py  ← RAG 检索               │
│    │    │    └─ services/rag/service.py                 │
│    │    │         └─ services/rag/pipelines/llamaindex/ │
│    │    └─ tools/web_search.py ← 联网搜索               │
│    │         └─ services/search/providers/*.py          │
│    │              (tavily/brave/bing/duckduckgo/...)    │
│    │                                                   │
│    ├─ 3. build_messages()     ← 组装 prompt             │
│    │    ├─ agents/chat/prompts/{zh,en}/chat_agent.yaml  │
│    │    └─ services/prompt/language.py ← 语言指令       │
│    │                                                   │
│    └─ 4. generate_stream()    ← 流式调用 LLM            │
│         └─ agents/base_agent.py ← BaseAgent.stream_llm()│
└───────────────────────────────────────────────────────┘
    │
    ▼
┌─ LLM 服务层 ──────────────────────────────────────────┐
│  services/llm/factory.py      ← factory.stream()       │
│    ├─ services/llm/config.py  ← LLMConfig 解析         │
│    ├─ services/provider_registry.py ← Provider 查找     │
│    ├─ services/llm/provider_factory.py ← 运行时 Provider│
│    │                                                   │
│    ├─→ [云端] services/llm/cloud_provider.py            │
│    │    └─ services/llm/provider_core/                  │
│    │         ├─ openai_compat_provider.py (OpenAI/兼容) │
│    │         ├─ anthropic_provider.py                   │
│    │         ├─ azure_openai_provider.py                │
│    │         └─ github_copilot_provider.py              │
│    │                                                   │
│    └─→ [本地] services/llm/local_provider.py            │
│         └─ (Ollama / vLLM / LM Studio)                 │
│                                                       │
│  services/llm/capabilities.py ← 能力检测（vision/tools）│
│  services/llm/multimodal.py   ← 图片处理（如有附件）     │
│  services/llm/error_mapping.py← 错误映射                │
└───────────────────────────────────────────────────────┘
    │
    ▼
┌─ 流式返回 ────────────────────────────────────────────┐
│  factory.py stream 产生 chunk                          │
│    ↓                                                   │
│  base_agent.py stream_llm 逐 chunk yield               │
│    ↓                                                   │
│  chat_agent.py generate_stream → stream_generator      │
│    ↓                                                   │
│  chat.py websocket 逐 chunk 发送 {"type":"stream"}     │
│    ↓                                                   │
│  最终发送 {"type":"result", "content": full_response}  │
│    +  {"type":"sources", ...} （如有 RAG/Web 来源）     │
│                                                       │
│  agents/chat/session_manager.py ← 保存 assistant 消息   │
│  logging/LLMStats ← Token 统计                         │
└───────────────────────────────────────────────────────┘





前端 (unified-ws.ts)
    │  type: "message" / "start_turn"
    │  携带: capability, tools, knowledge_bases, attachments,
    │        notebook_references, history_references, book_references,
    │        skills, memory_references, llm_selection, config ...
    ▼
┌─ API 层 ──────────────────────────────────────────────────────┐
│  api/routers/unified_ws.py        ← /ws 统一 WebSocket 入口    │
│    └─ runtime.start_turn(msg)     ← 创建 Turn，启动后台任务     │
└───────────────────────────────────────────────────────────────┘
    │
    ▼
┌─ Turn 运行时 ─────────────────────────────────────────────────┐
│  services/session/turn_runtime.py                              │
│    TurnRuntimeManager._run_turn()                              │
│      │                                                         │
│      ├─ 1. 解析 payload（capability, tools, attachments, ...） │
│      ├─ 2. 模型选择（LLMSelection → apply_llm_selection）      │
│      ├─ 3. 附件处理（base64 → attachment_store → 文档提取）     │
│      ├─ 4. 上下文构建                                           │
│      │    ├─ ContextBuilder.build()     ← 对话历史 + 压缩摘要   │
│      │    ├─ NotebookAnalysisAgent      ← Notebook 引用分析     │
│      │    ├─ build_book_context()       ← Book 章节引用         │
│      │    ├─ _build_question_bank_context() ← 题库引用          │
│      │    ├─ memory_store.read_l3_concat()  ← Memory 记忆       │
│      │    ├─ SkillService.load_for_context()← Skills 技能       │
│      │    └─ build_inventory() / render_manifest() ← 来源清单   │
│      ├─ 5. 组装 UnifiedContext                                  │
│      └─ 6. ChatOrchestrator.handle(context)                    │
└───────────────────────────────────────────────────────────────┘
    │
    ▼
┌─ 编排器 ──────────────────────────────────────────────────────┐
│  runtime/orchestrator.py                                       │
│    ChatOrchestrator.handle()                                   │
│      └─ capability_registry.get(cap_name)                      │
│         └─ capability.run(context, bus)  ← 路由到具体 Capability│
└───────────────────────────────────────────────────────────────┘
    │
    ▼
┌─ 5 种 Capability ─────────────────────────────────────────────┐
│                                                                │
│  [chat]     → agents/chat/       → ChatAgent + 工具调用循环     │
│  [deep_solve] → agents/solve/    → SolveAgent（多步推理）       │
│  [deep_question] → agents/question/ → QuestionAgent（出题）    │
│  [deep_research] → agents/research/ → ResearchAgent（深度研究） │
│  [visualize] → agents/visualize/ → VisualizeAgent（图表/动画）  │
│                                                                │
│  每个 Capability 内部可调用工具：                                │
│    tool_registry.execute("web_search")                         │
│    tool_registry.execute("code_execution")                     │
│    tool_registry.execute("brainstorm")                         │
│    tool_registry.execute("reason")                             │
│    tool_registry.execute("paper_search")                       │
│    tool_registry.execute("geogebra_analysis")                  │
│    tool_registry.execute("rag")                                │
│    tool_registry.execute("write_note")                         │
│    tool_registry.execute("read_source")                        │
│    tool_registry.execute("ask_user")   ← 暂停等待用户回复       │
│    ...                                                         │
└───────────────────────────────────────────────────────────────┘
    │
    ▼
┌─ 流式事件返回 ────────────────────────────────────────────────┐
│  StreamEvent 通过 StreamBus → TurnRuntimeManager               │
│    → _publish_live_event() → subscriber.queue                  │
│      → unified_ws.py safe_send() → WebSocket                   │
│                                                                │
│  事件类型：                                                     │
│    session / session_meta  — 会话 ID / 自动生成标题             │
│    stage_start / stage_end — 阶段开始/结束                      │
│    thinking                — 思考过程（CoT）                    │
│    content                 — 流式文本                           │
│    tool_call / tool_result — 工具调用/结果                      │
│    progress                — 进度更新                          │
│    sources                 — 检索来源                           │
│    result                  — 最终结果                           │
│    error / done            — 错误/完成                          │
└───────────────────────────────────────────────────────────────┘
