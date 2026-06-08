"""
服务层
=======

AidLearning 统一服务层，提供：
- LLM 客户端与配置
- Embedding 客户端与配置
- RAG 管道与组件
- Prompt 管理
- 网络搜索 Provider
- 系统初始化工具
- 配置加载

用法：
    from aidlearning.services.llm import get_llm_client
    from aidlearning.services.embedding import get_embedding_client
    from aidlearning.services.rag import RAGService
    from aidlearning.services.prompt import get_prompt_manager
    from aidlearning.services.search import web_search
    from aidlearning.services.setup import init_user_directories
    from aidlearning.services.config import load_config_with_main

    # LLM
    llm = get_llm_client()
    response = await llm.complete("Hello, world!")

    # Embedding
    embed = get_embedding_client()
    vectors = await embed.embed(["text1", "text2"])

    # RAG（LlamaIndex 后端）
    rag = RAGService()
    result = await rag.search("query", kb_name="my_kb")

    # Prompt
    pm = get_prompt_manager()
    prompts = pm.load_prompts("solve", "solve_agent")

    # 搜索
    result = web_search("What is AI?")
"""

# 保持服务包导入副作用最小化。
# 模块在 __getattr__ 中延迟加载以避免循环导入。
from .path_service import PathService, get_path_service

__all__ = [
    "llm",
    "embedding",
    "rag",
    "prompt",
    "search",
    "setup",
    "session",
    "config",
    "PathService",
    "get_path_service",
    "BaseSessionManager",
]


def __getattr__(name: str):
    """对依赖大型库的模块进行延迟导入。"""
    import importlib

    if name == "llm":
        return importlib.import_module(f"{__name__}.llm")
    if name == "prompt":
        return importlib.import_module(f"{__name__}.prompt")
    if name == "search":
        return importlib.import_module(f"{__name__}.search")
    if name == "setup":
        return importlib.import_module(f"{__name__}.setup")
    if name == "session":
        return importlib.import_module(f"{__name__}.session")
    if name == "config":
        return importlib.import_module(f"{__name__}.config")
    if name == "rag":
        return importlib.import_module(f"{__name__}.rag")
    if name == "embedding":
        return importlib.import_module(f"{__name__}.embedding")
    if name == "BaseSessionManager":
        from .session import BaseSessionManager

        return BaseSessionManager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
