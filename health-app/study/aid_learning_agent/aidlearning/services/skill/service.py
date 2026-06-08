"""
SkillService
============

从 ``data/user/workspace/skills/`` 加载用户编写的 SKILL.md 文件。

每个技能位于自己的目录中：

    data/user/workspace/skills/<name>/SKILL.md

文件以 YAML frontmatter 块开头，包含 ``name``、``description``
（以及可选的 ``triggers`` 和 ``tags``），后跟 Markdown 正文，
当技能激活时会被原样注入到聊天系统提示中。

技能目录旁的 ``.tags.json`` 小文件保存了规范的用户管理标签词汇表，
以便标签可以独立于使用它们的技能进行创建、重命名或删除。
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import re
import shutil
from typing import Any

import yaml

from aidlearning.services.path_service import get_path_service

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
_TAG_RE = re.compile(r"^[a-z0-9][a-z0-9\- _]{0,31}$")
_DEFAULT_TAGS: tuple[str, ...] = ("style", "tool")
_TAGS_FILE = ".tags.json"


@dataclass(slots=True)
class SkillInfo:
    name: str
    description: str
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "tags": list(self.tags),
        }


@dataclass(slots=True)
class SkillDetail:
    name: str
    description: str
    content: str
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "content": self.content,
            "tags": list(self.tags),
        }


class SkillNotFoundError(Exception):
    pass


class SkillExistsError(Exception):
    pass


class InvalidSkillNameError(Exception):
    pass


class InvalidTagError(Exception):
    pass


class TagNotFoundError(Exception):
    pass


class TagExistsError(Exception):
    pass


class SkillService:
    """用户工作空间下 SKILL.md 文件的增删改查与选择。"""

    def __init__(self, root: Path | None = None) -> None:
        self._root = root or (get_path_service().get_workspace_dir() / "skills")

    @property
    def root(self) -> Path:
        return self._root

    # ── 路径辅助方法 ────────────────────────────────────────────────────

    def _validate_name(self, name: str) -> str:
        candidate = (name or "").strip().lower()
        if not _NAME_RE.match(candidate):
            raise InvalidSkillNameError("Skill name must match ^[a-z0-9][a-z0-9-]{0,63}$")
        return candidate

    def _skill_dir(self, name: str) -> Path:
        return self._root / self._validate_name(name)

    def _skill_file(self, name: str) -> Path:
        return self._skill_dir(name) / "SKILL.md"

    # ── 标签辅助方法 ─────────────────────────────────────────────────────

    @staticmethod
    def _normalize_tag(raw: Any) -> str:
        candidate = str(raw or "").strip().lower()
        if not candidate:
            raise InvalidTagError("Tag name must not be empty.")
        if not _TAG_RE.match(candidate):
            raise InvalidTagError(
                "Tag must match ^[a-z0-9][a-z0-9- _]{0,31}$ (letters/digits/dash/space/underscore)."
            )
        return candidate

    @staticmethod
    def _dedupe_tags(values: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for v in values:
            if v in seen:
                continue
            seen.add(v)
            out.append(v)
        return out

    def _tags_path(self) -> Path:
        return self._root / _TAGS_FILE

    def _read_tag_vocab(self) -> list[str]:
        path = self._tags_path()
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        raw = data.get("tags") if isinstance(data, dict) else None
        if not isinstance(raw, list):
            return []
        out: list[str] = []
        for item in raw:
            try:
                out.append(self._normalize_tag(item))
            except InvalidTagError:
                continue
        return self._dedupe_tags(out)

    def _write_tag_vocab(self, tags: list[str]) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        payload = {"tags": self._dedupe_tags(tags)}
        self._tags_path().write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _tags_from_meta(self, meta: dict[str, Any]) -> list[str]:
        raw = meta.get("tags")
        if not isinstance(raw, list):
            return []
        out: list[str] = []
        for item in raw:
            try:
                out.append(self._normalize_tag(item))
            except InvalidTagError:
                continue
        return self._dedupe_tags(out)

    def _collect_skill_tags(self) -> list[str]:
        """扫描所有技能并收集其 frontmatter 中的标签。"""
        if not self._root.exists():
            return []
        found: list[str] = []
        for entry in sorted(self._root.iterdir()):
            if not entry.is_dir():
                continue
            try:
                detail = self.get_detail(entry.name)
            except (SkillNotFoundError, InvalidSkillNameError):
                continue
            for tag in detail.tags:
                if tag not in found:
                    found.append(tag)
        return found

    def _ensure_initialized_vocab(self) -> list[str]:
        """首次访问时播种默认标签，并回填技能中发现的所有标签。"""
        vocab = self._read_tag_vocab()
        existed = self._tags_path().exists()
        if not existed:
            vocab = list(_DEFAULT_TAGS)
        union = self._dedupe_tags(vocab + self._collect_skill_tags())
        if not existed or union != vocab:
            self._write_tag_vocab(union)
        return union

    # ── 解析 ─────────────────────────────────────────────────────────

    @staticmethod
    def _parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
        match = _FRONTMATTER_RE.match(content)
        if not match:
            return {}, content
        raw = match.group(1)
        body = content[match.end() :]
        try:
            data = yaml.safe_load(raw) or {}
        except yaml.YAMLError:
            data = {}
        if not isinstance(data, dict):
            data = {}
        return data, body

    def _load_info(self, name: str) -> SkillInfo | None:
        file = self._skill_file(name)
        if not file.exists():
            return None
        try:
            text = file.read_text(encoding="utf-8")
        except OSError:
            return None
        meta, _ = self._parse_frontmatter(text)
        description = str(meta.get("description") or "").strip()
        tags = self._tags_from_meta(meta)
        return SkillInfo(name=name, description=description, tags=tags)

    # ── 公开读取 API ─────────────────────────────────────────────────

    def list_skills(self) -> list[SkillInfo]:
        if not self._root.exists():
            return []
        out: list[SkillInfo] = []
        for entry in sorted(self._root.iterdir()):
            if not entry.is_dir():
                continue
            try:
                info = self._load_info(entry.name)
            except InvalidSkillNameError:
                continue
            if info is not None:
                out.append(info)
        return out

    def get_detail(self, name: str) -> SkillDetail:
        file = self._skill_file(name)
        if not file.exists():
            raise SkillNotFoundError(name)
        text = file.read_text(encoding="utf-8")
        meta, _ = self._parse_frontmatter(text)
        description = str(meta.get("description") or "").strip()
        tags = self._tags_from_meta(meta)
        return SkillDetail(name=name, description=description, content=text, tags=tags)

    def load_for_context(self, names: list[str]) -> str:
        """将选中的技能渲染为单一的系统提示块。

        去除 frontmatter；正文在共享标题下拼接，
        使 LLM 将该部分视为权威的行为指导。
        """
        if not names:
            return ""
        parts: list[str] = []
        for name in names:
            try:
                detail = self.get_detail(name)
            except (SkillNotFoundError, InvalidSkillNameError):
                continue
            _, body = self._parse_frontmatter(detail.content)
            body = body.strip()
            if not body:
                continue
            parts.append(f"### Skill: {detail.name}\n\n{body}")
        if not parts:
            return ""
        return (
            "## Active Skills\n"
            "Follow the playbooks below. They override generic defaults.\n\n"
            + "\n\n---\n\n".join(parts)
        )

    # ── 自动选择（基于关键词，无 LLM）─────────────────────────────

    def auto_select(self, user_message: str, limit: int = 1) -> list[str]:
        """通过关键词评分选择与消息最相关的技能。

        评分规则（简单且可预测）：
          - 消息中出现的 frontmatter ``triggers`` 术语 +3 分。
          - 消息中出现的 ``description`` 非停用词 +1 分。
        """
        message = (user_message or "").lower()
        if not message.strip():
            return []
        scored: list[tuple[int, str]] = []
        for entry in sorted((self._root.iterdir() if self._root.exists() else [])):
            if not entry.is_dir():
                continue
            try:
                detail = self.get_detail(entry.name)
            except (SkillNotFoundError, InvalidSkillNameError):
                continue
            meta, _ = self._parse_frontmatter(detail.content)
            score = 0
            for trig in meta.get("triggers") or []:
                term = str(trig).strip().lower()
                if term and term in message:
                    score += 3
            for token in re.findall(r"[\w\u4e00-\u9fff]{3,}", detail.description.lower()):
                if token in message:
                    score += 1
            if score > 0:
                scored.append((score, detail.name))
        scored.sort(reverse=True)
        return [name for _, name in scored[: max(0, limit)]]

    # ── 公开写入 API ────────────────────────────────────────────────

    def create(
        self,
        name: str,
        description: str,
        content: str,
        tags: list[str] | None = None,
    ) -> SkillInfo:
        slug = self._validate_name(name)
        target_dir = self._skill_dir(slug)
        if target_dir.exists():
            raise SkillExistsError(slug)
        clean_tags = self._validate_tag_list(tags)
        body = self._normalize_content(
            slug,
            description,
            content,
            tags=clean_tags,
        )
        target_dir.mkdir(parents=True, exist_ok=False)
        self._skill_file(slug).write_text(body, encoding="utf-8")
        self._merge_tags_into_vocab(clean_tags)
        return SkillInfo(name=slug, description=description.strip(), tags=clean_tags)

    def update(
        self,
        name: str,
        *,
        description: str | None = None,
        content: str | None = None,
        rename_to: str | None = None,
        tags: list[str] | None = None,
    ) -> SkillInfo:
        slug = self._validate_name(name)
        target_dir = self._skill_dir(slug)
        if not target_dir.exists():
            raise SkillNotFoundError(slug)

        if content is not None:
            text = content
        else:
            text = self._skill_file(slug).read_text(encoding="utf-8")

        if description is not None:
            text = self._rewrite_frontmatter(text, description=description.strip())

        clean_tags: list[str] | None = None
        if tags is not None:
            clean_tags = self._validate_tag_list(tags)
            text = self._rewrite_frontmatter(text, tags=clean_tags)

        meta, _ = self._parse_frontmatter(text)
        final_description = str(meta.get("description") or "").strip()
        final_tags = self._tags_from_meta(meta)

        if rename_to and rename_to != slug:
            new_slug = self._validate_name(rename_to)
            new_dir = self._skill_dir(new_slug)
            if new_dir.exists():
                raise SkillExistsError(new_slug)
            text = self._rewrite_frontmatter(text, name=new_slug)
            target_dir.rename(new_dir)
            slug = new_slug
            target_dir = new_dir

        self._skill_file(slug).write_text(text, encoding="utf-8")
        if clean_tags is not None:
            self._merge_tags_into_vocab(clean_tags)
        return SkillInfo(name=slug, description=final_description, tags=final_tags)

    def delete(self, name: str) -> None:
        slug = self._validate_name(name)
        target_dir = self._skill_dir(slug)
        if not target_dir.exists():
            raise SkillNotFoundError(slug)
        shutil.rmtree(target_dir)

    # ── 标签管理 API ─────────────────────────────────────────────

    def list_tags(self) -> list[str]:
        return self._ensure_initialized_vocab()

    def create_tag(self, name: str) -> str:
        tag = self._normalize_tag(name)
        vocab = self._ensure_initialized_vocab()
        if tag in vocab:
            raise TagExistsError(tag)
        self._write_tag_vocab(vocab + [tag])
        return tag

    def rename_tag(self, old: str, new: str) -> str:
        old_tag = self._normalize_tag(old)
        new_tag = self._normalize_tag(new)
        vocab = self._ensure_initialized_vocab()
        if old_tag not in vocab:
            raise TagNotFoundError(old_tag)
        if new_tag != old_tag and new_tag in vocab:
            raise TagExistsError(new_tag)
        if new_tag == old_tag:
            return old_tag
        new_vocab = [new_tag if t == old_tag else t for t in vocab]
        self._write_tag_vocab(new_vocab)
        # 级联：重写使用了旧标签的每个技能的 frontmatter。
        self._replace_tag_in_skills(old_tag, new_tag)
        return new_tag

    def delete_tag(self, name: str) -> None:
        tag = self._normalize_tag(name)
        vocab = self._ensure_initialized_vocab()
        if tag not in vocab:
            raise TagNotFoundError(tag)
        new_vocab = [t for t in vocab if t != tag]
        self._write_tag_vocab(new_vocab)
        self._replace_tag_in_skills(tag, None)

    # ── 内部标签辅助方法 ───────────────────────────────────────────

    def _validate_tag_list(self, tags: list[str] | None) -> list[str]:
        if not tags:
            return []
        cleaned: list[str] = []
        for raw in tags:
            try:
                cleaned.append(self._normalize_tag(raw))
            except InvalidTagError:
                continue
        return self._dedupe_tags(cleaned)

    def _merge_tags_into_vocab(self, new_tags: list[str]) -> None:
        if not new_tags:
            # 仍然触发初始化，使词汇表文件在首次写入后存在。
            self._ensure_initialized_vocab()
            return
        vocab = self._ensure_initialized_vocab()
        merged = self._dedupe_tags(vocab + new_tags)
        if merged != vocab:
            self._write_tag_vocab(merged)

    def _replace_tag_in_skills(self, old_tag: str, new_tag: str | None) -> None:
        if not self._root.exists():
            return
        for entry in sorted(self._root.iterdir()):
            if not entry.is_dir():
                continue
            try:
                detail = self.get_detail(entry.name)
            except (SkillNotFoundError, InvalidSkillNameError):
                continue
            if old_tag not in detail.tags:
                continue
            updated: list[str] = []
            for t in detail.tags:
                if t == old_tag:
                    if new_tag and new_tag not in updated:
                        updated.append(new_tag)
                elif t not in updated:
                    updated.append(t)
            new_text = self._rewrite_frontmatter(detail.content, tags=updated)
            self._skill_file(entry.name).write_text(new_text, encoding="utf-8")

    # ── 内容辅助方法 ────────────────────────────────────────────────

    def _normalize_content(
        self,
        name: str,
        description: str,
        content: str,
        *,
        tags: list[str] | None = None,
    ) -> str:
        """确保保存的文件具有包含 ``name``/``description`` 的有效 frontmatter 块。

        如果用户提供的 ``content`` 已有 frontmatter，则修补 ``name``、
        ``description`` 和 ``tags`` 字段；否则合成一个头部。
        """
        text = content if content is not None else ""
        if _FRONTMATTER_RE.match(text):
            text = self._rewrite_frontmatter(
                text,
                name=name,
                description=description.strip(),
                tags=tags,
            )
            return text
        payload: dict[str, Any] = {
            "name": name,
            "description": description.strip(),
        }
        if tags:
            payload["tags"] = list(tags)
        header = yaml.safe_dump(
            payload,
            sort_keys=False,
            allow_unicode=True,
        ).strip()
        body = text.lstrip()
        return f"---\n{header}\n---\n\n{body}".rstrip() + "\n"

    def _rewrite_frontmatter(
        self,
        text: str,
        *,
        name: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
    ) -> str:
        meta, body = self._parse_frontmatter(text)
        if name is not None:
            meta["name"] = name
        if description is not None:
            meta["description"] = description
        if tags is not None:
            if tags:
                meta["tags"] = list(tags)
            elif "tags" in meta:
                meta.pop("tags", None)
        if not meta:
            return text
        header = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True).strip()
        return f"---\n{header}\n---\n\n{body.lstrip()}".rstrip() + "\n"


_instances: dict[str, SkillService] = {}


def get_skill_service() -> SkillService:
    root = (get_path_service().get_workspace_dir() / "skills").resolve()
    key = str(root)
    if key not in _instances:
        _instances[key] = SkillService(root=root)
    return _instances[key]


__all__ = [
    "InvalidSkillNameError",
    "InvalidTagError",
    "SkillDetail",
    "SkillExistsError",
    "SkillInfo",
    "SkillNotFoundError",
    "SkillService",
    "TagExistsError",
    "TagNotFoundError",
    "get_skill_service",
]
