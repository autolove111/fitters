按调用顺序，从 unified_ws.py 开始一步步往里走。

第 1 步：unified_ws.py — WebSocket 入口

# 用户发消息，前端发送：
# {"type": "start_turn", "content": "什么是量子力学？", "capability": "deep_solve", "tools": [...], ...}

if msg_type in {"message", "start_turn"}:
    runtime = get_turn_runtime_manager()
    _, turn = await runtime.start_turn(msg)   # ← 进入第 2 步
    await subscribe_turn(turn["id"])           # ← 订阅事件流
这一步只做两件事：调 start_turn()，然后订阅事件。

第 2 步：turn_runtime.py → start_turn()
文件：turn_runtime.py


async def start_turn(self, payload):
    # 1. 校验 capability 配置
    validated_config = validate_capability_config(capability, raw_config)
    
    # 2. 确保 session 存在
    session = await self.store.ensure_session(payload.get("session_id"))
    
    # 3. 处理 LLM 模型选择
    llm_selection = _llm_selection_dict(raw_llm_selection)
    apply_llm_selection_to_catalog(...)  # 激活用户选的模型
    
    # 4. 创建 Turn 记录
    turn = await self.store.create_turn(session["id"], capability=capability)
    
    # 5. 启动后台任务 ← 进入第 3 步
    execution.task = asyncio.create_task(self._run_turn(execution))
    
    return session, turn
这一步是准备阶段：校验配置、选模型、创建 Turn 记录，然后启动后台任务 _run_turn()。

第 3 步：turn_runtime.py → _run_turn()
这是最核心的函数，1600 多行，做了所有上下文构建和执行。按顺序：


async def _run_turn(self, execution):
    payload = execution.payload
    
    # ── 3a. 处理附件 ──
    for item in payload.get("attachments", []):
        # base64 解码 → 存到 attachment_store → 提取文档文本
        record["url"] = await attachment_store.put(...)
    document_texts, attachment_records = extract_documents_from_records(...)
    
    # ── 3b. 构建对话历史上下文 ──           ← 调用 context_builder.py
    builder = ContextBuilder(self.store)
    history_result = await builder.build(
        session_id=session_id,
        llm_config=llm_config,
        language=payload.get("language"),
    )
    
    # ── 3c. 读取 Memory 记忆 ──
    memory_context = memory_store.read_l3_concat() if memory_references else ""
    
    # ── 3d. 加载 Skills 技能 ──
    skills_context = skill_service.load_for_context(resolved_skills)
    
    # ── 3e. 构建 Notebook/History/QuestionBank/Book 上下文 ──
    if notebook_references:
        notebook_context = await NotebookAnalysisAgent().analyze(...)
    if history_references:
        history_context = await NotebookAnalysisAgent().analyze(...)
    if question_notebook_references:
        question_bank_context = await _build_question_bank_context(...)
    book_context = build_book_context(book_references)
    
    # ── 3f. 构建来源清单 ──                ← 调用 source_inventory.py
    inventory = await build_inventory(...)
    source_manifest_text, source_index = render_manifest(inventory)
    
    # ── 3g. 组装 UnifiedContext ──
    context = UnifiedContext(
        session_id=session_id,
        user_message=effective_user_message,  # 拼接了所有上下文
        conversation_history=conversation_history,
        enabled_tools=payload.get("tools"),
        active_capability=payload.get("capability"),
        knowledge_bases=payload.get("knowledge_bases"),
        attachments=attachments,
        memory_context=memory_context,
        skills_context=skills_context,
        source_manifest=source_manifest_text,
        metadata={...},
    )
    
    # ── 3h. 调用编排器 ──                  ← 进入第 4 步
    orch = ChatOrchestrator()
    async for event in orch.handle(context):
        await self._publish_live_event(execution, event)
    
    # ── 3i. 保存 assistant 回复 ──
    await self.store.add_message(session_id, role="assistant", content=assistant_content)
    
    # ── 3j. 生成会话标题 ──
    await self._maybe_generate_session_title(...)
这一步是上下文构建阶段：把用户选的所有东西（附件、历史、Notebook、Book、Memory、Skills）拼成一个 UnifiedContext 对象。

第 4 步：orchestrator.py → ChatOrchestrator.handle()
文件：orchestrator.py


async def handle(self, context: UnifiedContext):
    # 1. 根据 capability 名称查找对应的 Capability 实现
    cap_name = context.active_capability or "chat"
    capability = self._cap_registry.get(cap_name)   # ← 查 capability_registry
    
    # 2. 创建 StreamBus（事件总线）
    bus = StreamBus()
    
    # 3. 执行 Capability                         ← 进入第 5 步
    async def _run():
        await capability.run(context, bus)         # ← 关键调用
    task = asyncio.create_task(_run())
    
    # 4. 订阅 StreamBus，逐事件 yield 给调用方
    async for event in bus.subscribe():
        yield event
这一步是路由阶段：根据 capability 名称找到对应的实现，调用它的 run() 方法。

第 5 步：capability_registry.py → 查找 Capability
文件：capability_registry.py


# 注册表里有 5 种 Capability：
#   "chat"           → agents/chat/agentic_pipeline.py
#   "deep_solve"     → agents/solve/
#   "deep_question"  → agents/question/
#   "deep_research"  → agents/research/
#   "visualize"      → agents/visualize/

capability = self._cap_registry.get("deep_solve")
# 返回 SolveCapability 实例
第 6 步：以 Chat 为例 → agentic_pipeline.py
文件：agentic_pipeline.py

Chat Capability 的 run() 方法内部是一个agentic 工具调用循环：


async def run(self, context, bus):
    # 1. 组装 system prompt（注入 Skills、Memory、来源清单等）
    system_prompt = build_system_prompt(context)
    
    # 2. 组装 messages
    messages = [{"role": "system", "content": system_prompt}, ...]
    
    # 3. 获取工具 schemas（从 tool_registry）
    tools = get_tool_schemas(context.enabled_tools)
    
    # 4. 进入 agentic 循环
    while True:
        # 调用 LLM（带工具定义）
        response = await llm_stream(messages, tools=tools)
        
        if response.has_tool_calls:
            # 执行工具调用
            for tool_call in response.tool_calls:
                result = await tool_registry.execute(tool_call.name, **tool_call.args)
                # 工具可能是：web_search / code_execution / brainstorm / ask_user 等
                messages.append(tool_result)
            continue  # 继续循环，让 LLM 看到工具结果
        
        else:
            # 没有工具调用，输出最终回复
            await bus.emit(StreamEvent(type="content", content=response.text))
            break
这一步是执行阶段：Agent 与 LLM 反复对话，需要时调用工具，直到产出最终回复。

第 7 步：tool_registry.py → 执行工具
文件：tool_registry.py


# Agent 调用工具时：
result = await tool_registry.execute("web_search", query="什么是量子力学")

# 注册表里有这些工具：
#   "rag"               → tools/rag_tool.py         → RAGService.search()
#   "web_search"        → tools/web_search.py        → services/search/
#   "code_execution"    → tools/code_executor.py      → 沙箱执行代码
#   "brainstorm"        → tools/brainstorm.py         → 头脑风暴
#   "reason"            → tools/reason.py             → 推理增强
#   "paper_search"      → tools/paper_search_tool.py  → Arxiv 论文搜索
#   "geogebra_analysis" → tools/vision/               → GeoGebra 分析
#   "write_note"        → tools/write_note.py         → 写笔记
#   "ask_user"          → tools/ask_user.py           → 暂停等待用户回复
#   "read_source"       → tools/read_source.py        → 读取来源文档
第 8 步：事件流回传

工具执行 / LLM 生成
    ↓
StreamBus.emit(StreamEvent)
    ↓
orchestrator → yield event
    ↓
turn_runtime._publish_live_event()
    ↓
subscriber.queue → unified_ws.safe_send()
    ↓
WebSocket → 前端
完整调用链一图流

前端 WebSocket
    │
    ▼
[1] unified_ws.py          接收消息，调用 start_turn()
    │
    ▼
[2] turn_runtime.py        start_turn()：校验配置、选模型、创建 Turn
    │                      启动后台任务 _run_turn()
    ▼
[3] turn_runtime.py        _run_turn()：构建上下文
    │  ├─ attachment_store    处理附件
    │  ├─ context_builder     对话历史
    │  ├─ memory_store        Memory
    │  ├─ skill_service       Skills
    │  ├─ notebook_agent      Notebook
    │  ├─ book_context        Book
    │  ├─ question_bank       QuestionBank
    │  └─ source_inventory    来源清单
    │
    ▼
[4] orchestrator.py        ChatOrchestrator.handle()：路由到 Capability
    │
    ▼
[5] capability_registry.py 查找 Capability 实现
    │
    ▼
[6] agentic_pipeline.py    Capability.run()：agentic 工具调用循环
    │  ├─ 组装 system prompt
    │  ├─ 调用 LLM（带工具定义）
    │  ├─ 解析工具调用
    │  └─ 循环直到无工具调用
    │
    ▼
[7] tool_registry.py       执行具体工具（web_search / code / rag 等）
    │
    ▼
[8] StreamBus → turn_runtime → unified_ws → WebSocket → 前端


---------------------------------------------------------------------------------------
订阅某个时间流的意思就是监控这个对话流将其实时输出而执行逻辑在services.session
对，理解完全正确。用代码来说明：

订阅 = 监控 + 实时推送

# unified_ws.py 中的订阅
async for event in runtime.subscribe_turn(turn_id, after_seq=after_seq):
    await safe_send(event)   # 每来一个事件就推给客户端
subscribe_turn() 返回一个异步生成器，它背后是一个 asyncio.Queue。当 Turn 执行过程中产生事件时，事件会被放入队列，async for 拿到后立刻通过 WebSocket 推给客户端。

执行逻辑 = turn_runtime.py
真正的对话处理在 turn_runtime.py 的 _run_turn() 中：


_run_turn()
  ├─ ContextBuilder.build()     ← 构建上下文（历史、附件、知识库等）
  ├─ ChatOrchestrator.handle()  ← 路由到对应 Capability
  │    └─ Capability.run()      ← 执行 Agent 循环
  │         ├─ 调用 LLM
  │         ├─ 执行工具（搜索、代码等）
  │         ├─ 每一步都 publish_event()
  │         └─ 直到生成最终回复
  └─ 发送 done 事件
每次 publish_event() 都会把事件放入 StreamBus，订阅方（unified_ws.py 的 subscribe_turn）立刻收到并转发给客户端。

两个角色
角色	文件	职责
生产者	turn_runtime.py	执行对话逻辑，产生事件
消费者	unified_ws.py	订阅事件，推送给前端
中间通过 StreamBus（发布/订阅机制）连接，解耦了执行和推送。





核心对话
路由文件	端点	作用
unified_ws.py	/ws	主入口，统一 WebSocket，所有对话功能走这里
chat.py	/chat + /chat/sessions	旧版简单对话 WebSocket + 会话 CRUD
sessions.py	/sessions	会话管理（列表、详情、删除、分支选择）
AI 功能
路由文件	端点	作用
question.py	/mimic、/generate	出题（模拟题 / AI 生成题）
quiz_judge.py	/question/judge	AI 判题（WebSocket）
vision_solver.py	/vision/analyze、/vision/solve	拍照解题
co_writer.py	/edit、/automark	AI 写作助手（编辑、自动标注）
book.py	/books	AI 电子书（生成、编辑、测验）
知识管理
路由文件	端点	作用
knowledge.py	/knowledge	知识库管理（上传、索引、RAG）
notebook.py	/notebook	笔记本（创建、记录 CRUD）
question_notebook.py	/question-notebook	题库笔记本
memory.py	/memory	L3 记忆系统（用户画像、偏好、摘要）
配置和系统
路由文件	端点	作用
auth.py	/auth	认证（登录、注册、用户管理）
settings.py	/settings	系统设置（LLM、主题、语言、工具）
system.py	/system	系统状态（LLM 测试、嵌入测试）
tools.py	/tools	工具列表
skills.py	/skills	技能管理（CRUD）
agent_config.py	/agents	Agent 配置
capabilities_settings.py	/capabilities	能力模式配置
其他
路由文件	端点	作用
tutorbot.py	/tutorbot	自定义 AI 助手（创建、配置、对话）
dashboard.py	/dashboard	仪表盘（最近活动）
attachments.py	/attachments	附件下载
plugins_api.py	/plugins	插件系统（工具/能力执行）
一共约 150+ 个 API 端点，核心对话走 /ws，其余都是 REST 接口。





cd e:/xiangmu/study/AidLearning

# 构建镜像
docker build -t aidlearning:local .

# 运行
docker run -d \
  -p 8001:8001 \
  -p 3782:3782 \
  -v aidlearning-data:/app/data \
  --name aidlearning \
  aidlearning:local
cd e:/xiangmu/study/AidLearning

# 构建镜像
docker build -t aidlearning:local .

# 运行
docker run -d \
  -p 8001:8001 \
  -p 3782:3782 \
  -v aidlearning-data:/app/data \
  --name aidlearning \
  aidlearning:local





