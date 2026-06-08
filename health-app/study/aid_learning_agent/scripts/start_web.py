#!/usr/bin/env python
"""``aidlearning start`` 的兼容性包装器。"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aidlearning.runtime.launcher import start  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="启动 AidLearning Web。")
    parser.add_argument(
        "--home",
        type=Path,
        default=None,
        help="运行时工作区根目录。默认为当前目录。",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    start(home=build_parser().parse_args(argv).home)


if __name__ == "__main__":
    main()
