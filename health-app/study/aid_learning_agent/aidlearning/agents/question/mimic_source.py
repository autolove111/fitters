"""试卷 → QuizTemplate 适配器，用于模拟模式。

封装（同步、IO 密集的）MinerU PDF 解析器和基于规则的问题提取器，
以便能力层可以通过其 ``templates_override`` 入口将模拟模板交给 :class:`QuestionPipeline`。

本模块故意很窄：它仅将 PDF（或先前解析的工作目录）转换为
:class:`QuizTemplate` 列表。流式进度、提示词组装、LLM 调用和结果发送
都留在管线/能力层。
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from aidlearning.agents.question.pipeline import QuizTemplate
from aidlearning.tools.question.pdf_parser import parse_pdf_with_mineru
from aidlearning.tools.question.question_extractor import extract_questions_from_paper

logger = logging.getLogger(__name__)


_DEFAULT_DIFFICULTY = "medium"
_DEFAULT_QUESTION_TYPE = "written"
_TOPIC_CLIP_CHARS = 240


async def parse_exam_paper_to_templates(
    paper_path: str | Path,
    *,
    max_questions: int,
    paper_mode: str,
    output_dir: str | Path,
) -> tuple[list[QuizTemplate], dict[str, str]]:
    """将试卷解析为模拟模式 ``QuizTemplate`` 列表。

    ``paper_mode``：

    * ``"upload"``  — ``paper_path`` 是新上传的 PDF；MinerU 在 ``output_dir``
      下解析它，我们选取最新的子目录。
    * ``"parsed"``  — ``paper_path`` 是先前解析的工作目录（已包含 MinerU 输出）；
      跳过解析步骤。

    返回 ``(templates, trace)``。``trace`` 携带路径和计数用于包含在最终的
    ``stream.result`` 信封中。解析或提取失败时抛出 ``RuntimeError``
    —— 调用方发送面向用户的错误。
    """
    return await asyncio.to_thread(
        _parse_sync,
        Path(paper_path),
        int(max_questions),
        str(paper_mode),
        Path(output_dir),
    )


def _parse_sync(
    paper_path: Path,
    max_questions: int,
    paper_mode: str,
    output_base: Path,
) -> tuple[list[QuizTemplate], dict[str, str]]:
    output_base.mkdir(parents=True, exist_ok=True)

    if paper_mode == "parsed":
        working_dir = paper_path
    else:
        ok = parse_pdf_with_mineru(str(paper_path), str(output_base))
        if not ok:
            raise RuntimeError("Failed to parse exam paper with MinerU")
        subdirs = sorted(
            [d for d in output_base.iterdir() if d.is_dir()],
            key=lambda d: d.stat().st_mtime,
            reverse=True,
        )
        if not subdirs:
            raise RuntimeError("No parsed exam directory found after MinerU parsing")
        working_dir = subdirs[0]

    json_files = list(working_dir.glob("*_questions.json"))
    if not json_files:
        ok = extract_questions_from_paper(str(working_dir), output_dir=None)
        if not ok:
            raise RuntimeError("Failed to extract questions from parsed exam")
        json_files = list(working_dir.glob("*_questions.json"))
    if not json_files:
        raise RuntimeError("Question extraction output not found")

    with json_files[0].open(encoding="utf-8") as fh:
        payload = json.load(fh)
    questions = payload.get("questions") or []
    if max_questions > 0:
        questions = questions[:max_questions]

    templates: list[QuizTemplate] = []
    for idx, item in enumerate(questions, 1):
        if not isinstance(item, dict):
            continue
        q_text = str(item.get("question_text") or "").strip()
        if not q_text:
            continue
        templates.append(
            QuizTemplate(
                question_id=f"q_{idx}",
                topic=q_text[:_TOPIC_CLIP_CHARS],
                question_type=str(item.get("question_type") or _DEFAULT_QUESTION_TYPE).lower(),
                difficulty=_DEFAULT_DIFFICULTY,
                source="mimic",
                reference_question=q_text,
                reference_answer=str(item.get("answer") or "").strip() or None,
            )
        )

    trace = {
        "paper_dir": str(working_dir),
        "question_file": str(json_files[0]),
        "template_count": str(len(templates)),
    }
    return templates, trace


__all__ = ["parse_exam_paper_to_templates"]
