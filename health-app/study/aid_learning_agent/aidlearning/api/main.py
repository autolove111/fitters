from contextlib import asynccontextmanager
import logging

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from aidlearning.logging import configure_logging
from aidlearning.services.config import (
    ensure_runtime_settings_files,
    export_runtime_settings_to_env,
    load_auth_settings,
    load_system_settings,
)
from aidlearning.services.path_service import get_path_service

ensure_runtime_settings_files()
export_runtime_settings_to_env(overwrite=True)
configure_logging()
logger = logging.getLogger(__name__)


class _SuppressWsNoise(logging.Filter):
    """抑制 WebSocket 连接频繁断开/重连时 uvicorn 产生的冗余日志。"""

    _SUPPRESSED = ("connection open", "connection closed")

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return not any(f in msg for f in self._SUPPRESSED)


logging.getLogger("uvicorn.error").addFilter(_SuppressWsNoise())

CONFIG_DRIFT_ERROR_TEMPLATE = (
    "检测到配置偏差：能力清单中引用的工具 {drift} 未在运行时工具注册表中注册。"
    "请注册缺失的工具，或从能力清单中移除过时的工具名称。"
)


class SafeOutputStaticFiles(StaticFiles):
    """静态文件挂载，仅对外提供经过白名单校验的文件。"""

    def __init__(self, *args, path_service, **kwargs):
        super().__init__(*args, **kwargs)
        self._path_service = path_service

    async def get_response(self, path: str, scope):
        if not self._path_service.is_public_output_path(path):
            raise HTTPException(status_code=404, detail="Output not found")
        return await super().get_response(path, scope)


def validate_tool_consistency():
    """
    校验能力清单中引用的所有工具是否都已在运行时 ToolRegistry 中注册。
    """
    try:
        from aidlearning.runtime.registry.capability_registry import get_capability_registry
        from aidlearning.tools.registry import get_tool_registry

        capability_registry = get_capability_registry()
        tool_registry = get_tool_registry()
        available_tools = set(tool_registry.list_tools())

        referenced_tools = set()
        for manifest in capability_registry.get_manifests():
            referenced_tools.update(manifest.get("tools_used", []) or [])

        drift = referenced_tools - available_tools
        if drift:
            raise RuntimeError(CONFIG_DRIFT_ERROR_TEMPLATE.format(drift=drift))
    except RuntimeError:
        logger.exception("Configuration validation failed")
        raise
    except Exception:
        logger.exception("Failed to load configuration for validation")
        raise


def _split_origins(value: str | None) -> list[str]:
    if not value:
        return []
    origins: list[str] = []
    seen: set[str] = set()
    for raw in value.replace("\n", ",").split(","):
        origin = raw.strip().rstrip("/")
        if not origin or origin in seen:
            continue
        origins.append(origin)
        seen.add(origin)
    return origins


def _build_cors_settings() -> dict[str, object]:
    """构建 CORS 配置，同时兼容本地开发和远程 Docker 部署场景。"""
    system_settings = load_system_settings()
    auth_settings = load_auth_settings()
    frontend_port = str(system_settings["frontend_port"])
    extra_origins = _split_origins(system_settings["cors_origin"]) + _split_origins(
        ",".join(system_settings["cors_origins"])
    )
    origins = [
        f"http://localhost:{frontend_port}",
        f"http://127.0.0.1:{frontend_port}",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    for origin in extra_origins:
        if origin not in origins:
            origins.append(origin)

    # 认证默认关闭。在此本地/单用户模式下，保持 v1.3.8 之前的行为，
    # 默认允许远程 Docker/局域网来源。
    # 开启认证后，需要显式配置 CORS_ORIGIN(S) 以支持携带凭证的跨域请求。
    allow_origin_regex = None if auth_settings["enabled"] else r"https?://.*"
    return {"allow_origins": origins, "allow_origin_regex": allow_origin_regex}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理
    优雅处理启动和关闭事件，避免 CancelledError
    """
    # 启动时执行
    logger.info("Application startup")

    # 校验配置一致性
    validate_tool_consistency()

    # 提前初始化 LLM 客户端，确保 OPENAI_* 环境变量在下游集成启动前就绪。
    try:
        from aidlearning.services.llm import get_llm_client

        llm_client = get_llm_client()
        logger.info(f"LLM client initialized: model={llm_client.config.model}")
    except Exception as e:
        logger.warning(f"Failed to initialize LLM client at startup: {e}")

    try:
        from aidlearning.events.event_bus import get_event_bus

        event_bus = get_event_bus()
        await event_bus.start()
        logger.info("EventBus started")
    except Exception as e:
        logger.warning(f"Failed to start EventBus: {e}")

    # 如果配置了 PocketBase 则进行连通性检测——不可达时记录警告（非错误）
    try:
        from aidlearning.services.pocketbase_client import ping_pocketbase

        await ping_pocketbase()
    except Exception as e:
        logger.warning(f"PocketBase startup check failed: {e}")

    # 将 v1 记忆文件（PROFILE.md / SUMMARY.md）迁移到备份目录，
    # 使 v2 三层记忆子系统以干净状态启动。
    try:
        from aidlearning.memory import migrate_v1_if_needed

        backup = migrate_v1_if_needed()
        if backup is not None:
            logger.info("v1 memory archived to %s", backup)
    except Exception as e:
        logger.warning(f"v1 memory migration failed: {e}")

    yield

    # 关闭时执行
    logger.info("Application shutdown")

    # 停止 EventBus
    try:
        from aidlearning.events.event_bus import get_event_bus

        event_bus = get_event_bus()
        await event_bus.stop()
        logger.info("EventBus stopped")
    except Exception as e:
        logger.warning(f"Failed to stop EventBus: {e}")


app = FastAPI(
    title="AidLearning API",
    version="1.0.0",
    lifespan=lifespan,
    # 禁用自动尾部斜杠重定向，防止在 HTTPS 反向代理（如 nginx）后部署时
    # 出现协议降级问题。否则 FastAPI 的 307 重定向可能将 HTTPS 变为 HTTP。
    # 参见：https://github.com/HKUDS/AidLearning/issues/112
    redirect_slashes=False,
)

# 仅记录非 200 请求（run_server.py 中已禁用 uvicorn 的 access_log）
_access_logger = logging.getLogger("uvicorn.access")


@app.middleware("http")
async def selective_access_log(request, call_next):
    response = await call_next(request)
    if response.status_code != 200:
        _access_logger.info(
            '%s - "%s %s HTTP/%s" %d',
            request.client.host if request.client else "-",
            request.method,
            request.url.path,
            request.scope.get("http_version", "1.1"),
            response.status_code,
        )
    return response


_cors_settings = _build_cors_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_settings["allow_origins"],
    allow_origin_regex=_cors_settings["allow_origin_regex"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载用户输出的过滤视图。
# 仅白名单中的文件路径可通过静态文件处理器访问。
path_service = get_path_service()
user_dir = path_service.get_public_outputs_root()

# 启动时初始化用户目录
try:
    from aidlearning.services.setup import init_user_directories

    init_user_directories()
except Exception:
    # 兜底方案：主目录不存在时直接创建
    if not user_dir.exists():
        user_dir.mkdir(parents=True)

app.mount(
    "/api/outputs",
    SafeOutputStaticFiles(directory=str(user_dir), path_service=path_service),
    name="outputs",
)

# 在运行时设置初始化完成后再导入路由模块。
# 部分路由模块会在导入时加载 YAML 配置。
from aidlearning.api.routers import (
    agent_config,
    attachments,
    auth,
    capabilities_settings,
    knowledge,
    memory,
    question,
    sessions,
    settings,
    skills,
    system,
    unified_ws,
)
from aidlearning.api.routers import (
    tools as tools_router,
)
from aidlearning.multi_user.router import router as multi_user_router  # noqa: E402

# 认证路由为公开接口——登录/登出/注册/状态查询无需 token
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])

# 其他所有路由在 AUTH_ENABLED=true 时需要有效的会话。
# 当 AUTH_ENABLED=false 时 require_auth 为空操作，本地使用无需担心。
from aidlearning.api.routers.auth import require_auth  # noqa: E402

_auth = [Depends(require_auth)]

app.include_router(
    multi_user_router,
    prefix="/api/v1/multi-user",
    tags=["multi-user"],
    dependencies=_auth,
)

app.include_router(
    question.router, prefix="/api/v1/question", tags=["question"], dependencies=_auth
)
app.include_router(
    knowledge.router, prefix="/api/v1/knowledge", tags=["knowledge"], dependencies=_auth
)
app.include_router(memory.router, prefix="/api/v1/memory", tags=["memory"], dependencies=_auth)
app.include_router(
    capabilities_settings.router,
    prefix="/api/v1/capabilities",
    tags=["capabilities"],
    dependencies=_auth,
)
app.include_router(
    sessions.router, prefix="/api/v1/sessions", tags=["sessions"], dependencies=_auth
)
app.include_router(
    settings.router, prefix="/api/v1/settings", tags=["settings"], dependencies=_auth
)
app.include_router(skills.router, prefix="/api/v1/skills", tags=["skills"], dependencies=_auth)
app.include_router(tools_router.router, prefix="/api/v1/tools", tags=["tools"], dependencies=_auth)
app.include_router(system.router, prefix="/api/v1/system", tags=["system"], dependencies=_auth)
app.include_router(
    agent_config.router, prefix="/api/v1/agent-config", tags=["agent-config"], dependencies=_auth
)
app.include_router(
    attachments.router,
    prefix="/api/attachments",
    tags=["attachments"],
    dependencies=_auth,
)

# 统一 WebSocket 端点——鉴权在处理器内部完成（WebSocket 无法以标准方式使用 FastAPI 依赖注入）
app.include_router(unified_ws.router, prefix="/api/v1", tags=["unified-ws"])


@app.get("/")
async def root():
    return {"message": "Welcome to AidLearning API"}


if __name__ == "__main__":
    from aidlearning.api.run_server import main as run_server_main

    run_server_main()
