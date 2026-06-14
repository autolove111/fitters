#!/usr/bin/env python
"""运行 Docker Compose，端口映射从 JSON 配置文件中渲染生成。

Docker Compose 无法直接读取 ``data/user/settings/system.json`` 来进行主机端口插值。
此包装器从 JSON 配置渲染一个小型 compose 环境文件，然后调用 ``docker compose --env-file``。
它不会读取或迁移项目根目录下的 ``.env`` 文件。
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SETTINGS_DIR = PROJECT_ROOT / "data" / "user" / "settings"
DOCKER_ENV_PATH = SETTINGS_DIR / "docker.env"

DEFAULT_BACKEND_PORT = 8001
DEFAULT_FRONTEND_PORT = 3782
DEFAULT_POCKETBASE_PORT = 8090


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _coerce_port(value: Any, default: int) -> int:
    try:
        port = int(str(value).strip())
    except (TypeError, ValueError):
        return default
    return port if 1 <= port <= 65535 else default


def render_docker_env(
    settings_dir: Path = SETTINGS_DIR,
    output_path: Path = DOCKER_ENV_PATH,
) -> dict[str, str]:
    """仅从 JSON 配置渲染 compose 插值变量。"""
    system = _read_json_object(settings_dir / "system.json")
    integrations = _read_json_object(settings_dir / "integrations.json")
    values = {
        "AIDLEARNING_DOCKER_BACKEND_PORT": str(
            _coerce_port(system.get("backend_port"), DEFAULT_BACKEND_PORT)
        ),
        "AIDLEARNING_DOCKER_FRONTEND_PORT": str(
            _coerce_port(system.get("frontend_port"), DEFAULT_FRONTEND_PORT)
        ),
        "AIDLEARNING_DOCKER_POCKETBASE_PORT": str(
            _coerce_port(integrations.get("pocketbase_port"), DEFAULT_POCKETBASE_PORT)
        ),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 由 scripts/docker_compose.py 根据 data/user/settings/*.json 自动生成。",
        "# 请勿手动编辑；请修改 system.json/integrations.json。",
    ]
    lines.extend(f"{key}={value}" for key, value in values.items())
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return values


def _compose_command(args: list[str]) -> list[str]:
    docker = shutil.which("docker")
    if not docker:
        raise SystemExit("docker was not found on PATH")
    return [docker, "compose", "--env-file", str(DOCKER_ENV_PATH), *args]


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if not args:
        args = ["up", "-d"]

    values = render_docker_env()
    print(
        "Docker settings: "
        f"backend={values['AIDLEARNING_DOCKER_BACKEND_PORT']} "
        f"frontend={values['AIDLEARNING_DOCKER_FRONTEND_PORT']} "
        f"pocketbase={values['AIDLEARNING_DOCKER_POCKETBASE_PORT']}",
        file=sys.stderr,
    )

    env = os.environ.copy()
    # 保持 Docker 执行不受宿主机进程环境变量覆盖的影响。
    for key in (
        "BACKEND_PORT",
        "FRONTEND_PORT",
        "POCKETBASE_PORT",
        "AUTH_ENABLED",
        "POCKETBASE_URL",
        "NEXT_PUBLIC_API_BASE",
        "NEXT_PUBLIC_API_BASE_EXTERNAL",
    ):
        env.pop(key, None)

    result = subprocess.run(_compose_command(args), cwd=str(PROJECT_ROOT), env=env, check=False)
    return int(result.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
