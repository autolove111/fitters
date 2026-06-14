"""能力设置端点。

暴露各能力的可调参数（temperature、max_tokens、阶段预算、迭代限制），
这些参数当前分散在 data/user/settings/agents.yaml 和 data/user/settings/main.yaml 中。

与 /api/v1/memory/settings 的模式一致：

* GET  /settings  → 返回完整 schema（含默认值）。
* PUT  /settings  → 将请求体合并回两个 YAML 文件并返回新状态。

校验逻辑在 aidlearning.services.config.capabilities_settings 中，
API 层仅作为薄传输层。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

router = APIRouter()


@router.get("/settings")
async def get_capabilities_settings_endpoint() -> dict[str, Any]:
    from aidlearning.services.config.capabilities_settings import capabilities_settings_dict

    return capabilities_settings_dict()


@router.put("/settings")
async def put_capabilities_settings(payload: dict[str, Any]) -> dict[str, Any]:
    from aidlearning.services.config.capabilities_settings import save_capabilities_settings

    return save_capabilities_settings(payload)
