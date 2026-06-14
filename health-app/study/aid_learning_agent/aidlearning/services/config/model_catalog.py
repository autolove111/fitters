from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from aidlearning.services.path_service import get_path_service

from .embedding_endpoint import normalize_embedding_endpoint_for_display

# 仅作回退 — 在导入时冻结于管理员作用域。生产代码应通过
# ``get_model_catalog_service()`` 进入，以便每次调用时从当前用户的 PathService 解析路径。
CATALOG_PATH = get_path_service().get_settings_file("model_catalog")


def _service_shell() -> dict[str, Any]:
    return {
        "active_profile_id": None,
        "active_model_id": None,
        "profiles": [],
    }


def _search_shell() -> dict[str, Any]:
    return {
        "active_profile_id": None,
        "profiles": [],
    }


def _default_catalog() -> dict[str, Any]:
    return {
        "version": 1,
        "services": {
            "llm": _service_shell(),
            "embedding": _service_shell(),
            "search": _search_shell(),
        },
    }


class ModelCatalogService:
    _instances: dict[str, "ModelCatalogService"] = {}

    def __init__(self, path: Path | None = None):
        self.path = path or CATALOG_PATH

    @classmethod
    def get_instance(cls, path: Path | None = None) -> "ModelCatalogService":
        resolved = (path or get_path_service().get_settings_file("model_catalog")).resolve()
        key = str(resolved)
        if key not in cls._instances:
            cls._instances[key] = cls(resolved)
        return cls._instances[key]

    def load(self) -> dict[str, Any]:
        loaded = self._read_existing_catalog()
        if loaded:
            catalog = _default_catalog()
            catalog.update({k: v for k, v in loaded.items() if k != "services"})
            catalog["services"].update(loaded.get("services", {}))
            merged_defaults = catalog != loaded
            before = deepcopy(catalog)
            self._normalize(catalog)
            if merged_defaults or catalog != before:
                self.save(catalog)
            return catalog

        catalog = _default_catalog()
        self._normalize(catalog)
        self.save(catalog)
        return catalog

    def _read_existing_catalog(self) -> dict[str, Any]:
        if not self.path.exists() or self.path.stat().st_size == 0:
            return {}
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return loaded if isinstance(loaded, dict) else {}

    def save(self, catalog: dict[str, Any]) -> dict[str, Any]:
        normalized = deepcopy(catalog)
        self._normalize(normalized)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump(normalized, handle, indent=2, ensure_ascii=False)
        return normalized

    def apply(self, catalog: dict[str, Any] | None = None) -> dict[str, Any]:
        current = self.save(catalog or self.load())
        return {"catalog_path": str(self.path), "services": list(current.get("services", {}))}

    def _normalize(self, catalog: dict[str, Any]) -> bool:
        services = catalog.setdefault("services", {})
        changed = False
        services.setdefault("llm", _service_shell())
        services.setdefault("embedding", _service_shell())
        services.setdefault("search", _search_shell())
        for service_name in ("llm", "embedding", "search"):
            service = services[service_name]
            profiles = service.setdefault("profiles", [])
            for profile in profiles:
                profile.setdefault("id", f"{service_name}-profile-{uuid4().hex[:8]}")
                profile.setdefault("name", "Untitled Profile")
                profile.setdefault("api_version", "")
                profile.setdefault("base_url", "")
                profile.setdefault("api_key", "")
                if service_name == "search":
                    profile.setdefault("provider", "brave")
                    profile.setdefault("proxy", "")
                    profile["models"] = []
                else:
                    profile.setdefault("binding", "openai")
                    profile.setdefault("extra_headers", {})
                    if service_name == "embedding":
                        before = str(profile.get("base_url") or "")
                        after = normalize_embedding_endpoint_for_display(
                            profile.get("binding"),
                            before,
                        )
                        if after != before:
                            profile["base_url"] = after
                            changed = True
                    models = profile.setdefault("models", [])
                    for model in models:
                        model.setdefault("id", f"{service_name}-model-{uuid4().hex[:8]}")
                        model.setdefault("name", model.get("model") or "Untitled Model")
                        model.setdefault("model", "")
                        if service_name == "embedding":
                            # 空默认值 → test_runner 在首次连接测试时从实际 API 响应自动填充。
                            model.setdefault("dimension", "")
                            # 上次成功"测试连接"时发现的支持维度 CSV —
                            # 驱动 UI 下拉菜单。当模型不在任何适配器的
                            # MODELS_INFO 映射中时为空。
                            model.setdefault("supported_dimensions", "")
            profile_ids = {profile.get("id") for profile in profiles}
            if profiles and service.get("active_profile_id") not in profile_ids:
                service["active_profile_id"] = profiles[0]["id"]
                changed = True
            if service_name in {"llm", "embedding"}:
                active_profile = self.get_active_profile(catalog, service_name)
                models = (active_profile or {}).get("models") or []
                model_ids = {model.get("id") for model in models}
                if models and service.get("active_model_id") not in model_ids:
                    service["active_model_id"] = models[0]["id"]
                    changed = True
        return changed

    def get_active_profile(
        self, catalog: dict[str, Any], service_name: str
    ) -> dict[str, Any] | None:
        service = catalog.get("services", {}).get(service_name, {})
        active_id = service.get("active_profile_id")
        for profile in service.get("profiles", []):
            if profile.get("id") == active_id:
                return profile
        profiles = service.get("profiles", [])
        return profiles[0] if profiles else None

    def get_active_model(self, catalog: dict[str, Any], service_name: str) -> dict[str, Any] | None:
        if service_name == "search":
            return None
        service = catalog.get("services", {}).get(service_name, {})
        active_model_id = service.get("active_model_id")
        profile = self.get_active_profile(catalog, service_name)
        if not profile:
            return None
        for model in profile.get("models", []):
            if model.get("id") == active_model_id:
                return model
        models = profile.get("models", [])
        return models[0] if models else None


def get_model_catalog_service() -> ModelCatalogService:
    try:
        from aidlearning.multi_user.context import get_current_user
        from aidlearning.multi_user.paths import get_admin_path_service

        if not get_current_user().is_admin:
            return ModelCatalogService.get_instance(
                get_admin_path_service().get_settings_file("model_catalog")
            )
    except Exception:
        pass
    return ModelCatalogService.get_instance(get_path_service().get_settings_file("model_catalog"))


__all__ = ["CATALOG_PATH", "ModelCatalogService", "get_model_catalog_service"]
