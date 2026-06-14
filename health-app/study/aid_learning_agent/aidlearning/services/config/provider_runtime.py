"""AidLearning 的 Nanobot 风格标准化运行时配置。"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any
from urllib.parse import urlparse

from aidlearning.services.model_selection import LLMSelection, apply_llm_selection_to_catalog
from aidlearning.services.provider_registry import (
    NANOBOT_LLM_PROVIDERS,
    PROVIDERS,
    ProviderSpec,
    canonical_provider_name,
    find_by_model,
    find_by_name,
    find_gateway,
)

from .embedding_endpoint import (
    EMBEDDING_PROVIDER_ALIASES,
    EMBEDDING_PROVIDER_DEFAULT_ENDPOINTS,
    embedding_endpoint_validation_error,
    normalize_embedding_endpoint_for_display,
)
from .loader import load_config_with_main
from .model_catalog import ModelCatalogService, get_model_catalog_service

SUPPORTED_SEARCH_PROVIDERS = {
    "brave",
    "tavily",
    "jina",
    "searxng",
    "duckduckgo",
    "perplexity",
    "serper",
    "none",
}
DEPRECATED_SEARCH_PROVIDERS = {"exa", "baidu", "openrouter"}


LLM_LOCALHOST_PROVIDERS = ("ollama", "vllm")


@dataclass(frozen=True)
class EmbeddingProviderSpec:
    """单个 Embedding Provider 元数据条目。

    关于 `default_api_base` 的说明：从 v1.3.0 起，这是**完整的
    Embedding 端点 URL**（如 ``https://api.openai.com/v1/embeddings``），
    而非基础 URL。适配器直接使用配置的 URL — 不会追加路径。
    """

    label: str
    default_api_base: str
    keywords: tuple[str, ...]
    is_local: bool
    adapter: str = "openai_compat"
    mode: str = "standard"
    default_model: str = ""
    default_dim: int = 0
    # 每个 Provider 的单次 Embedding 请求批量上限。适配器/客户端会根据此值
    # 约束 `batch_size`。SiliconFlow Qwen3 系列上限为 32；DashScope 为 20；大多数其他的限制较宽松。
    max_batch_items: int = 256
    # 当前默认模型是否支持多模态 `contents` 输入。
    multimodal: bool = False


EMBEDDING_PROVIDERS: dict[str, EmbeddingProviderSpec] = {
    "openai": EmbeddingProviderSpec(
        label="OpenAI",
        default_api_base=EMBEDDING_PROVIDER_DEFAULT_ENDPOINTS["openai"],
        keywords=("openai", "text-embedding", "ada-002", "embedding-3"),
        is_local=False,
        default_model="text-embedding-3-large",
        default_dim=3072,
    ),
    "gemini": EmbeddingProviderSpec(
        label="Gemini",
        default_api_base=EMBEDDING_PROVIDER_DEFAULT_ENDPOINTS["gemini"],
        keywords=("gemini", "gemini-embedding", "text-embedding"),
        is_local=False,
        default_model="gemini-embedding-001",
        default_dim=3072,
    ),
    "azure_openai": EmbeddingProviderSpec(
        label="Azure OpenAI",
        mode="direct",
        default_api_base="",
        keywords=("azure", "aoai"),
        is_local=False,
    ),
    "cohere": EmbeddingProviderSpec(
        label="Cohere",
        adapter="cohere",
        default_api_base=EMBEDDING_PROVIDER_DEFAULT_ENDPOINTS["cohere"],
        keywords=("cohere", "embed-v4", "embed-english", "embed-multilingual"),
        is_local=False,
        default_model="embed-v4.0",
        default_dim=1024,
        multimodal=True,
    ),
    "jina": EmbeddingProviderSpec(
        label="Jina",
        adapter="jina",
        default_api_base=EMBEDDING_PROVIDER_DEFAULT_ENDPOINTS["jina"],
        keywords=("jina", "jina-embeddings"),
        is_local=False,
        default_model="jina-embeddings-v3",
        default_dim=1024,
    ),
    "ollama": EmbeddingProviderSpec(
        label="Ollama",
        adapter="ollama",
        mode="local",
        default_api_base=EMBEDDING_PROVIDER_DEFAULT_ENDPOINTS["ollama"],
        keywords=("ollama", "nomic-embed", "mxbai", "snowflake-arctic", "all-minilm"),
        is_local=True,
        default_model="nomic-embed-text",
        default_dim=768,
    ),
    "vllm": EmbeddingProviderSpec(
        label="vLLM / LM Studio",
        mode="local",
        default_api_base=EMBEDDING_PROVIDER_DEFAULT_ENDPOINTS["vllm"],
        keywords=("vllm", "lmstudio"),
        is_local=True,
    ),
    "siliconflow": EmbeddingProviderSpec(
        label="SiliconFlow",
        adapter="openai_compat",
        default_api_base=EMBEDDING_PROVIDER_DEFAULT_ENDPOINTS["siliconflow"],
        keywords=(
            "siliconflow",
            "qwen3-embedding",
            "qwen3-vl-embedding",
            "bge-m3",
            "Pro/BAAI",
        ),
        is_local=False,
        default_model="Qwen/Qwen3-Embedding-8B",
        default_dim=4096,
        max_batch_items=32,
        multimodal=True,
    ),
    "aliyun": EmbeddingProviderSpec(
        label="Aliyun DashScope",
        adapter="dashscope_native",
        default_api_base=EMBEDDING_PROVIDER_DEFAULT_ENDPOINTS["aliyun"],
        keywords=("dashscope", "qwen3-vl-embedding", "qwen3-embedding", "aliyun", "bailian"),
        is_local=False,
        default_model="qwen3-vl-embedding",
        default_dim=2560,
        max_batch_items=20,
        multimodal=True,
    ),
    "custom": EmbeddingProviderSpec(
        label="OpenAI Compatible",
        mode="direct",
        default_api_base="",
        keywords=(),
        is_local=False,
    ),
    # 仅保留用于旧版配置。公开设置 Provider 使用精确的端点 URL
    # 和原始 HTTP 适配器，因此不会隐藏任何请求路径。
    "custom_openai_sdk": EmbeddingProviderSpec(
        label="Custom (OpenAI SDK)",
        adapter="openai_sdk",
        mode="direct",
        default_api_base="",
        keywords=(),
        is_local=False,
    ),
    "openrouter": EmbeddingProviderSpec(
        label="OpenRouter",
        adapter="openai_compat",
        default_api_base=EMBEDDING_PROVIDER_DEFAULT_ENDPOINTS["openrouter"],
        keywords=("openrouter",),
        is_local=False,
    ),
}


@dataclass(slots=True)
class NormalizedProviderConfig:
    """标准化的 Provider 配置输入。"""

    name: str
    api_key: str = ""
    api_base: str | None = None
    api_version: str | None = None
    extra_headers: dict[str, str] | None = None


@dataclass(slots=True)
class ResolvedLLMConfig:
    """get_llm_config/factory 使用的已解析运行时 LLM 配置。"""

    model: str
    provider_name: str
    provider_mode: str
    binding_hint: str | None = None
    binding: str = "openai"
    api_key: str = ""
    base_url: str | None = None
    effective_url: str | None = None
    api_version: str | None = None
    extra_headers: dict[str, str] = field(default_factory=dict)
    reasoning_effort: str | None = None
    context_window: int | None = None


@dataclass(slots=True)
class ResolvedEmbeddingConfig:
    """已解析的运行时 Embedding 配置。"""

    model: str
    provider_name: str
    provider_mode: str
    binding_hint: str | None = None
    binding: str = "openai"
    api_key: str = ""
    base_url: str | None = None
    effective_url: str | None = None
    api_version: str | None = None
    extra_headers: dict[str, str] = field(default_factory=dict)
    dimension: int = 0
    send_dimensions: bool | None = None
    request_timeout: int = 60
    batch_size: int = 10
    batch_delay: float = 0.0


@dataclass(slots=True)
class ResolvedSearchConfig:
    """已解析的运行时网络搜索配置。"""

    provider: str
    requested_provider: str
    api_key: str = ""
    base_url: str = ""
    max_results: int = 5
    proxy: str | None = None
    unsupported_provider: bool = False
    deprecated_provider: bool = False
    missing_credentials: bool = False
    fallback_reason: str | None = None

    @property
    def status(self) -> str:
        if self.unsupported_provider:
            return "unsupported"
        if self.deprecated_provider:
            return "deprecated"
        if self.missing_credentials:
            return "missing_credentials"
        if self.fallback_reason:
            return "fallback"
        return "ok"


def _as_str(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _to_headers(value: Any) -> dict[str, str]:
    if isinstance(value, dict):
        return {str(k): str(v) for k, v in value.items() if str(k).strip() and v is not None}
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, dict):
            return {str(k): str(v) for k, v in parsed.items() if str(k).strip() and v is not None}
    return {}


def _is_local_base_url(base_url: str | None) -> bool:
    if not base_url:
        return False
    try:
        parsed = urlparse(base_url if "://" in base_url else f"http://{base_url}")
    except Exception:
        return False
    host = (parsed.hostname or "").lower()
    return host in {"localhost", "127.0.0.1", "::1"} or host.endswith(".local")


def _load_catalog(catalog: dict[str, Any] | None) -> dict[str, Any]:
    if catalog is not None:
        return catalog
    return get_model_catalog_service().load()


def _active_profile_and_model(
    catalog: dict[str, Any],
    service: ModelCatalogService,
    service_name: str,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    profile = service.get_active_profile(catalog, service_name)
    model = service.get_active_model(catalog, service_name)
    return profile, model


def _collect_provider_pool(catalog: dict[str, Any]) -> dict[str, NormalizedProviderConfig]:
    providers: dict[str, NormalizedProviderConfig] = {}
    llm_profiles = catalog.get("services", {}).get("llm", {}).get("profiles", [])
    for profile in llm_profiles:
        name = canonical_provider_name(_as_str(profile.get("binding")))
        if not name:
            continue
        providers[name] = NormalizedProviderConfig(
            name=name,
            api_key=_as_str(profile.get("api_key")),
            api_base=_as_str(profile.get("base_url")) or None,
            api_version=_as_str(profile.get("api_version")) or None,
            extra_headers=_to_headers(profile.get("extra_headers")) or None,
        )
    return providers


def _choose_resolved_provider(
    *,
    hint: str | None,
    model: str,
    api_key: str,
    api_base: str | None,
    provider_pool: dict[str, NormalizedProviderConfig],
) -> ProviderSpec:
    explicit_spec = find_by_name(hint) if hint else None
    detected_gateway = find_gateway(
        provider_name=None,
        api_key=api_key or None,
        api_base=api_base or None,
    )
    # 保持向后兼容：当 key/base 明确指向网关 Provider 时，
    # 旧的 `binding=openai` 不应阻止网关检测。
    if explicit_spec and detected_gateway and explicit_spec.name == "openai":
        return detected_gateway
    if explicit_spec:
        return explicit_spec
    if detected_gateway:
        return detected_gateway

    model_spec = find_by_model(model)
    if model_spec:
        return model_spec

    if _is_local_base_url(api_base):
        if api_base and "11434" in api_base:
            return find_by_name("ollama") or find_by_name("vllm") or find_by_name("openai")
        return find_by_name("vllm") or find_by_name("ollama") or find_by_name("openai")

    for spec in PROVIDERS:
        configured = provider_pool.get(spec.name)
        if not configured:
            continue
        if spec.is_gateway and (configured.api_key or configured.api_base):
            return spec
    for spec in PROVIDERS:
        configured = provider_pool.get(spec.name)
        if not configured:
            continue
        if spec.is_local and configured.api_base:
            return spec
        if not spec.is_oauth and configured.api_key:
            return spec

    return find_by_name("openai") or PROVIDERS[0]


def resolve_llm_runtime_config(
    catalog: dict[str, Any] | None = None,
    *,
    service: ModelCatalogService | None = None,
    llm_selection: dict[str, Any] | LLMSelection | None = None,
) -> ResolvedLLMConfig:
    """使用 TutorBot 风格的 Provider 匹配解析活跃 LLM 配置。"""
    catalog_service = service or get_model_catalog_service()
    loaded = _load_catalog(catalog)
    loaded = apply_llm_selection_to_catalog(loaded, llm_selection)

    profile, model = _active_profile_and_model(loaded, catalog_service, "llm")
    resolved_model = _as_str((model or {}).get("model"))
    if not resolved_model:
        resolved_model = "gpt-4o-mini"

    binding_hint_raw = _as_str((profile or {}).get("binding"))
    binding_hint = canonical_provider_name(binding_hint_raw)

    active_api_key = _as_str((profile or {}).get("api_key"))
    active_api_base = _as_str((profile or {}).get("base_url"))
    active_api_version = _as_str((profile or {}).get("api_version"))
    reasoning_effort = _as_str((model or {}).get("reasoning_effort")) or None
    active_extra_headers = _to_headers((profile or {}).get("extra_headers"))
    context_window = _coerce_optional_int((model or {}).get("context_window"))
    if context_window is None:
        context_window = _coerce_optional_int((model or {}).get("context_window_tokens"))

    provider_pool = _collect_provider_pool(loaded)
    spec = _choose_resolved_provider(
        hint=binding_hint,
        model=resolved_model,
        api_key=active_api_key,
        api_base=active_api_base or None,
        provider_pool=provider_pool,
    )

    mapped = provider_pool.get(spec.name)
    api_key = active_api_key or (mapped.api_key if mapped else "")
    api_base = active_api_base or ((mapped.api_base or "") if mapped else "")
    api_version = active_api_version or ((mapped.api_version or "") if mapped else "")
    if not api_base and spec.default_api_base:
        api_base = spec.default_api_base
    if not api_key and spec.is_local:
        api_key = "sk-no-key-required"
    extra_headers = active_extra_headers or ((mapped.extra_headers or {}) if mapped else {})

    return ResolvedLLMConfig(
        model=resolved_model,
        provider_name=spec.name,
        provider_mode=spec.mode,
        binding_hint=binding_hint,
        binding=spec.name,
        api_key=api_key,
        base_url=api_base or None,
        effective_url=api_base or None,
        api_version=api_version or None,
        extra_headers=extra_headers,
        reasoning_effort=reasoning_effort,
        context_window=context_window,
    )


def _canonical_embedding_provider_name(name: str | None) -> str | None:
    if not name:
        return None
    key = name.strip().replace("-", "_")
    if not key:
        return None
    key = EMBEDDING_PROVIDER_ALIASES.get(key, key)
    key = canonical_provider_name(key) or key
    key = EMBEDDING_PROVIDER_ALIASES.get(key, key)
    if key in EMBEDDING_PROVIDERS:
        return key
    return None


def _collect_embedding_provider_pool(
    catalog: dict[str, Any],
) -> dict[str, NormalizedProviderConfig]:
    providers: dict[str, NormalizedProviderConfig] = {}
    embedding_profiles = catalog.get("services", {}).get("embedding", {}).get("profiles", [])
    for profile in embedding_profiles:
        name = _canonical_embedding_provider_name(_as_str(profile.get("binding")))
        if not name:
            continue
        providers[name] = NormalizedProviderConfig(
            name=name,
            api_key=_as_str(profile.get("api_key")),
            api_base=_as_str(profile.get("base_url")) or None,
            api_version=_as_str(profile.get("api_version")) or None,
            extra_headers=_to_headers(profile.get("extra_headers")) or None,
        )
    return providers


def _resolve_embedding_dimension(value: Any, default: int = 0) -> int:
    """解析维度值。未知/无法解析时返回 0。

    下游中值为 0 表示"使用 Provider 的原生默认值"；
    test_runner 在首次成功连接测试时会用实际响应维度自动填充目录。
    """
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return default
    if parsed <= 0:
        return default
    return parsed


def _coerce_optional_bool(value: Any) -> bool | None:
    """从目录值中解析三态布尔值。

    对显式值返回 ``True``/``False``，对缺失、空或无法识别的输入
    返回 ``None``（表示"使用默认行为"）。
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if not text:
        return None
    if text in {"true", "1", "yes", "on"}:
        return True
    if text in {"false", "0", "no", "off"}:
        return False
    return None


def _coerce_optional_int(value: Any) -> int | None:
    """从目录值中解析正整数，未设置时返回 ``None``。"""
    if value is None:
        return None
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _resolve_embedding_provider(
    *,
    hint: str | None,
    model: str,
    api_base: str | None,
    provider_pool: dict[str, NormalizedProviderConfig],
) -> str:
    if hint and hint in EMBEDDING_PROVIDERS:
        return hint

    model_lower = (model or "").lower()
    model_prefix = model_lower.split("/", 1)[0].replace("-", "_") if "/" in model_lower else ""
    if model_prefix in EMBEDDING_PROVIDERS:
        return model_prefix

    for provider_name, spec in EMBEDDING_PROVIDERS.items():
        if any(keyword in model_lower for keyword in spec.keywords):
            return provider_name

    if _is_local_base_url(api_base):
        if api_base and "11434" in api_base:
            return "ollama"
        return "vllm"

    for provider_name, spec in EMBEDDING_PROVIDERS.items():
        configured = provider_pool.get(provider_name)
        if not configured:
            continue
        if spec.is_local and configured.api_base:
            return provider_name
        if configured.api_key:
            return provider_name

    return "openai"


def resolve_embedding_runtime_config(
    catalog: dict[str, Any] | None = None,
    *,
    service: ModelCatalogService | None = None,
) -> ResolvedEmbeddingConfig:
    """使用 Provider 运行时标准化解析活跃 Embedding 配置。"""
    catalog_service = service or get_model_catalog_service()
    loaded = _load_catalog(catalog)
    profile, model = _active_profile_and_model(loaded, catalog_service, "embedding")
    resolved_model = _as_str((model or {}).get("model"))
    if not resolved_model:
        raise ValueError(
            "No active embedding model is configured. Please set it in Settings > Catalog."
        )

    binding_hint_raw = _as_str((profile or {}).get("binding"))
    binding_hint = _canonical_embedding_provider_name(binding_hint_raw)

    active_api_key = _as_str((profile or {}).get("api_key"))
    active_api_base = _as_str((profile or {}).get("base_url"))
    active_api_version = _as_str((profile or {}).get("api_version"))
    active_extra_headers = _to_headers((profile or {}).get("extra_headers"))
    # 默认 0 表示"尚未知" — test_runner 在首次成功连接时自动填充。
    # 适配器/客户端应将 0 视为"让 Provider 使用其原生默认值"。
    # 之前此处硬编码为 3072，导致每个非 OpenAI Provider 在首次使用时维度验证失败。
    dimension = _resolve_embedding_dimension((model or {}).get("dimension") or 0, default=0)
    # ``None`` 表示"回退到适配器启发式"。
    send_dimensions = _coerce_optional_bool((model or {}).get("send_dimensions"))

    provider_pool = _collect_embedding_provider_pool(loaded)
    provider_name = _resolve_embedding_provider(
        hint=binding_hint,
        model=resolved_model,
        api_base=active_api_base or None,
        provider_pool=provider_pool,
    )
    spec = EMBEDDING_PROVIDERS[provider_name]
    mapped = provider_pool.get(provider_name)

    api_key = active_api_key or (mapped.api_key if mapped else "")
    api_base = active_api_base or ((mapped.api_base or "") if mapped else "")
    if not api_base and spec.default_api_base:
        api_base = spec.default_api_base
    api_version = active_api_version or ((mapped.api_version or "") if mapped else "")
    extra_headers = active_extra_headers or ((mapped.extra_headers or {}) if mapped else {})

    return ResolvedEmbeddingConfig(
        model=resolved_model,
        provider_name=provider_name,
        provider_mode=spec.mode,
        binding_hint=binding_hint,
        binding=provider_name,
        api_key=api_key,
        base_url=api_base or None,
        effective_url=api_base or None,
        api_version=api_version or None,
        extra_headers=extra_headers,
        dimension=dimension,
        send_dimensions=send_dimensions,
        request_timeout=60,
        batch_size=10,
        batch_delay=0.0,
    )


def _resolve_search_max_results(catalog: dict[str, Any], default: int = 5) -> int:
    profile = get_model_catalog_service().get_active_profile(catalog, "search") or {}
    raw = profile.get("max_results")
    if raw is not None:
        try:
            value = int(raw)
            return max(1, min(value, 10))
        except (TypeError, ValueError):
            pass
    try:
        settings = load_config_with_main("main.yaml")
    except Exception:
        return default
    tools = settings.get("tools", {}) if isinstance(settings, dict) else {}
    web_search = tools.get("web_search", {}) if isinstance(tools, dict) else {}
    if isinstance(web_search, dict):
        raw = web_search.get("max_results")
        if raw is not None:
            try:
                value = int(raw)
                return max(1, min(value, 10))
            except (TypeError, ValueError):
                pass
    web = tools.get("web", {}) if isinstance(tools, dict) else {}
    search = web.get("search", {}) if isinstance(web, dict) else {}
    raw = search.get("max_results") if isinstance(search, dict) else None
    if raw is None:
        return default
    try:
        value = int(raw)
        return max(1, min(value, 10))
    except (TypeError, ValueError):
        return default


def resolve_search_runtime_config(
    catalog: dict[str, Any] | None = None,
    *,
    service: ModelCatalogService | None = None,
) -> ResolvedSearchConfig:
    """使用 TutorBot 风格的回退行为解析活跃网络搜索配置。"""
    catalog_service = service or get_model_catalog_service()
    loaded = _load_catalog(catalog)
    profile = catalog_service.get_active_profile(loaded, "search") or {}

    requested_provider = (_as_str(profile.get("provider")) or "duckduckgo").lower()
    provider = requested_provider
    api_key = _as_str(profile.get("api_key"))
    base_url = _as_str(profile.get("base_url"))
    proxy = _as_str(profile.get("proxy")) or None
    max_results = _resolve_search_max_results(loaded)

    deprecated = provider in DEPRECATED_SEARCH_PROVIDERS
    unsupported = provider not in SUPPORTED_SEARCH_PROVIDERS
    fallback_reason: str | None = None
    missing_credentials = False

    if provider == "none":
        return ResolvedSearchConfig(
            provider="none",
            requested_provider="none",
            api_key="",
            base_url="",
            max_results=max_results,
            proxy=proxy,
        )

    if provider in {"perplexity", "serper"} and not api_key:
        missing_credentials = True

    if unsupported:
        return ResolvedSearchConfig(
            provider=provider,
            requested_provider=requested_provider,
            api_key=api_key,
            base_url=base_url,
            max_results=max_results,
            proxy=proxy,
            unsupported_provider=True,
            deprecated_provider=deprecated,
            missing_credentials=missing_credentials,
        )

    if provider in {"brave", "tavily", "jina"} and not api_key:
        fallback_reason = f"{provider} requires api_key, falling back to duckduckgo"
        provider = "duckduckgo"
    elif provider == "searxng" and not base_url:
        fallback_reason = "searxng requires base_url, falling back to duckduckgo"
        provider = "duckduckgo"

    return ResolvedSearchConfig(
        provider=provider,
        requested_provider=requested_provider,
        api_key=api_key,
        base_url=base_url,
        max_results=max_results,
        proxy=proxy,
        unsupported_provider=False,
        deprecated_provider=deprecated,
        missing_credentials=missing_credentials,
        fallback_reason=fallback_reason,
    )


def search_provider_state(provider: str | None) -> str:
    """返回 Provider 状态类别，用于 UI/CLI/系统输出。"""
    value = (provider or "").strip().lower()
    if not value:
        return "not_configured"
    if value in DEPRECATED_SEARCH_PROVIDERS:
        return "deprecated"
    if value not in SUPPORTED_SEARCH_PROVIDERS:
        return "unsupported"
    return "supported"


__all__ = [
    "SUPPORTED_SEARCH_PROVIDERS",
    "DEPRECATED_SEARCH_PROVIDERS",
    "NANOBOT_LLM_PROVIDERS",
    "EmbeddingProviderSpec",
    "EMBEDDING_PROVIDERS",
    "EMBEDDING_PROVIDER_ALIASES",
    "embedding_endpoint_validation_error",
    "normalize_embedding_endpoint_for_display",
    "NormalizedProviderConfig",
    "ResolvedLLMConfig",
    "ResolvedEmbeddingConfig",
    "ResolvedSearchConfig",
    "LLM_LOCALHOST_PROVIDERS",
    "resolve_llm_runtime_config",
    "resolve_embedding_runtime_config",
    "resolve_search_runtime_config",
    "search_provider_state",
]
