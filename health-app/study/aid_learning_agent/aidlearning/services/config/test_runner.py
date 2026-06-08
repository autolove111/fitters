from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import json
import threading
from threading import Lock
import time
from typing import Any
from uuid import uuid4

from .context_window_detection import detect_context_window
from .model_catalog import get_model_catalog_service
from .provider_runtime import (
    resolve_embedding_runtime_config,
    resolve_llm_runtime_config,
    resolve_search_runtime_config,
)


def _redact(value: str) -> str:
    if not value:
        return "(empty)"
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}...{value[-4:]}"


def _coerce_int(value: Any, default: int, *, minimum: int = 1) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, parsed)


def _coerce_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


@dataclass
class TestRun:
    id: str
    service: str
    status: str = "running"
    events: list[dict[str, Any]] = field(default_factory=list)
    lock: Lock = field(default_factory=Lock)
    cancelled: bool = False

    def emit(self, kind: str, message: str, **extra: Any) -> None:
        payload = {
            "type": kind,
            "message": message,
            "timestamp": time.time(),
            **extra,
        }
        with self.lock:
            self.events.append(payload)

    def snapshot(self, start: int) -> list[dict[str, Any]]:
        with self.lock:
            return self.events[start:]


class ConfigTestRunner:
    _instance: "ConfigTestRunner | None" = None

    def __init__(self) -> None:
        self._runs: dict[str, TestRun] = {}
        self._lock = Lock()

    @classmethod
    def get_instance(cls) -> "ConfigTestRunner":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def start(self, service: str, catalog: dict[str, Any] | None = None) -> TestRun:
        run = TestRun(id=f"{service}-{uuid4().hex[:10]}", service=service)
        with self._lock:
            self._runs[run.id] = run
        resolved = catalog or get_model_catalog_service().load()
        thread = threading.Thread(target=self._run_sync, args=(run, resolved), daemon=True)
        thread.start()
        return run

    def get(self, run_id: str) -> TestRun:
        return self._runs[run_id]

    def cancel(self, run_id: str) -> None:
        self.get(run_id).cancelled = True

    def _run_sync(self, run: TestRun, catalog: dict[str, Any]) -> None:
        try:
            service = run.service
            profile = get_model_catalog_service().get_active_profile(catalog, service)
            model = get_model_catalog_service().get_active_model(catalog, service)

            run.emit("info", "Preparing configuration snapshot.")
            if profile:
                run.emit(
                    "config",
                    "Using active profile.",
                    profile={
                        "name": profile.get("name", ""),
                        "base_url": profile.get("base_url", ""),
                        "binding": profile.get("binding") or profile.get("provider"),
                        "api_key": _redact(str(profile.get("api_key", ""))),
                        "api_version": profile.get("api_version", ""),
                    },
                    model=model,
                )

            if service == "llm":
                asyncio.run(self._test_llm(run, catalog))
            elif service == "embedding":
                asyncio.run(self._test_embedding(run, model or {}, catalog))
            elif service == "search":
                self._test_search(run, catalog)
            else:
                raise ValueError(f"Unsupported service: {service}")
            if not run.cancelled and run.status == "running":
                run.status = "completed"
                run.emit("completed", f"{service.upper()} test completed successfully.")
        except Exception as exc:
            run.status = "failed"
            run.emit("failed", str(exc))

    def _persist_embedding_dimension(
        self,
        catalog: dict[str, Any],
        model: dict[str, Any],
        actual_dimension: int,
    ) -> dict[str, Any]:
        """将探测到的维度写入活跃 Embedding 模型条目。

        每次"测试连接"成功后调用 — 探测是唯一数据源，
        因此会覆盖之前的目录维度。刷新 Embedding 客户端单例，
        使后续 embed 调用使用新维度。
        """
        from aidlearning.services.embedding.client import reset_embedding_client

        service = get_model_catalog_service()
        if model is None:
            return catalog
        model["dimension"] = str(actual_dimension)
        saved = service.save(catalog)
        reset_embedding_client()
        return saved

    @staticmethod
    def _capabilities_from_adapter(adapter: Any, model_name: str) -> dict[str, Any]:
        """将适配器的静态模型知识标准化为统一格式。

        各适配器在 ``get_model_info()`` 暴露的键上存在分歧
        （Cohere/Ollama 遗漏了 ``supported_dimensions``，即使数据
        存在于其 ``MODELS_INFO`` 中）。此辅助函数将两个来源合并，
        使 SSE 事件载荷始终保持相同格式。
        """
        info: dict[str, Any] = {}
        try:
            info = adapter.get_model_info() or {}
        except Exception:
            info = {}
        models_info = getattr(adapter, "MODELS_INFO", {}) or {}
        model_known = bool(model_name and model_name in models_info)

        raw_supported = info.get("supported_dimensions")
        if not isinstance(raw_supported, list):
            entry = models_info.get(model_name) if model_known else None
            if isinstance(entry, dict):
                raw_supported = entry.get("dimensions")
            else:
                raw_supported = None
        supported: list[int] = []
        if isinstance(raw_supported, list):
            for value in raw_supported:
                try:
                    supported.append(int(value))
                except (TypeError, ValueError):
                    continue

        default_raw = info.get("dimensions")
        try:
            default_dim = int(default_raw) if default_raw is not None else 0
        except (TypeError, ValueError):
            default_dim = 0

        return {
            "default_dim": default_dim,
            "supported_dimensions": supported,
            "supports_variable_dimensions": bool(info.get("supports_variable_dimensions")),
            "model_known": model_known,
        }

    async def _test_llm(self, run: TestRun, catalog: dict[str, Any]) -> None:
        from aidlearning.services.llm import clear_llm_config_cache, get_token_limit_kwargs
        from aidlearning.services.llm import complete as llm_complete
        from aidlearning.services.llm.config import LLMConfig

        clear_llm_config_cache()
        run.emit("info", "Loading LLM config from the active catalog selection.")
        resolved = resolve_llm_runtime_config(catalog=catalog)
        llm_config = LLMConfig(
            model=resolved.model,
            api_key=resolved.api_key,
            base_url=resolved.base_url,
            effective_url=resolved.effective_url,
            binding=resolved.binding,
            provider_name=resolved.provider_name,
            provider_mode=resolved.provider_mode,
            api_version=resolved.api_version,
            extra_headers=resolved.extra_headers,
            reasoning_effort=resolved.reasoning_effort,
        )
        run.emit(
            "info", f"Resolved model `{llm_config.model}` with binding `{llm_config.binding}`."
        )
        run.emit("info", f"Request target: {llm_config.base_url}")
        # 推理模型会将部分预算用于内部思考；
        # 上限过紧会导致返回空内容。可通过 agents.yaml 中的
        # diagnostics.llm_probe.max_tokens 进行配置。
        from .loader import get_agent_params

        probe_params = get_agent_params("llm_probe")
        max_tokens = _coerce_int(probe_params.get("max_tokens"), 1024)
        temperature = _coerce_float(probe_params.get("temperature"), 0.1)
        token_kwargs: dict[str, Any] = get_token_limit_kwargs(
            llm_config.model, max_tokens=max_tokens
        )
        run.emit("info", f"Token options: {json.dumps(token_kwargs)}")
        if llm_config.reasoning_effort:
            run.emit("info", f"Reasoning effort: {llm_config.reasoning_effort}")
        response = await llm_complete(
            model=llm_config.model,
            prompt="Say 'OK' and identify the model you are using.",
            system_prompt="Respond briefly but include your model identity if possible.",
            binding=llm_config.binding,
            api_key=llm_config.api_key or "sk-no-key-required",
            base_url=llm_config.effective_url or llm_config.base_url or "",
            api_version=llm_config.api_version,
            temperature=temperature,
            extra_headers=llm_config.extra_headers,
            reasoning_effort=llm_config.reasoning_effort,
            **token_kwargs,
        )
        snippet = (response or "").strip()
        run.emit("response", "Received LLM response.", snippet=snippet[:400])
        if not snippet:
            raise ValueError("LLM returned an empty response.")
        run.emit(
            "info",
            (
                "Basic LLM completion succeeded. Chat additionally validates "
                "streaming and provider tool compatibility at runtime."
            ),
        )

        run.emit("info", "正在检测模型上下文窗口。")
        detection = await detect_context_window(
            llm_config,
            on_log=lambda message: run.emit("info", message),
        )
        run.emit(
            "context_window",
            (f"检测到上下文窗口 {detection.context_window} tokens（{detection.source}）。"),
            context_window=detection.context_window,
            source=detection.source,
            detail=detection.detail,
            detected_at=detection.detected_at,
        )
        run.emit(
            "info",
            "上下文窗口检测在设置中可用，但未自动写入。",
        )

    async def _test_embedding(
        self, run: TestRun, model: dict[str, Any], catalog: dict[str, Any]
    ) -> None:
        from aidlearning.services.embedding.client import EmbeddingClient
        from aidlearning.services.embedding.config import EmbeddingConfig

        run.emit("info", "正在从活跃目录选择中加载 Embedding 配置。")
        resolved = resolve_embedding_runtime_config(catalog=catalog)
        catalog_dim = _coerce_int(model.get("dimension"), 0, minimum=0)
        # 强制冒烟探测不发送 `dimensions=` 参数，以便获取模型的原生最大维度。
        # 如果使用配置的维度，Matryoshka 模型（OpenAI text-embedding-3-*、
        # Cohere embed-v4、Jina v3/v4、DashScope qwen3-vl-embedding）会直接
        # 截断并返回我们请求的值 — 使 "detected_dim" 失去意义。
        config = EmbeddingConfig(
            model=resolved.model,
            api_key=resolved.api_key,
            base_url=resolved.base_url,
            effective_url=resolved.effective_url,
            binding=resolved.binding,
            provider_name=resolved.provider_name,
            provider_mode=resolved.provider_mode,
            api_version=resolved.api_version,
            extra_headers=resolved.extra_headers,
            dim=0,
            send_dimensions=False,
            request_timeout=max(1, resolved.request_timeout),
            batch_size=max(1, resolved.batch_size),
            batch_delay=max(0.0, resolved.batch_delay),
        )
        run.emit(
            "info", f"已解析 Embedding 模型 `{config.model}`，绑定 `{config.binding}`。"
        )
        run.emit(
            "info",
            f"请求目标（与设置中显示的完全一致）：{config.base_url}",
        )
        run.emit(
            "info",
            "使用小批量探测原生最大维度（不发送 `dimensions=` 参数）。",
        )
        client = EmbeddingClient(config)
        probe_texts = [
            "AidLearning embedding smoke test",
            "AidLearning retrieval batch probe",
        ]
        vectors = await client.embed(probe_texts)
        if len(vectors) != len(probe_texts):
            raise ValueError(
                "Embedding service returned an unexpected number of vectors "
                f"(expected {len(probe_texts)}, got {len(vectors)})."
            )
        if any(not vector for vector in vectors):
            raise ValueError("Embedding service returned an empty vector.")
        detected_dim = len(vectors[0])
        if any(len(vector) != detected_dim for vector in vectors):
            raise ValueError("Embedding service returned inconsistent vector dimensions.")

        capabilities = self._capabilities_from_adapter(client.adapter, config.model)
        supported = capabilities["supported_dimensions"]
        default_dim = capabilities["default_dim"]
        model_known = capabilities["model_known"]

        # 探测是唯一数据源：始终用检测到的值覆盖目录维度。
        # 希望使用截断变体的 Matryoshka 用户可在测试后手动编辑该字段。
        # 来源代码保持为 ``"detected"``，以便 UI 显示"来源：从 API 探测检测"。
        active_dim = detected_dim
        active_source = "detected"
        if catalog_dim and catalog_dim != detected_dim:
            active_message = (
                f"Catalog dim {catalog_dim}d overwritten with API probe value {detected_dim}d."
            )
        else:
            active_message = f"Active dim {detected_dim}d set from API probe."

        run.emit(
            "capabilities",
            (
                f"Probe returned {detected_dim}d. "
                + (
                    f"Static catalog: default {default_dim}d, "
                    f"supported {supported or '(fixed)'}, model recognized."
                    if model_known
                    else "Static catalog: model not recognized — using probe value as the only signal."
                )
            ),
            detected_dim=detected_dim,
            default_dim=default_dim,
            supported_dimensions=supported,
            supports_variable_dimensions=capabilities["supports_variable_dimensions"],
            model_known=model_known,
            active_dim=active_dim,
            active_dim_source=active_source,
        )

        run.emit(
            "response",
            "Embedding vector received.",
            actual_dimension=detected_dim,
            expected_dimension=catalog_dim or None,
        )

        # 刷新模型条目上缓存的 ``supported_dimensions`` CSV，
        # 以便设置页面无需重新运行测试即可填充下拉菜单。
        # 空列表 → 空字符串，清除任何过期缓存。变更发生在持久化调用之前，
        # 以确保单次保存往返携带两个字段。
        new_supported_csv = ",".join(str(d) for d in supported)
        if (model.get("supported_dimensions") or "") != new_supported_csv:
            model["supported_dimensions"] = new_supported_csv

        run.emit(
            "info",
            active_message,
            active_dim=active_dim,
            active_dim_source=active_source,
        )

        # 始终持久化：探测端到端运行成功，因此检测到的维度是权威数据。
        # ``_persist_embedding_dimension`` 在同一次保存中也会写入
        # 刷新后的 ``supported_dimensions`` CSV。
        saved_catalog = self._persist_embedding_dimension(catalog, model, detected_dim)
        run.emit(
            "catalog",
            "Saved detected embedding dimension to model_catalog.json.",
            catalog=saved_catalog,
        )

    def _test_search(self, run: TestRun, catalog: dict[str, Any]) -> None:
        from aidlearning.services.search import web_search

        resolved = resolve_search_runtime_config(catalog=catalog)
        if resolved.provider == "none":
            run.status = "completed"
            run.emit("completed", "Search skipped because no active provider is configured.")
            return
        if resolved.unsupported_provider:
            raise ValueError(
                f"Search provider `{resolved.requested_provider}` is deprecated/unsupported. "
                "Switch to none/brave/tavily/jina/searxng/duckduckgo/perplexity/serper."
            )
        if resolved.missing_credentials:
            raise ValueError(
                f"Search provider `{resolved.requested_provider}` requires api_key. "
                "Set profile.api_key in Settings > Catalog."
            )
        provider = resolved.provider
        run.emit("info", f"Resolved search provider `{provider}`.")
        if resolved.fallback_reason:
            run.emit("warning", resolved.fallback_reason)
        run.emit("info", "Running search query: AidLearning configuration health check")
        result = web_search("AidLearning configuration health check", provider=provider)
        run.emit(
            "response",
            "Search result received.",
            answer_preview=str(result.get("answer", ""))[:240],
            citation_count=len(result.get("citations", []) or []),
            search_result_count=len(result.get("search_results", []) or []),
        )
        if not (result.get("answer") or result.get("search_results")):
            raise ValueError("Search provider returned no answer and no search results.")


def get_config_test_runner() -> ConfigTestRunner:
    return ConfigTestRunner.get_instance()


__all__ = ["ConfigTestRunner", "TestRun", "get_config_test_runner"]
