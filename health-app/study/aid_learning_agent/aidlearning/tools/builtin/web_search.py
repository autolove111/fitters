"""
Web Search Tool — 联网搜索工具

【调用链路位置】ChatAgent.retrieve_context() → tool_registry.execute("web_search") → web_search()

薄封装层，实际搜索逻辑在 services/search/ 中。
可用 Provider：brave、tavily、jina、searxng、duckduckgo、perplexity 等。
配置来源：data/user/settings/model_catalog.json 中的 search 配置。
"""

# Re-export from services layer
from aidlearning.services.search import (
    PROVIDER_TEMPLATES,
    SEARCH_API_KEY_ENV,
    AnswerConsolidator,
    BaseSearchProvider,
    Citation,
    SearchProvider,
    SearchResult,
    WebSearchResponse,
    get_available_providers,
    get_current_config,
    get_default_provider,
    get_provider,
    get_providers_info,
    list_providers,
    web_search,
)

__all__ = [
    # Main function
    "web_search",
    "get_current_config",
    # Provider management
    "get_provider",
    "list_providers",
    "get_available_providers",
    "get_default_provider",
    "get_providers_info",
    # Types
    "WebSearchResponse",
    "Citation",
    "SearchResult",
    # Consolidation
    "AnswerConsolidator",
    "PROVIDER_TEMPLATES",
    # Base class
    "BaseSearchProvider",
    "SearchProvider",
    "SEARCH_API_KEY_ENV",
]
