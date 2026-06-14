#!/usr/bin/env python
"""AidLearning 配置引导。

此脚本仅配置 ``data/user/settings`` 下的运行时文件。
它不会安装 Python 包、Node 依赖或启动 Web 应用。
日常使用请优先选择：

    aidlearning init
    aidlearning start
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aidlearning_cli.init_cmd import run_init  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="创建或更新 data/user/settings 下的 AidLearning 配置。",
    )
    parser.add_argument(
        "--cli",
        action="store_true",
        help="配置为仅 CLI 模式，跳过 Web 端口提示。",
    )
    parser.add_argument(
        "--home",
        type=Path,
        default=None,
        help="运行时工作区根目录。默认为当前目录。",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    print("AidLearning settings tour")
    print("Writing configuration to data/user/settings; no dependencies will be installed.")
    run_init(cli_only=args.cli, home=args.home)
    if args.cli:
        print("\nNext: aidlearning chat")
    else:
        print("\nNext: aidlearning start")


if __name__ == "__main__":
    main()
