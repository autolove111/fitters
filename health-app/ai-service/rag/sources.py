from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RAGSource:
    source: str
    title: str
    url: str
    authority_level: int
    topics: list[str]
    language: str
    source_path: str
    source_doc_hash: str
    text: str


def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if value.isdigit():
        return int(value)
    return value.strip("\"'")


def parse_frontmatter(raw: str) -> tuple[dict[str, Any], str]:
    if not raw.startswith("---"):
        return {}, raw
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return {}, raw
    meta_text = parts[1]
    body = parts[2].strip()
    metadata: dict[str, Any] = {}
    current_list_key: str | None = None
    for line in meta_text.splitlines():
        if not line.strip():
            continue
        if line.startswith("  - ") and current_list_key:
            metadata.setdefault(current_list_key, []).append(line[4:].strip())
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value:
            metadata[key] = _parse_scalar(value)
            current_list_key = None
        else:
            metadata[key] = []
            current_list_key = key
    return metadata, body


def markdown_to_plain_text(text: str) -> str:
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"!\[[^\]]*]\([^)]*\)", " ", text)
    text = re.sub(r"\[([^\]]+)]\([^)]*\)", r"\1", text)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.M)
    text = re.sub(r"[*_~>#]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def load_sources(directory: str | Path) -> list[RAGSource]:
    root = Path(directory)
    if not root.exists():
        return []
    sources: list[RAGSource] = []
    for path in sorted(root.glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        metadata, body = parse_frontmatter(raw)
        plain_text = markdown_to_plain_text(body)
        doc_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        topics = metadata.get("topics") or []
        if not isinstance(topics, list):
            topics = [str(topics)]
        sources.append(
            RAGSource(
                source=str(metadata.get("source") or path.stem),
                title=str(metadata.get("title") or path.stem.replace("_", " ").title()),
                url=str(metadata.get("url") or ""),
                authority_level=int(metadata.get("authority_level") or 3),
                topics=[str(topic) for topic in topics],
                language=str(metadata.get("language") or "en"),
                source_path=str(path),
                source_doc_hash=doc_hash,
                text=plain_text,
            )
        )
    return sources
