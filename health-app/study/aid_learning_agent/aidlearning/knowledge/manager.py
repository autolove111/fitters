#!/usr/bin/env python
"""
知识库管理器

管理多个知识库并提供访问工具。
"""

from contextlib import contextmanager
from datetime import datetime, timedelta
import hashlib
import json
import logging
import os
from pathlib import Path
import shutil
import stat
import sys
from typing import Any

from aidlearning.services.rag.factory import DEFAULT_PROVIDER, normalize_provider_name
from aidlearning.services.rag.file_routing import FileTypeRouter

logger = logging.getLogger(__name__)


# 一个条目在被 ``list_knowledge_bases`` 视为过期孤立条目之前，允许其 KB 目录缺失的时间。
# KB 创建流程会在磁盘文件夹创建之前写入 "initializing" 配置条目，
# 因此宽限期太短会导致创建过程中的列表调用竞态删除该条目。
# 60 秒足以超过创建握手时间，同时仍能排除多日未清理的僵尸条目。
_ORPHAN_PRUNE_GRACE_SECONDS = 60


def _entry_updated_after(kb_entry: dict | None, cutoff: datetime) -> bool:
    """当条目的 ``updated_at`` 严格晚于 ``cutoff`` 时返回 True。

    无法解析时间戳的条目被视为旧条目（返回 False）——
    长时间卡住且在记录时间戳之前崩溃的孤立条目仍应被清理。
    """
    if not isinstance(kb_entry, dict):
        return False
    raw = kb_entry.get("updated_at")
    if not isinstance(raw, str):
        return False
    try:
        return datetime.fromisoformat(raw) > cutoff
    except ValueError:
        return False


# 跨平台文件锁
@contextmanager
def file_lock_shared(file_handle):
    """获取文件的共享（读）锁 - 跨平台。"""
    if sys.platform == "win32":
        import msvcrt

        msvcrt.locking(file_handle.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            yield
        finally:
            file_handle.seek(0)
            msvcrt.locking(file_handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(file_handle.fileno(), fcntl.LOCK_SH)
        try:
            yield
        finally:
            fcntl.flock(file_handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def file_lock_exclusive(file_handle):
    """获取文件的排他（写）锁 - 跨平台。"""
    if sys.platform == "win32":
        import msvcrt

        msvcrt.locking(file_handle.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            yield
        finally:
            file_handle.seek(0)
            msvcrt.locking(file_handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(file_handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(file_handle.fileno(), fcntl.LOCK_UN)


def _get_embedding_fingerprint() -> tuple[str, int] | None:
    """返回当前活跃 embedding 配置的 ``(model_name, dimension)``。"""
    try:
        from aidlearning.services.embedding import get_embedding_config

        cfg = get_embedding_config()
        return (cfg.model, cfg.dim)
    except Exception:
        return None


def _reconcile_embedding_flags(knowledge_bases: dict, base_dir: Path | None = None) -> bool:
    """将每个知识库的 embedding 标志与磁盘上的索引版本进行对账。

    对于每个知识库，我们检查扁平的 ``version-N`` 目录（以及旧版布局）
    中是否有与活跃 embedding 签名匹配的版本：

    * 找到匹配 → 清除 ``needs_reindex`` 和 ``embedding_mismatch``
      （用户已切换回之前已索引的配置）。
    * 未匹配，但知识库存储的 ``embedding_model`` 与当前指纹不同
      → 设置两个标志，以便 UI 显示"重新索引"操作提示。

    当任何条目发生更改时返回 ``True``。
    """
    from aidlearning.services.rag.embedding_signature import signature_from_embedding_config
    from aidlearning.services.rag.index_versioning import (
        find_matching_version,
        list_kb_versions,
    )

    fp = _get_embedding_fingerprint()
    signature = signature_from_embedding_config()
    changed = False

    if signature is None and not fp:
        return False

    for kb_name, kb_entry in knowledge_bases.items():
        if not isinstance(kb_entry, dict):
            continue

        kb_dir = (base_dir / kb_name) if base_dir is not None else None
        matched = False
        if kb_dir is not None and signature is not None:
            matched = find_matching_version(kb_dir, signature) is not None

        if matched:
            mutated_local = False
            if kb_entry.get("needs_reindex"):
                kb_entry["needs_reindex"] = False
                mutated_local = True
            if kb_entry.get("embedding_mismatch"):
                kb_entry.pop("embedding_mismatch", None)
                mutated_local = True
            if mutated_local:
                changed = True
            # 无论如何都刷新展示的版本列表，以便 UI 看到准确的状态。
            if kb_dir is not None:
                kb_entry["index_versions"] = list_kb_versions(kb_dir)
            continue

        # 磁盘上没有匹配的就绪索引版本。
        stored_model = kb_entry.get("embedding_model")
        # 空的/进行中的版本目录在索引完成之前创建。
        # 它们不应将全新知识库标记为需要重新索引。
        versions: list[dict] = []
        has_ready_version = False
        if kb_dir is not None:
            versions = list_kb_versions(kb_dir)
            has_ready_version = any(bool(version.get("ready")) for version in versions)
            kb_entry["index_versions"] = versions

        if not has_ready_version and not stored_model:
            continue

        current_model = fp[0] if fp else ""
        current_dim = fp[1] if fp else 0
        stored_dim = kb_entry.get("embedding_dim")
        mismatch = (stored_model and stored_model != current_model) or (
            stored_dim is not None and current_dim and stored_dim != current_dim
        )
        # 如果存在就绪版本但没有一个匹配活跃签名，那也是不匹配。
        if has_ready_version:
            mismatch = True

        if mismatch and not kb_entry.get("embedding_mismatch"):
            kb_entry["embedding_mismatch"] = True
            if not kb_entry.get("needs_reindex"):
                kb_entry["needs_reindex"] = True
            changed = True
        elif not mismatch and kb_entry.get("embedding_mismatch"):
            kb_entry.pop("embedding_mismatch", None)
            changed = True

    return changed


class KnowledgeBaseManager:
    """知识库管理器"""

    def __init__(self, base_dir="./data/knowledge_bases"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

        # 用于跟踪知识库的配置文件
        self.config_file = self.base_dir / "kb_config.json"
        self.config = self._load_config()

        # PocketBase 同步 — 当 integrations.pocketbase_url 设置时启用。
        # 本地 JSON 文件仍然是数据源；PocketBase 获得镜像副本，
        # 用于管理面板可见性和未来的多用户访问。
        from aidlearning.services.pocketbase_client import is_pocketbase_enabled

        self._pb_enabled = is_pocketbase_enabled()

    def _load_config(self) -> dict:
        """从规范的 kb_config.json 文件加载知识库配置。"""
        if self.config_file.exists():
            try:
                with open(self.config_file, encoding="utf-8") as f:
                    with file_lock_shared(f):
                        content = f.read()
                        if not content.strip():
                            # 空文件，返回默认值
                            return {"knowledge_bases": {}}
                        config = json.loads(content)

                # 确保 knowledge_bases 键存在
                if "knowledge_bases" not in config:
                    config["knowledge_bases"] = {}

                # 迁移：如果存在旧的 "default" 字段则移除
                if "default" in config:
                    del config["default"]
                    # 注意：不要在加载期间保存以避免递归问题
                    # 下一次 _save_config() 调用将持久化此更改

                # 迁移：将旧版提供者规范化为 llamaindex，
                # 并将仅旧版索引的知识库标记为 needs_reindex。
                from aidlearning.services.rag.index_versioning import list_kb_versions

                knowledge_bases = config.get("knowledge_bases", {})
                config_changed = False
                for kb_name, kb_entry in knowledge_bases.items():
                    if not isinstance(kb_entry, dict):
                        continue

                    raw_provider = kb_entry.get("rag_provider")
                    if kb_entry.get("rag_provider") != DEFAULT_PROVIDER:
                        kb_entry["rag_provider"] = DEFAULT_PROVIDER
                        config_changed = True

                    if isinstance(raw_provider, str) and raw_provider.strip().lower() not in {
                        "",
                        DEFAULT_PROVIDER,
                    }:
                        if not kb_entry.get("needs_reindex", False):
                            kb_entry["needs_reindex"] = True
                            config_changed = True

                    kb_dir = self.base_dir / kb_name
                    legacy_storage = kb_dir / "rag_storage"
                    has_llamaindex_index = any(
                        bool(version.get("ready")) for version in list_kb_versions(kb_dir)
                    )
                    if (
                        legacy_storage.exists()
                        and legacy_storage.is_dir()
                        and not has_llamaindex_index
                    ):
                        if not kb_entry.get("needs_reindex", False):
                            kb_entry["needs_reindex"] = True
                            config_changed = True

                if _reconcile_embedding_flags(knowledge_bases, self.base_dir):
                    config_changed = True

                if config_changed:
                    try:
                        with open(self.config_file, "w", encoding="utf-8") as f:
                            with file_lock_exclusive(f):
                                json.dump(config, f, indent=2, ensure_ascii=False)
                                f.flush()
                                os.fsync(f.fileno())
                    except Exception as save_err:
                        logger.warning(f"Failed to persist normalized KB config: {save_err}")

                return config
            except (json.JSONDecodeError, Exception) as e:
                logger.warning(f"Error loading config: {e}")
                return {"knowledge_bases": {}}
        return {"knowledge_bases": {}}

    def _save_config(self):
        """保存知识库配置（通过文件锁实现线程安全）"""
        # 使用排他锁进行写入
        with open(self.config_file, "w", encoding="utf-8") as f:
            with file_lock_exclusive(f):
                json.dump(self.config, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())  # 确保数据写入磁盘

    def _sync_kb_to_pb(self, name: str, kb_entry: dict) -> None:
        """
        将知识库元数据条目镜像到 PocketBase（尽力而为，非阻塞）。
        当 PocketBase 启用时，在每次本地配置保存后调用。
        """
        if not self._pb_enabled:
            return
        try:
            from aidlearning.services.pocketbase_client import get_pb_client

            pb = get_pb_client()
            records = pb.collection("knowledge_bases").get_full_list(
                query_params={"filter": f'kb_name="{name}"'}
            )
            payload = {
                "kb_name": name,
                "description": kb_entry.get("description", f"Knowledge base: {name}"),
                "rag_provider": kb_entry.get("rag_provider", "llamaindex"),
                "needs_reindex": bool(kb_entry.get("needs_reindex", False)),
                "status": kb_entry.get("status", "unknown"),
                "kb_created_at": kb_entry.get("created_at", ""),
            }
            if records:
                pb.collection("knowledge_bases").update(records[0].id, payload)
            else:
                pb.collection("knowledge_bases").create(payload)
        except Exception as exc:
            logger.debug(f"PocketBase KB sync failed for '{name}': {exc}")

    def update_kb_status(
        self,
        name: str,
        status: str,
        progress: dict | None = None,
    ):
        """
        更新 kb_config.json 中的知识库状态和进度。

        当 PocketBase 启用时，更新的条目也会镜像到
        PocketBase knowledge_bases 集合（尽力而为）。

        Args:
            name: 知识库名称
            status: 状态字符串（"initializing"、"processing"、"ready"、"error"）
            progress: 可选的进度字典，包含以下键：
                - stage: 当前阶段名称
                - message: 人类可读的消息
                - percent: 进度百分比（0-100）
                - current: 当前项目编号
                - total: 总项目数
                - file_name: 当前正在处理的文件
                - error: 错误消息（如果状态为 "error"）
        """
        # 重新加载配置以获取最新状态
        self.config = self._load_config()

        if "knowledge_bases" not in self.config:
            self.config["knowledge_bases"] = {}

        if name not in self.config["knowledge_bases"]:
            # 如果不存在则自动注册
            self.config["knowledge_bases"][name] = {
                "path": name,
                "description": f"Knowledge base: {name}",
            }

        kb_config = self.config["knowledge_bases"][name]
        kb_config["status"] = status
        kb_config["updated_at"] = datetime.now().isoformat()
        index_changed = False
        indexed_count: int | None = None
        index_action: str | None = None
        if isinstance(progress, dict):
            raw_indexed_count = progress.get("indexed_count")
            if isinstance(raw_indexed_count, bool):
                indexed_count = int(raw_indexed_count)
            elif isinstance(raw_indexed_count, (int, float)):
                indexed_count = int(raw_indexed_count)
            elif isinstance(raw_indexed_count, str):
                try:
                    indexed_count = int(raw_indexed_count)
                except ValueError:
                    indexed_count = None

            index_changed = bool(progress.get("index_changed")) or (
                indexed_count is not None and indexed_count > 0
            )
            raw_index_action = progress.get("index_action")
            if isinstance(raw_index_action, str) and raw_index_action.strip():
                index_action = raw_index_action.strip()

        if status == "ready":
            # 就绪的知识库在 UI 中应显示为稳定资源，
            # 而不是永久携带 "completed" 进度横幅。
            kb_config.pop("progress", None)
            if progress is not None:
                kb_config["last_completed_at"] = (
                    progress.get("timestamp") or datetime.now().isoformat()
                )
                if index_changed:
                    kb_config["last_indexed_at"] = kb_config["last_completed_at"]
                    if indexed_count is not None:
                        kb_config["last_indexed_count"] = max(indexed_count, 0)
                    if index_action:
                        kb_config["last_indexed_action"] = index_action
        elif progress is not None:
            kb_config["progress"] = progress

        if status == "ready":
            fp = _get_embedding_fingerprint()
            if fp:
                kb_config["embedding_model"], kb_config["embedding_dim"] = fp
            # 记录活跃签名和磁盘上的版本注册表，
            # 以便 UI 可以渲染版本标签而无需重新计算。
            try:
                from aidlearning.services.rag.embedding_signature import (
                    signature_from_embedding_config,
                )
                from aidlearning.services.rag.index_versioning import (
                    list_kb_versions,
                )

                sig = signature_from_embedding_config()
                if sig is not None:
                    kb_config["embedding_signature"] = sig.hash()
                kb_dir = self.base_dir / name
                if kb_dir.is_dir():
                    kb_config["index_versions"] = list_kb_versions(kb_dir)
            except Exception:  # pragma: no cover - 尽力而为的元数据
                pass

        self._save_config()
        self._sync_kb_to_pb(name, kb_config)

    def get_kb_status(self, name: str) -> dict | None:
        """获取知识库的状态和进度。"""
        self.config = self._load_config()
        kb_config = self.config.get("knowledge_bases", {}).get(name)
        if not kb_config:
            return None
        return {
            "status": kb_config.get("status", "unknown"),
            "progress": kb_config.get("progress"),
            "updated_at": kb_config.get("updated_at"),
        }

    def list_knowledge_bases(self) -> list[str]:
        """列出所有可用的知识库。

        此方法：
        1. 从 kb_config.json 加载已注册的知识库
        2. 移除磁盘目录已不存在的已注册条目
           （初始化失败或手动 ``rm -rf`` 知识库文件夹产生的孤立条目）。
        3. 扫描目录中尚未注册的现有知识库
        4. 自动注册发现的有效 raw/index 结构的知识库
        """
        # 始终从文件重新加载配置以确保拥有最新数据
        self.config = self._load_config()

        config_kbs = self.config.get("knowledge_bases", {})
        kb_list: set[str] = set()
        config_changed = False

        # 过滤掉 KB 目录已消失的孤立条目。磁盘上的文件夹是存在性的
        # 真实来源——没有它，知识库就没有文档、没有索引，在 UI 中
        # 显示它只会展示用户无法操作的僵尸条目。
        #
        # 宽限期：新创建的知识库在 ``create_directory_structure`` 创建
        # 文件夹之前就写入了配置条目（以便 UI 可以立即渲染 "initializing"
        # 行）。如果 ``list`` 在该窗口期竞态调用，我们会错误地清理一个
        # 完全健康的正在创建的知识库。当 ``updated_at`` 足够新（初始化
        # 可能仍在进行中）时跳过清理。
        base_exists = self.base_dir.exists()
        grace_cutoff = datetime.now() - timedelta(seconds=_ORPHAN_PRUNE_GRACE_SECONDS)
        for kb_name, kb_entry in list(config_kbs.items()):
            rel_path = (kb_entry or {}).get("path", kb_name)
            kb_dir = self.base_dir / rel_path
            if base_exists and not kb_dir.exists():
                if _entry_updated_after(kb_entry, grace_cutoff):
                    kb_list.add(kb_name)
                    continue
                logger.warning(
                    "Pruning orphaned KB entry '%s': directory %s no longer exists.",
                    kb_name,
                    kb_dir,
                )
                del config_kbs[kb_name]
                config_changed = True
                continue
            kb_list.add(kb_name)

        # 同时扫描目录中可能尚未注册的知识库
        # 这确保了向后兼容性和自动发现
        if base_exists:
            for item in self.base_dir.iterdir():
                if not item.is_dir() or item.name.startswith(("__", ".")):
                    continue

                # 如果已在配置中则跳过
                if item.name in kb_list:
                    continue

                # 检查这是否是有效的知识库目录（扁平版本或旧版存储）
                from aidlearning.services.rag.index_versioning import list_kb_versions

                rag_storage = item / "rag_storage"
                is_valid_kb = any(
                    bool(version.get("ready")) for version in list_kb_versions(item)
                ) or (rag_storage.exists() and rag_storage.is_dir())

                if is_valid_kb:
                    # 将此知识库自动注册到 kb_config.json
                    kb_list.add(item.name)
                    self._auto_register_kb(item.name)
                    config_changed = True

        # 如果清理了孤立条目或注册了新知识库，则保存配置
        if config_changed:
            self._save_config()

        return sorted(kb_list)

    def _auto_register_kb(self, name: str):
        """将现有知识库自动注册到 kb_config.json。

        从 metadata.json（如果存在）读取信息以保持向后兼容。
        """
        kb_dir = self.base_dir / name

        # 默认值
        kb_entry: dict[str, Any] = {
            "path": name,
            "description": f"Knowledge base: {name}",
            "status": "ready",  # 已有存储的现有知识库被视为就绪
            "updated_at": datetime.now().isoformat(),
        }

        # 尝试从 metadata.json 读取现有信息（向后兼容）
        metadata_file = kb_dir / "metadata.json"
        if metadata_file.exists():
            try:
                with open(metadata_file, encoding="utf-8") as f:
                    metadata = json.load(f)
                # 迁移相关字段
                if metadata.get("description"):
                    kb_entry["description"] = metadata["description"]
                if metadata.get("rag_provider"):
                    raw_provider = str(metadata["rag_provider"]).strip().lower()
                    kb_entry["rag_provider"] = normalize_provider_name(raw_provider)
                    if raw_provider not in {"", DEFAULT_PROVIDER}:
                        kb_entry["needs_reindex"] = True
                if metadata.get("created_at"):
                    kb_entry["created_at"] = metadata["created_at"]
                if metadata.get("last_updated"):
                    kb_entry["updated_at"] = metadata["last_updated"]
                if metadata.get("last_indexed_at"):
                    kb_entry["last_indexed_at"] = metadata["last_indexed_at"]
                elif metadata.get("last_updated"):
                    kb_entry["last_indexed_at"] = metadata["last_updated"]
                if metadata.get("last_indexed_count") is not None:
                    kb_entry["last_indexed_count"] = metadata["last_indexed_count"]
                if metadata.get("last_indexed_action"):
                    kb_entry["last_indexed_action"] = metadata["last_indexed_action"]
            except Exception as e:
                logger.warning(f"Failed to read metadata.json for '{name}': {e}")

        # 如果未设置，从存储类型检测 rag_provider
        if "rag_provider" not in kb_entry:
            from aidlearning.services.rag.index_versioning import list_kb_versions

            rag_storage = kb_dir / "rag_storage"
            if any(bool(version.get("ready")) for version in list_kb_versions(kb_dir)):
                kb_entry["rag_provider"] = DEFAULT_PROVIDER
            elif rag_storage.exists():
                kb_entry["rag_provider"] = DEFAULT_PROVIDER
                kb_entry["needs_reindex"] = True

        # 添加到配置
        if "knowledge_bases" not in self.config:
            self.config["knowledge_bases"] = {}
        self.config["knowledge_bases"][name] = kb_entry

        logger.info(f"Auto-registered KB '{name}' to kb_config.json")

    def register_knowledge_base(self, name: str, description: str = "", set_default: bool = False):
        """注册知识库"""
        kb_dir = self.base_dir / name
        if not kb_dir.exists():
            raise ValueError(f"Knowledge base directory does not exist: {kb_dir}")

        if "knowledge_bases" not in self.config:
            self.config["knowledge_bases"] = {}

        self.config["knowledge_bases"][name] = {"path": name, "description": description}

        # 仅在明确请求时设置默认值
        if set_default:
            self.set_default(name)

        self._save_config()

    def get_knowledge_base_path(self, name: str | None = None) -> Path:
        """获取知识库路径"""
        if name is None:
            name = self.config.get("default")
            if name is None:
                raise ValueError("No default knowledge base set")

        kb_dir = self.base_dir / name
        if not kb_dir.exists():
            raise ValueError(f"Knowledge base not found: {name}")

        return kb_dir

    def get_rag_storage_path(self, name: str | None = None) -> Path:
        """获取知识库的活跃索引存储路径。"""
        kb_dir = self.get_knowledge_base_path(name)
        from aidlearning.services.rag.embedding_signature import signature_from_embedding_config
        from aidlearning.services.rag.index_versioning import (
            resolve_storage_dir_for_read,
        )

        active_storage = resolve_storage_dir_for_read(kb_dir, signature_from_embedding_config())
        legacy_storage = kb_dir / "rag_storage"
        if active_storage is not None:
            return active_storage
        if legacy_storage.exists():
            return legacy_storage
        raise ValueError(f"Index storage not found for knowledge base: {name or 'default'}")

    def get_images_path(self, name: str | None = None) -> Path:
        """获取知识库的图片路径"""
        kb_dir = self.get_knowledge_base_path(name)
        return kb_dir / "images"

    def get_content_list_path(self, name: str | None = None) -> Path:
        """获取知识库的内容列表路径"""
        kb_dir = self.get_knowledge_base_path(name)
        return kb_dir / "content_list"

    def get_raw_path(self, name: str | None = None) -> Path:
        """获取知识库的原始文档路径"""
        kb_dir = self.get_knowledge_base_path(name)
        return kb_dir / "raw"

    def set_default(self, name: str):
        """使用集中配置服务设置默认知识库。"""
        if name not in self.list_knowledge_bases():
            raise ValueError(f"Knowledge base not found: {name}")

        # 通过规范的 KB 配置服务持久化默认知识库选择。
        try:
            from aidlearning.services.config import get_kb_config_service

            kb_config_service = get_kb_config_service()
            kb_config_service.set_default_kb(name)
        except Exception as e:
            logger.warning(f"Failed to save default to centralized config: {e}")

    def get_default(self) -> str | None:
        """
        获取默认知识库名称。

        优先级：
        1. 规范 KB 配置服务（`data/knowledge_bases/kb_config.json`）
        2. 列表中的第一个知识库（自动回退）
        """
        # 首先尝试集中配置
        try:
            from aidlearning.services.config import get_kb_config_service

            kb_config_service = get_kb_config_service()
            default_kb = kb_config_service.get_default_kb()
            if default_kb and default_kb in self.list_knowledge_bases():
                return default_kb
        except Exception:
            pass

        # 回退到排序列表中的第一个知识库
        kb_list = self.list_knowledge_bases()
        if kb_list:
            return kb_list[0]

        return None

    @staticmethod
    def _embedding_fields(kb_config: dict) -> dict:
        """从知识库配置条目中提取 embedding 指纹字段。"""
        fields = {}
        for key in ("embedding_model", "embedding_dim"):
            val = kb_config.get(key)
            if val is not None:
                fields[key] = val
        if kb_config.get("embedding_mismatch"):
            fields["embedding_mismatch"] = True
        return fields

    def get_metadata(self, name: str | None = None) -> dict:
        """获取知识库元数据。

        来源：
        1. kb_config.json（权威来源）
        """
        kb_name = name
        if kb_name is None:
            kb_name = self.get_default()
            if kb_name is None:
                return {}

        # 首先尝试 kb_config.json（权威来源）
        self.config = self._load_config()
        kb_config = self.config.get("knowledge_bases", {}).get(kb_name, {})

        if kb_config:
            # 从配置构建元数据
            metadata = {
                "name": kb_name,
                "description": kb_config.get("description", f"Knowledge base: {kb_name}"),
                "rag_provider": DEFAULT_PROVIDER,
                "needs_reindex": bool(kb_config.get("needs_reindex", False)),
                "created_at": kb_config.get("created_at"),
                "last_updated": kb_config.get("updated_at"),
                "last_indexed_at": kb_config.get("last_indexed_at"),
                "last_indexed_count": kb_config.get("last_indexed_count"),
                "last_indexed_action": kb_config.get("last_indexed_action"),
            }
            metadata.update(self._embedding_fields(kb_config))
            # 移除 None 值
            metadata = {k: v for k, v in metadata.items() if v is not None}
            return metadata

        return {}

    def get_info(self, name: str | None = None) -> dict:
        """获取知识库的详细信息。

        此方法：
        1. 获取知识库名称（来自参数或默认值）
        2. 从 kb_config.json（权威来源）读取所有配置
        3. 对旧版知识库回退到 metadata.json
        4. 收集文件和 RAG 状态的统计信息
        """
        # 重新加载配置以获取最新状态
        self.config = self._load_config()

        kb_name = name or self.get_default()
        if kb_name is None:
            raise ValueError("No knowledge base name provided and no default set")

        # 获取知识库路径
        kb_dir = self.base_dir / kb_name

        # 从 kb_config.json（权威来源）获取配置
        kb_config = self.config.get("knowledge_bases", {}).get(kb_name, {})
        status = kb_config.get("status")
        progress = kb_config.get("progress")
        description = kb_config.get("description", f"Knowledge base: {kb_name}")
        rag_provider = DEFAULT_PROVIDER
        needs_reindex = bool(kb_config.get("needs_reindex", False))
        created_at = kb_config.get("created_at")
        updated_at = kb_config.get("updated_at")

        live_status = status in {"initializing", "processing"}
        if live_status and isinstance(progress, dict):
            live_status = progress.get("stage") not in {"completed", "error"}
        effective_needs_reindex = needs_reindex and not live_status

        # 如果仍在初始化，知识库可能还没有目录
        dir_exists = kb_dir.exists()
        index_versions: list[dict[str, Any]] = []
        has_ready_llamaindex = False
        if dir_exists:
            from aidlearning.services.rag.index_versioning import list_kb_versions

            index_versions = list_kb_versions(kb_dir)
            has_ready_llamaindex = any(bool(version.get("ready")) for version in index_versions)

        # 对于没有状态字段的旧版知识库，从 rag_storage 确定状态
        if effective_needs_reindex:
            status = "needs_reindex"
        elif (
            status in {"processing", "initializing"}
            and has_ready_llamaindex
            and not (isinstance(progress, dict) and progress.get("stage") == "error")
        ):
            # 磁盘上存在就绪的索引版本，但持久化的状态仍是 "live" 哨兵值
            # ——通常是因为进度写入器在索引完成之后、状态提升为 "ready"
            # 之前崩溃（或进程被杀死）。在读取时恢复实际状态，以免 UI
            # 显示永久的处理横幅。持久化的 kb_config.json 保持不变；
            # 下一次合法的 update_kb_status() 调用会清理它。
            # 参见 issue #418。
            status = "ready"
            progress = None
        elif not status and dir_exists:
            rag_storage_dir = kb_dir / "rag_storage"
            if has_ready_llamaindex:
                status = "ready"
            elif rag_storage_dir.exists() and any(rag_storage_dir.iterdir()):
                status = "needs_reindex"
                needs_reindex = True
                effective_needs_reindex = True
            else:
                status = "unknown"
        elif not status:
            status = "unknown"

        # 从 kb_config.json（权威来源）构建元数据
        metadata = {
            "name": kb_name,
            "description": description,
            "rag_provider": rag_provider,
            "needs_reindex": effective_needs_reindex,
        }
        if created_at:
            metadata["created_at"] = created_at
        if updated_at:
            metadata["last_updated"] = updated_at
        if kb_config.get("last_indexed_at"):
            metadata["last_indexed_at"] = kb_config.get("last_indexed_at")
        if kb_config.get("last_indexed_count") is not None:
            metadata["last_indexed_count"] = kb_config.get("last_indexed_count")
        if kb_config.get("last_indexed_action"):
            metadata["last_indexed_action"] = kb_config.get("last_indexed_action")

        metadata.update(self._embedding_fields(kb_config))

        # Remove None values
        metadata = {k: v for k, v in metadata.items() if v is not None}

        info = {
            "name": kb_name,
            "path": str(kb_dir),
            "is_default": kb_name == self.get_default(),
            "metadata": metadata,
            "status": status,
            "progress": progress,
        }

        # 统计文件数量 - 优雅处理错误
        raw_dir = kb_dir / "raw" if dir_exists else None
        images_dir = kb_dir / "images" if dir_exists else None
        content_list_dir = kb_dir / "content_list" if dir_exists else None

        raw_count = 0
        images_count = 0
        content_lists_count = 0

        if dir_exists:
            try:
                raw_count = len([f for f in raw_dir.iterdir() if f.is_file()]) if raw_dir else 0
            except Exception:
                pass

            try:
                images_count = (
                    len([f for f in images_dir.iterdir() if f.is_file()]) if images_dir else 0
                )
            except Exception:
                pass

            try:
                content_lists_count = (
                    len(list(content_list_dir.glob("*.json"))) if content_list_dir else 0
                )
            except Exception:
                pass

        # 检查 rag_initialized：扁平版本或旧版单层/嵌套存储。
        from aidlearning.services.rag.embedding_signature import signature_from_embedding_config
        from aidlearning.services.rag.index_versioning import (
            find_matching_version,
        )

        kb_dir = self.base_dir / kb_name if dir_exists else None
        rag_initialized = has_ready_llamaindex

        active_signature = signature_from_embedding_config()
        active_match = (
            find_matching_version(kb_dir, active_signature) is not None
            if (kb_dir and active_signature)
            else False
        )

        info["statistics"] = {
            "raw_documents": raw_count,
            "images": images_count,
            "content_lists": content_lists_count,
            "rag_initialized": rag_initialized,
            "rag_provider": rag_provider,
            "needs_reindex": effective_needs_reindex,
            "index_versions": index_versions,
            "active_signature": active_signature.hash() if active_signature else None,
            "active_match": active_match,
            # 在统计信息中包含状态和进度以保持向后兼容
            "status": status,
            "progress": progress,
        }

        return info

    def delete_knowledge_base(self, name: str, confirm: bool = False) -> bool:
        """
        删除知识库

        Args:
            name: 知识库名称
            confirm: 如果为 True，跳过确认（请谨慎使用！）

        Returns:
            删除成功返回 True
        """
        # 对原始配置进行查找而不是 ``list_knowledge_bases``：
        # 后者会作为副作用清理孤立条目（目录缺失），因此
        # 在这里调用它会竞态删除我们即将清理的条目，
        # 然后在现在为空的配置上抛出 "not found"。
        self.config = self._load_config()
        config_kbs = self.config.get("knowledge_bases", {})
        if name not in config_kbs and not (self.base_dir / name).exists():
            raise ValueError(f"Knowledge base not found: {name}")

        # 直接解析目录以保持幂等性：如果磁盘上的文件夹已被移除
        # （例如手动 rm-rf），我们仍希望从 kb_config.json 中清除
        # 孤立条目而不是失败。
        kb_dir = self.base_dir / name
        dir_exists = kb_dir.exists()

        if not confirm:
            # 在 CLI 中请求确认
            print(f"⚠️  Warning: This will permanently delete the knowledge base '{name}'")
            print(f"   Path: {kb_dir}")
            response = input("Are you sure? Type 'yes' to confirm: ")
            if response.lower() != "yes":
                print("Deletion cancelled.")
                return False

        if dir_exists:

            def _on_rmtree_error(func, path, exc_info):
                exc = exc_info[1]
                if isinstance(exc, FileNotFoundError):
                    # 竞态：其他进程在遍历和删除之间移除了该条目。
                    return
                # 在 Windows（以及某些绑定挂载的文件系统）上，只读位
                # 或失败的 RAG 初始化产生的过时句柄可能阻止删除。
                # 清除只读位并重试一次；如果仍然失败，记录日志并继续，
                # 以便配置条目无论如何都能被清理——让知识库卡在列表中
                # 比磁盘上的孤立文件更糟糕（issue #370）。
                try:
                    os.chmod(path, stat.S_IWRITE)
                    func(path)
                except Exception as retry_exc:
                    logger.warning(
                        f"Could not remove '{path}' while deleting KB '{name}': "
                        f"{retry_exc}. Continuing; orphan files may remain on disk."
                    )

            shutil.rmtree(kb_dir, onerror=_on_rmtree_error)
        else:
            logger.warning(
                f"KB directory '{kb_dir}' missing on disk; cleaning up orphaned config entry."
            )

        # 从配置中移除
        if name in self.config.get("knowledge_bases", {}):
            del self.config["knowledge_bases"][name]

        # 如果这是默认值则更新默认值
        if self.config.get("default") == name:
            remaining = [n for n in self.config.get("knowledge_bases", {}).keys() if n != name]
            self.config["default"] = sorted(remaining)[0] if remaining else None

        self._save_config()
        return True

    def clean_rag_storage(self, name: str | None = None, backup: bool = True) -> bool:
        """
        清理（删除）知识库的索引存储。

        Args:
            name: 知识库名称（未指定则使用默认值）
            backup: 如果为 True，删除前备份存储

        Returns:
            清理成功返回 True
        """
        kb_name = name or self.get_default()
        kb_dir = self.get_knowledge_base_path(kb_name)
        from aidlearning.services.rag.index_versioning import (
            LEGACY_VERSION_DIRNAME,
            VERSION_PREFIX,
        )

        legacy_llamaindex_storage_dir = kb_dir / "llamaindex_storage"
        legacy_versions_dir = kb_dir / LEGACY_VERSION_DIRNAME
        legacy_storage_dir = kb_dir / "rag_storage"

        flat_version_dirs = [
            path
            for path in kb_dir.iterdir()
            if path.is_dir() and path.name.startswith(VERSION_PREFIX)
        ]

        if (
            not flat_version_dirs
            and not legacy_versions_dir.exists()
            and not legacy_llamaindex_storage_dir.exists()
            and not legacy_storage_dir.exists()
        ):
            logger.info(f"Index storage does not exist for '{kb_name}'")
            return False

        targets = []
        for version_dir in flat_version_dirs:
            targets.append((version_dir.name, version_dir))
        if legacy_versions_dir.exists():
            targets.append((LEGACY_VERSION_DIRNAME, legacy_versions_dir))
        if legacy_llamaindex_storage_dir.exists():
            targets.append(("llamaindex_storage", legacy_llamaindex_storage_dir))
        if legacy_storage_dir.exists():
            targets.append(("rag_storage", legacy_storage_dir))

        for label, target in targets:
            if backup:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_dir = kb_dir / f"{label}_backup_{timestamp}"
                shutil.copytree(target, backup_dir)
                logger.info(f"Backed up {label} to: {backup_dir}")

            shutil.rmtree(target)
            logger.info(f"Cleaned {label} for '{kb_name}'")

        return True

    def link_folder(self, kb_name: str, folder_path: str) -> dict:
        """
        将本地文件夹链接到知识库。

        Args:
            kb_name: 知识库名称
            folder_path: 本地文件夹路径（支持 ~、相对路径）

        Returns:
            包含文件夹信息的字典，包括 id、路径和文件数量

        Raises:
            ValueError: 如果知识库未找到或文件夹不存在
        """
        if kb_name not in self.list_knowledge_bases():
            raise ValueError(f"Knowledge base not found: {kb_name}")

        # 规范化路径（跨平台：处理 ~、相对路径等）
        folder = Path(folder_path).expanduser().resolve()

        if not folder.exists():
            raise ValueError(f"Folder does not exist: {folder}")
        if not folder.is_dir():
            raise ValueError(f"Path is not a directory: {folder}")

        files = FileTypeRouter.collect_supported_files(folder, recursive=True)

        # 生成文件夹 ID

        folder_id = hashlib.md5(  # noqa: S324
            str(folder).encode(), usedforsecurity=False
        ).hexdigest()[:8]

        # 从元数据加载已链接的文件夹
        kb_dir = self.base_dir / kb_name
        metadata_file = kb_dir / "metadata.json"
        metadata: dict = {}

        if metadata_file.exists():
            try:
                with open(metadata_file, encoding="utf-8") as fp:
                    metadata = json.load(fp)
            except Exception:
                metadata = {}

        if "linked_folders" not in metadata:
            metadata["linked_folders"] = []

        # 检查是否已链接
        existing_ids = [item["id"] for item in metadata.get("linked_folders", [])]
        if folder_id in existing_ids:
            # 如果已链接，视为成功（幂等）
            # 查找并返回现有信息
            for item in metadata.get("linked_folders", []):
                if item["id"] == folder_id:
                    return item

        # 添加文件夹信息
        folder_info = {
            "id": folder_id,
            "path": str(folder),
            "added_at": datetime.now().isoformat(),
            "file_count": len(files),
        }
        metadata["linked_folders"].append(folder_info)

        # 保存元数据
        with open(metadata_file, "w", encoding="utf-8") as fp:
            json.dump(metadata, fp, indent=2, ensure_ascii=False)

        return folder_info

    def get_linked_folders(self, kb_name: str) -> list[dict]:
        """
        获取知识库的已链接文件夹列表。

        Args:
            kb_name: 知识库名称

        Returns:
            已链接文件夹信息字典列表
        """
        if kb_name not in self.list_knowledge_bases():
            raise ValueError(f"Knowledge base not found: {kb_name}")

        kb_dir = self.base_dir / kb_name
        metadata_file = kb_dir / "metadata.json"

        if not metadata_file.exists():
            return []

        try:
            with open(metadata_file, encoding="utf-8") as f:
                metadata = json.load(f)
                return metadata.get("linked_folders", [])
        except Exception:
            return []

    def unlink_folder(self, kb_name: str, folder_id: str) -> bool:
        """
        取消文件夹与知识库的链接。

        Args:
            kb_name: 知识库名称
            folder_id: 要取消链接的文件夹 ID

        Returns:
            取消链接成功返回 True，未找到返回 False
        """
        if kb_name not in self.list_knowledge_bases():
            raise ValueError(f"Knowledge base not found: {kb_name}")

        kb_dir = self.base_dir / kb_name
        metadata_file = kb_dir / "metadata.json"

        if not metadata_file.exists():
            return False

        try:
            with open(metadata_file, encoding="utf-8") as f:
                metadata = json.load(f)
        except Exception:
            return False

        linked = metadata.get("linked_folders", [])
        new_linked = [f for f in linked if f["id"] != folder_id]

        if len(new_linked) == len(linked):
            return False  # Not found

        metadata["linked_folders"] = new_linked

        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        return True

    def scan_linked_folder(self, folder_path: str, provider: str = DEFAULT_PROVIDER) -> list[str]:
        """
        扫描已链接文件夹并返回支持的文件路径列表。

        Args:
            folder_path: 文件夹路径
            provider: 用于确定支持扩展名的 RAG 提供者（默认：llamaindex）

        Returns:
            文件路径列表（字符串形式）
        """
        folder = Path(folder_path).expanduser().resolve()

        if not folder.exists() or not folder.is_dir():
            return []

        files = [
            str(file_path)
            for file_path in FileTypeRouter.collect_supported_files(folder, recursive=True)
        ]

        return sorted(files)

    def detect_folder_changes(self, kb_name: str, folder_id: str) -> dict:
        """
        检测已链接文件夹自上次同步以来的新文件和修改文件。

        这使得可以从可能与 SharePoint、Google Drive 等云服务
        同步的本地文件夹自动同步更改。

        Args:
            kb_name: 知识库名称
            folder_id: 要检查更改的文件夹 ID

        Returns:
            包含 'new_files'、'modified_files' 和 'has_changes' 键的字典
        """
        if kb_name not in self.list_knowledge_bases():
            raise ValueError(f"Knowledge base not found: {kb_name}")

        # 获取文件夹信息
        folders = self.get_linked_folders(kb_name)
        folder_info = next((f for f in folders if f["id"] == folder_id), None)

        if not folder_info:
            raise ValueError(f"Linked folder not found: {folder_id}")

        folder_path = Path(folder_info["path"]).expanduser().resolve()
        last_sync = folder_info.get("last_sync")
        synced_files = folder_info.get("synced_files", {})

        # 解析上次同步时间戳
        last_sync_time = None
        if last_sync:
            try:
                last_sync_time = datetime.fromisoformat(last_sync)
            except Exception:
                pass

        new_files = []
        modified_files = []

        for file_path in FileTypeRouter.collect_supported_files(folder_path, recursive=True):
            file_str = str(file_path)
            file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)

            if file_str in synced_files:
                # 检查自上次同步以来是否被修改
                prev_mtime_str = synced_files[file_str]
                try:
                    prev_mtime = datetime.fromisoformat(prev_mtime_str)
                    if file_mtime > prev_mtime:
                        modified_files.append(file_str)
                except Exception:
                    modified_files.append(file_str)
            else:
                # 新文件（不在已同步文件中）
                new_files.append(file_str)

        return {
            "new_files": sorted(new_files),
            "modified_files": sorted(modified_files),
            "has_changes": len(new_files) > 0 or len(modified_files) > 0,
            "new_count": len(new_files),
            "modified_count": len(modified_files),
        }

    def update_folder_sync_state(self, kb_name: str, folder_id: str, synced_files: list[str]):
        """
        成功同步后更新已链接文件夹的同步状态。

        记录哪些文件已同步及其修改时间，
        以便未来的更改检测。

        Args:
            kb_name: 知识库名称
            folder_id: 文件夹 ID
            synced_files: 成功同步的文件路径列表
        """
        if kb_name not in self.list_knowledge_bases():
            raise ValueError(f"Knowledge base not found: {kb_name}")

        kb_dir = self.base_dir / kb_name
        metadata_file = kb_dir / "metadata.json"

        if not metadata_file.exists():
            return

        try:
            with open(metadata_file, encoding="utf-8") as f:
                metadata = json.load(f)
        except Exception:
            return

        linked = metadata.get("linked_folders", [])

        for folder in linked:
            if folder["id"] == folder_id:
                # 记录同步时间戳
                folder["last_sync"] = datetime.now().isoformat()

                # 记录文件修改时间
                file_states = folder.get("synced_files", {})
                for file_path in synced_files:
                    try:
                        p = Path(file_path)
                        if p.exists():
                            mtime = datetime.fromtimestamp(p.stat().st_mtime)
                            file_states[file_path] = mtime.isoformat()
                    except Exception:
                        pass

                folder["synced_files"] = file_states
                folder["file_count"] = len(file_states)
                break


def main():
    """知识库管理器的命令行界面"""
    import argparse

    parser = argparse.ArgumentParser(description="Knowledge Base Manager")
    parser.add_argument(
        "--base-dir", default="./knowledge_bases", help="Base directory for knowledge bases"
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # 列表命令
    subparsers.add_parser("list", help="List all knowledge bases")

    # 信息命令
    info_parser = subparsers.add_parser("info", help="Show knowledge base information")
    info_parser.add_argument(
        "name", nargs="?", help="Knowledge base name (default if not specified)"
    )

    # 设置默认命令
    default_parser = subparsers.add_parser("set-default", help="Set default knowledge base")
    default_parser.add_argument("name", help="Knowledge base name")

    # 删除命令
    delete_parser = subparsers.add_parser("delete", help="Delete a knowledge base")
    delete_parser.add_argument("name", help="Knowledge base name")
    delete_parser.add_argument("--force", action="store_true", help="Skip confirmation")

    # 清理 RAG 命令
    clean_parser = subparsers.add_parser(
        "clean-rag", help="Clean RAG storage (useful for corrupted data)"
    )
    clean_parser.add_argument(
        "name", nargs="?", help="Knowledge base name (default if not specified)"
    )
    clean_parser.add_argument(
        "--no-backup", action="store_true", help="Don't backup before cleaning"
    )

    args = parser.parse_args()

    manager = KnowledgeBaseManager(args.base_dir)

    if args.command == "list":
        kb_list = manager.list_knowledge_bases()
        default_kb = manager.get_default()

        print("\nAvailable Knowledge Bases:")
        print("=" * 60)
        if not kb_list:
            print("No knowledge bases found")
        else:
            for kb_name in kb_list:
                default_marker = " (default)" if kb_name == default_kb else ""
                print(f"  • {kb_name}{default_marker}")
        print()

    elif args.command == "info":
        try:
            info = manager.get_info(args.name)

            print("\nKnowledge Base Information:")
            print("=" * 60)
            print(f"Name: {info['name']}")
            print(f"Path: {info['path']}")
            print(f"Default: {'Yes' if info['is_default'] else 'No'}")

            if info.get("metadata"):
                print("\nMetadata:")
                for key, value in info["metadata"].items():
                    print(f"  {key}: {value}")

            print("\nStatistics:")
            stats = info["statistics"]
            print(f"  Raw documents: {stats['raw_documents']}")
            print(f"  Images: {stats['images']}")
            print(f"  Content lists: {stats['content_lists']}")
            print(f"  RAG initialized: {'Yes' if stats['rag_initialized'] else 'No'}")

            if "rag" in stats:
                print("\n  RAG Statistics:")
                for key, value in stats["rag"].items():
                    print(f"    {key}: {value}")

            print()
        except Exception as e:
            print(f"Error: {e!s}")

    elif args.command == "set-default":
        try:
            manager.set_default(args.name)
            print(f"✓ Set '{args.name}' as default knowledge base")
        except Exception as e:
            print(f"Error: {e!s}")

    elif args.command == "delete":
        try:
            success = manager.delete_knowledge_base(args.name, confirm=args.force)
            if success:
                print(f"✓ Deleted knowledge base '{args.name}'")
        except Exception as e:
            print(f"Error: {e!s}")

    elif args.command == "clean-rag":
        try:
            manager.clean_rag_storage(args.name, backup=not args.no_backup)
        except Exception as e:
            print(f"Error: {e!s}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
