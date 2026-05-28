# BaseAgent 类参考文档

> 所有 Agent 的统一基类，定义在 `deeptutor/agents/base_agent.py`

## 调用链路位置

```
ChatAgent / SolveAgent / ResearchAgent / ...  （子类）
        ↓ 继承
    BaseAgent
        ↓ 调用
    services/llm/factory.py  →  complete() / stream()
        ↓ 路由到
    CloudProvider / LocalProvider
```

---

## 类变量

| 变量 | 类型 | 说明 |
|------|------|------|
| `_shared_stats` | `dict[str, LLMStats]` | 每个模块共享的 Token 追踪器（类级别，所有实例共享） |
| `TraceCallback` | `Callable[[dict], Awaitable[None] \| None]` | trace 回调的类型别名 |

---

## 实例变量

在 `__init__()` 中初始化：

| 变量 | 类型 | 来源 | 说明 |
|------|------|------|------|
| `module_name` | `str` | 参数 | 模块名（chat / solve / research 等） |
| `agent_name` | `str` | 参数 | Agent 名（chat_agent 等） |
| `language` | `str` | 参数 | 语言设置（zh / en） |
| `_trace_callback` | `TraceCallback \| None` | 默认 None | trace 回调函数 |
| `config` | `dict` | 参数 | 原始配置字典 |
| `_agent_params` | `dict` | `get_agent_params()` | 从 agents.yaml 加载的参数（temperature, max_tokens） |
| `api_key` | `str` | `get_llm_config()` | LLM API 密钥 |
| `base_url` | `str` | `get_llm_config()` | LLM API 端点 |
| `model` | `str` | `get_llm_config()` | 模型名 |
| `api_version` | `str` | `get_llm_config()` | Azure API 版本 |
| `binding` | `str` | `get_llm_config()` | Provider 类型（openai / anthropic 等） |
| `agent_config` | `dict` | `config["agents"][agent_name]` | Agent 专属配置 |
| `llm_config` | `dict` | `config["llm"]` | LLM 配置 |
| `enabled` | `bool` | `agent_config` | Agent 是否启用 |
| `token_tracker` | `Any \| None` | 参数 | 外部 TokenTracker 实例 |
| `logger` | `Logger` | `logging` | 日志记录器 |
| `prompts` | `dict \| None` | `PromptManager` | 加载的 YAML prompt 模板 |

---

## 方法

### 1. 模型和参数获取

#### `get_model() -> str`

获取模型名称。

**优先级：** agent_config > llm_config > self.model > 环境变量

**Returns:** 模型名称
**Raises:** `ValueError` — 未配置模型时抛出

---

#### `get_temperature() -> float`

获取 temperature 参数。

**来源：** agents.yaml 中对应模块的配置
**Returns:** temperature 值

---

#### `get_max_tokens() -> int`

获取最大 token 数。

**来源：** agents.yaml 中对应模块的配置
**Returns:** 最大 token 数

---

#### `get_max_retries() -> int`

获取最大重试次数。

**优先级：** agent_config["max_retries"] > settings.retry.max_retries
**Returns:** 重试次数

---

#### `refresh_config() -> None`

刷新 LLM 配置 — 重新从 `get_llm_config()` 加载最新配置。

用户在 Settings 中修改配置后，调用此方法可使 Agent 使用新配置，无需重启服务器或重建 Agent 实例。

---

### 2. Trace 事件

#### `set_trace_callback(callback: TraceCallback | None) -> None`

注册 trace 回调 — 接收 LLM 调用的结构化事件。

回调函数接收 `dict` payload，包含 `event` / `state` / `model` / `chunk` 等字段。用于前端实时展示 LLM 调用进度。

---

#### `_emit_trace_event(payload: dict) -> None` (内部方法)

触发 trace 事件 — 调用已注册的回调函数。

- 如果回调是协程则 `await`
- 回调失败仅记录 debug 日志，不影响主流程

---

### 3. Token 追踪

#### `get_stats(module_name: str) -> LLMStats` (类方法)

获取或创建指定模块的 LLMStats 追踪器。

每个模块（chat / solve / research 等）共享一个 LLMStats 实例，用于统计该模块所有 Agent 的 token 用量。

---

#### `reset_stats(module_name: str | None = None)` (类方法)

重置统计信息。

- 传入模块名：只重置该模块
- 传入 None：重置所有模块

---

#### `print_stats(module_name: str | None = None)` (类方法)

打印统计摘要。

- 传入模块名：只打印该模块
- 传入 None：打印所有模块

---

#### `_track_tokens(model, system_prompt, user_prompt, response, stage=None)` (内部方法)

记录 token 用量，同时写入两个追踪器：

1. **外部 TokenTracker**（`self.token_tracker`，可选）
2. **共享 LLMStats**（始终写入）

追踪错误不影响主流程。

---

### 4. LLM 调用接口（核心）

#### `call_llm(...) -> str`

**非流式 LLM 调用** — 等待完整响应返回。

**调用链：**
```
call_llm() → llm_complete() → factory.complete() → provider.chat_with_retry()
```

**流程：**
1. 解析参数（model, temperature, max_tokens, max_retries）
2. 构建 kwargs（token 限制、response_format、多模态附件）
3. 发射 trace 事件（state=running）
4. 调用 `llm_complete()` → `factory.complete()`
5. 记录 token 用量
6. 发射 trace 事件（state=complete）

**参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `user_prompt` | `str` | 用户提示词（传入 messages 时忽略） |
| `system_prompt` | `str` | 系统提示词（传入 messages 时忽略） |
| `messages` | `list[dict] \| None` | 预构建的 messages 数组（可选，覆盖 prompt/system_prompt） |
| `response_format` | `dict \| None` | 响应格式（如 `{"type": "json_object"}`） |
| `temperature` | `float \| None` | 温度参数（可选，默认从配置读取） |
| `max_tokens` | `int \| None` | 最大 token 数（可选，默认从配置读取） |
| `model` | `str \| None` | 模型名（可选，默认从配置读取） |
| `verbose` | `bool` | 是否记录详细日志（默认 True） |
| `stage` | `str \| None` | 阶段标记（用于日志和追踪） |
| `attachments` | `list \| None` | 图片/文件附件（多模态输入） |
| `trace_meta` | `dict \| None` | 额外的 trace 元数据 |

**Returns:** LLM 响应文本

---

#### `stream_llm(...) -> AsyncGenerator[str, None]`

**流式 LLM 调用** — 逐 chunk yield 文本。

**调用链：**
```
stream_llm() → llm_stream() → factory.stream() → provider.chat_stream_with_retry()
```

**流程：**
1. 解析参数（同 call_llm）
2. 处理多模态附件
3. 发射 trace 事件（state=running）
4. 调用 `llm_stream()` → `factory.stream()`，逐 chunk yield
5. 每个 chunk 发射 trace 事件（state=streaming）
6. 流结束后记录 token 用量，发射 trace 事件（state=complete）

**参数：** 同 `call_llm()`（不含 `verbose`）

**Yields:** 响应文本片段（逐 chunk）

---

### 5. Prompt 辅助

#### `get_prompt(section_or_type="system", field_or_fallback=None, fallback="") -> str | None`

获取 prompt 内容，支持两种查找模式：

| 模式 | 调用方式 | 查找逻辑 |
|------|---------|---------|
| 简单查找 | `get_prompt("system")` | `prompts["system"]` |
| 嵌套查找 | `get_prompt("section", "field", "fallback")` | `prompts["section"]["field"]` |

**Returns:** prompt 字符串，未找到时返回 fallback 或 None

---

#### `has_prompts() -> bool`

检查 prompt 是否已加载。

---

### 6. 状态和抽象方法

#### `is_enabled() -> bool`

检查 Agent 是否启用。

---

#### `process(*args, **kwargs) -> Any` (抽象方法)

Agent 的主处理逻辑 — **子类必须实现**。

---

#### `__repr__() -> str`

Agent 的字符串表示，格式：`ChatAgent(module=chat, name=chat_agent, enabled=True)`

---

## 子类使用示例

```python
class ChatAgent(BaseAgent):
    def __init__(self, language="zh", config=None, **kwargs):
        # 初始化基类（加载配置、Prompt 等）
        super().__init__(
            module_name="chat",
            agent_name="chat_agent",
            language=language,
            config=config,
            **kwargs,
        )

    async def process(self, message, history=None, **kwargs):
        # 1. 获取 prompt
        system_prompt = self.get_prompt("system", "默认提示词")

        # 2. 组装 messages
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message},
        ]

        # 3. 流式调用 LLM
        async for chunk in self.stream_llm(
            user_prompt=message,
            system_prompt=system_prompt,
            messages=messages,
        ):
            yield chunk
```

---

## 调用关系图

```
子类 (ChatAgent.process())
  │
  ├─ self.get_model() / get_temperature() / get_max_tokens()
  │     └─ 从 agents.yaml 和 get_llm_config() 读取
  │
  ├─ self.get_prompt("system")
  │     └─ 从 PromptManager 加载的 YAML 模板中读取
  │
  ├─ self.call_llm(...)              ← 非流式
  │    ├─ llm_complete()             ← factory.complete()
  │    │    └─ provider.chat_with_retry()
  │    ├─ _track_tokens()            ← 记录 token 用量
  │    └─ _emit_trace_event()        ← 触发 trace 事件
  │
  └─ self.stream_llm(...)            ← 流式
       ├─ llm_stream()               ← factory.stream()
       │    └─ provider.chat_stream_with_retry()
       ├─ _track_tokens()
       └─ _emit_trace_event()
```
