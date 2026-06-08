"""Memory v3 API — 工作台后端。

三层记忆，三种模式（更新 / 审计 / 去重）。长时间运行的任务
由 runs 管理器持有，刷新页面或导航离开不会中断；客户端通过
轮询 /runs/{id}/events?since=N 重新接入。

- GET  /overview                              → 全部 11 个文档状态 + L1 积压
- GET  /doc/{layer}/{key}                     → 原始 MD
- GET  /doc/{layer}/{key}/lines               → 带行号的视图
- PUT  /doc/{layer}/{key}                     → 用户编辑保存
- DELETE /doc/{layer}/{key}/entry/{id}        → 删除单条记录
- POST /runs/start                            → 启动更新/审计/去重；返回 run_id
- GET  /runs/{id}                             → 运行状态
- GET  /runs/{id}/events?since=N              → 从游标 N 开始的 SSE 回放事件
- POST /runs/{id}/cancel                      → 协作式取消
- POST /runs/{id}/undo                        → 恢复最近一次运行的写入
- GET  /runs?layer=L2&key=chat                → 单个文档的活跃+近期运行
- GET  /settings                              → memory: 设置子树
- PUT  /settings                              → 保存 memory: 设置子树
- GET  /trace/{surface}                       → 分页 L1 事件
- DELETE /trace/{surface}/day/{date}          → 删除某天的追踪记录
- DELETE /trace/{surface}                     → 删除某 surface 的所有追踪
- GET  /backup                                → 列出 v1 迁移备份目录（如有）

旧版按模式划分的端点（POST /doc/{layer}/{key}/update 等）
暂时保留为薄包装，启动运行并流式传输事件——旧客户端仍可正常工作。
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import date as date_cls
import json
import logging
import re
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from aidlearning.memory import (
    L3_SLOTS,
    SURFACES,
    Surface,
    get_memory_store,
)
from aidlearning.memory.shared import paths

_ENTRY_ID_RE = re.compile(r"^m_[0-9A-HJKMNP-TV-Z]{26}$")

logger = logging.getLogger(__name__)
router = APIRouter()

Layer = Literal["L2", "L3"]


# ── 辅助函数 ──────────────────────────────────────────────────────────────


def _validate_doc_key(layer: Layer, key: str) -> None:
    if layer == "L2" and key not in SURFACES:
        raise HTTPException(status_code=404, detail=f"unknown surface {key!r}")
    if layer == "L3" and key not in L3_SLOTS:
        raise HTTPException(status_code=404, detail=f"unknown L3 slot {key!r}")


def _validate_layer(layer: str) -> Layer:
    if layer not in {"L2", "L3"}:
        raise HTTPException(status_code=400, detail="layer must be L2 or L3")
    return layer  # type: ignore[return-value]


def _validate_surface(surface: str) -> Surface:
    if surface not in SURFACES:
        raise HTTPException(status_code=404, detail=f"unknown surface {surface!r}")
    return surface  # type: ignore[return-value]


# ── 概览 / 列表 ──────────────────────────────────────────────────────────


@router.get("/overview")
async def get_overview():
    store = get_memory_store()
    rows = [asdict(r) for r in store.overview()]
    backup_dir = paths.backup_root()
    backups: list[str] = []
    if backup_dir.exists():
        backups = sorted(p.name for p in backup_dir.iterdir() if p.is_dir())
    return {"docs": rows, "backups": backups}


@router.get("/resolve_entry/{entry_id}")
async def resolve_entry(entry_id: str):
    """查找此条目 ID 所属的 L2 文档。

    L3 文档通过 m_<ULID> 条目 ID 引用 L2 条目；工作台 UI 使用此解析器
    将 L3 脚注点击转换为导航到正确的 L2 surface + 滚动到锚点。

    按顺序扫描七个 L2 md 文件；第一个匹配即返回。如果没有任何 L2 文档
    包含该 ID（如条目已删除或 ID 已过期），返回 404。
    """
    if not _ENTRY_ID_RE.match(entry_id):
        raise HTTPException(status_code=400, detail="not a valid entry id")
    from aidlearning.memory.long_term.document import parse

    for surface in SURFACES:
        path = paths.l2_file(surface)
        if not path.exists():
            continue
        try:
            doc = parse(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 — malformed L2 should not 500 the resolver
            continue
        for entry in doc.all_entries():
            if entry.id == entry_id:
                return {"layer": "L2", "key": surface, "entry_id": entry_id}
    raise HTTPException(status_code=404, detail="entry not found in any L2 doc")


@router.get("/backup")
async def list_backups():
    backup_dir = paths.backup_root()
    if not backup_dir.exists():
        return {"backups": []}
    out: list[dict] = []
    for entry in sorted(backup_dir.iterdir()):
        if entry.is_dir():
            files = sorted(p.name for p in entry.iterdir())
            out.append({"name": entry.name, "files": files})
    return {"backups": out}


# ── 文档 读取 / 写入 / 删除 ────────────────────────────────────────────────


@router.get("/doc/{layer}/{key}")
async def get_doc(layer: str, key: str):
    lyr = _validate_layer(layer)
    _validate_doc_key(lyr, key)
    return {"layer": lyr, "key": key, "content": get_memory_store().read_raw(lyr, key)}


class DocWriteRequest(BaseModel):
    content: str


@router.put("/doc/{layer}/{key}")
async def put_doc(layer: str, key: str, payload: DocWriteRequest):
    lyr = _validate_layer(layer)
    _validate_doc_key(lyr, key)
    await get_memory_store().overwrite_doc(lyr, key, payload.content)
    return {"layer": lyr, "key": key, "saved": True}


@router.delete("/doc/{layer}/{key}/entry/{entry_id}")
async def delete_entry(layer: str, key: str, entry_id: str):
    lyr = _validate_layer(layer)
    _validate_doc_key(lyr, key)
    ok = await get_memory_store().delete_entry(lyr, key, entry_id)
    if not ok:
        raise HTTPException(status_code=404, detail="entry not found")
    return {"layer": lyr, "key": key, "deleted": entry_id}


@router.post("/doc/{layer}/{key}/reset")
async def reset_doc(layer: str, key: str):
    """清除文档及其元数据附属文件，使下次更新从头开始。

    破坏性操作——调用方已确认。返回后 .md 文件被删除，
    且 seen_entity_refs 集合被清空，因此后续的 run_update
    会重新摄入所有 L1 实体，而不是视为已处理。

    当该文档有活跃的整合器运行时拒绝执行；调用方应先取消。
    """
    lyr = _validate_layer(layer)
    _validate_doc_key(lyr, key)

    from aidlearning.memory.consolidator.runs import get_run_manager

    if get_run_manager().active_for(lyr, key) is not None:
        raise HTTPException(
            status_code=409,
            detail="cancel the active run before resetting this doc",
        )

    from aidlearning.memory.consolidator import meta as meta_mod

    doc_path = paths.l2_file(key) if lyr == "L2" else paths.l3_file(key)  # type: ignore[arg-type]
    meta_path = (
        meta_mod.l2_meta_path(key)  # type: ignore[arg-type]
        if lyr == "L2"
        else meta_mod.l3_meta_path(key)  # type: ignore[arg-type]
    )

    removed_doc = False
    removed_meta = False
    try:
        if doc_path.exists():
            doc_path.unlink()
            removed_doc = True
        if meta_path.exists():
            meta_path.unlink()
            removed_meta = True
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"reset failed: {exc}") from exc

    return {
        "layer": lyr,
        "key": key,
        "reset": True,
        "removed_doc": removed_doc,
        "removed_meta": removed_meta,
    }


# ── 文档更新（SSE 流式整合器）──────────────────────────────────────────────


class LLMSelectionPayload(BaseModel):
    profile_id: str
    model_id: str


class RunStartRequest(BaseModel):
    layer: str
    key: str
    mode: Literal["update", "audit", "dedup", "merge"]
    language: str = "en"
    budget: int | None = None
    iterations: int | None = None
    llm_selection: LLMSelectionPayload | None = None


def _runner_for(req: RunStartRequest):
    """返回请求模式对应的 async on_event → None 运行器。"""
    from aidlearning.memory.consolidator import (
        run_audit,
        run_dedup,
        run_merge,
        run_update,
    )

    selection = (
        {"profile_id": req.llm_selection.profile_id, "model_id": req.llm_selection.model_id}
        if req.llm_selection
        else None
    )

    if req.mode == "update":

        async def go(on_event):
            await run_update(
                req.layer,
                req.key,
                language=req.language,
                budget=req.budget,
                llm_selection=selection,
                on_event=on_event,
            )

        return go
    if req.mode == "audit":

        async def go(on_event):
            await run_audit(
                req.layer,
                req.key,
                language=req.language,
                budget=req.budget,
                llm_selection=selection,
                on_event=on_event,
            )

        return go
    if req.mode == "dedup":

        async def go(on_event):
            await run_dedup(
                req.layer,
                req.key,
                language=req.language,
                iterations=req.iterations,
                llm_selection=selection,
                on_event=on_event,
            )

        return go
    if req.mode == "merge":

        async def go(on_event):
            await run_merge(
                req.layer,
                req.key,
                language=req.language,
                on_event=on_event,
            )

        return go
    raise HTTPException(status_code=400, detail=f"unknown mode {req.mode!r}")


@router.post("/runs/start")
async def start_run(req: RunStartRequest):
    """启动一个整合器模式并返回运行句柄。

    运行在客户端断开后仍可继续；通过
    GET /runs/{id}/events?since=N 重新连接。
    """
    lyr = _validate_layer(req.layer)
    _validate_doc_key(lyr, req.key)
    if lyr == "L3" and req.key == "preferences" and req.mode not in ("dedup", "merge"):
        raise HTTPException(
            status_code=405,
            detail="preferences is written by the write_memory tool, not consolidated",
        )
    from aidlearning.memory.consolidator.runs import (
        RunBusyError,
        get_run_manager,
    )

    manager = get_run_manager()
    runner = _runner_for(req)
    selection = (
        {"profile_id": req.llm_selection.profile_id, "model_id": req.llm_selection.model_id}
        if req.llm_selection
        else None
    )
    try:
        run = await manager.start(
            layer=lyr,
            key=req.key,
            mode=req.mode,
            runner=runner,
            params={
                "budget": req.budget,
                "iterations": req.iterations,
                "language": req.language,
                "llm_selection": selection,
            },
            language=req.language,
        )
    except RunBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return run.to_dict()


@router.get("/runs/{run_id}")
async def get_run(run_id: str):
    from aidlearning.memory.consolidator.runs import get_run_manager

    run = get_run_manager().get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="unknown run_id")
    return run.to_dict()


@router.post("/runs/{run_id}/cancel")
async def cancel_run(run_id: str):
    from aidlearning.memory.consolidator.runs import get_run_manager

    ok = await get_run_manager().cancel(run_id)
    if not ok:
        raise HTTPException(status_code=409, detail="not active")
    return {"run_id": run_id, "cancelled": True}


@router.post("/runs/{run_id}/undo")
async def undo_run_edit(run_id: str):
    from aidlearning.memory.consolidator.runs import (
        RunBusyError,
        get_run_manager,
    )

    manager = get_run_manager()
    try:
        event = await manager.undo_last(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown run_id")
    except RunBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if event is None:
        raise HTTPException(status_code=409, detail="nothing to undo")
    run = manager.get(run_id)
    return {
        "run_id": run_id,
        "undone": True,
        "undo_count": len(run.undo_stack) if run else 0,
        "event": {"seq": event.seq, "ts": event.ts, **event.payload},
    }


@router.get("/runs")
async def list_runs(layer: str | None = None, key: str | None = None):
    from aidlearning.memory.consolidator.runs import get_run_manager

    lyr = _validate_layer(layer) if layer is not None else None
    if lyr and key is not None:
        _validate_doc_key(lyr, key)
    runs = get_run_manager().list_for(layer=lyr, key=key)
    return {"runs": [r.to_dict() for r in runs]}


@router.get("/runs/{run_id}/events")
async def stream_run_events(run_id: str, since: int = 0):
    """从 since（不含）开始 SSE 回放事件直到运行结束。

    刷新后重新连接：传入之前收到的最大 seq。
    管理器回放缓冲尾部，然后阻塞等待新事件直到运行达到终态。
    """
    from aidlearning.memory.consolidator.runs import get_run_manager

    manager = get_run_manager()
    run = manager.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="unknown run_id")

    async def producer():
        cursor = max(0, since)
        # 初始回填（如有）作为一批预先发送。
        while True:
            events = await manager.wait_for_events(run, since=cursor)
            for ev in events:
                yield (
                    "data: "
                    + json.dumps(
                        {"seq": ev.seq, "ts": ev.ts, **ev.payload},
                        ensure_ascii=False,
                    )
                    + "\n\n"
                )
            cursor = max(cursor, run.events[-1].seq + 1 if run.events else cursor)
            if not run.active:
                # 排空 wait 返回到此刻之间到达的最后一批事件。
                final = run.events[cursor:]
                for ev in final:
                    yield (
                        "data: "
                        + json.dumps(
                            {"seq": ev.seq, "ts": ev.ts, **ev.payload},
                            ensure_ascii=False,
                        )
                        + "\n\n"
                    )
                break

    return StreamingResponse(producer(), media_type="text/event-stream")


# ── 旧版按模式划分的端点（保留为 /runs/start 的薄包装）───────────────────


def _legacy_run_stream(req: RunStartRequest) -> StreamingResponse:
    """旧版约定：POST /doc/{layer}/{key}/<mode> 内联流式传输事件。"""
    from aidlearning.memory.consolidator.runs import (
        RunBusyError,
        get_run_manager,
    )

    async def producer():
        manager = get_run_manager()
        runner = _runner_for(req)
        selection = (
            {"profile_id": req.llm_selection.profile_id, "model_id": req.llm_selection.model_id}
            if req.llm_selection
            else None
        )
        try:
            run = await manager.start(
                layer=req.layer,
                key=req.key,
                mode=req.mode,
                runner=runner,
                params={
                    "budget": req.budget,
                    "iterations": req.iterations,
                    "language": req.language,
                    "llm_selection": selection,
                },
                language=req.language,
            )
        except RunBusyError as exc:
            yield (
                "data: "
                + json.dumps({"stage": "error", "message": str(exc)}, ensure_ascii=False)
                + "\n\n"
            )
            return
        cursor = 0
        while True:
            events = await manager.wait_for_events(run, since=cursor)
            for ev in events:
                yield (
                    "data: "
                    + json.dumps({**ev.payload, "seq": ev.seq}, ensure_ascii=False)
                    + "\n\n"
                )
                cursor = ev.seq + 1
            if not run.active:
                break

    return StreamingResponse(producer(), media_type="text/event-stream")


class UpdateRequest(BaseModel):
    language: str = "en"
    budget: int | None = None
    llm_selection: LLMSelectionPayload | None = None


class AuditRequest(BaseModel):
    language: str = "en"
    budget: int | None = None
    llm_selection: LLMSelectionPayload | None = None


class DedupRequest(BaseModel):
    language: str = "en"
    iterations: int | None = None
    llm_selection: LLMSelectionPayload | None = None


@router.post("/doc/{layer}/{key}/update")
async def update_doc(layer: str, key: str, payload: UpdateRequest | None = None):
    lyr = _validate_layer(layer)
    _validate_doc_key(lyr, key)
    req = RunStartRequest(
        layer=lyr,
        key=key,
        mode="update",
        language=(payload.language if payload else "en") or "en",
        budget=payload.budget if payload else None,
        llm_selection=payload.llm_selection if payload else None,
    )
    return _legacy_run_stream(req)


@router.post("/doc/{layer}/{key}/audit")
async def audit_doc(layer: str, key: str, payload: AuditRequest | None = None):
    lyr = _validate_layer(layer)
    _validate_doc_key(lyr, key)
    req = RunStartRequest(
        layer=lyr,
        key=key,
        mode="audit",
        language=(payload.language if payload else "en") or "en",
        budget=payload.budget if payload else None,
        llm_selection=payload.llm_selection if payload else None,
    )
    return _legacy_run_stream(req)


@router.post("/doc/{layer}/{key}/dedup")
async def dedup_doc(layer: str, key: str, payload: DedupRequest | None = None):
    lyr = _validate_layer(layer)
    _validate_doc_key(lyr, key)
    req = RunStartRequest(
        layer=lyr,
        key=key,
        mode="dedup",
        language=(payload.language if payload else "en") or "en",
        iterations=payload.iterations if payload else None,
        llm_selection=payload.llm_selection if payload else None,
    )
    return _legacy_run_stream(req)


@router.get("/doc/{layer}/{key}/lines")
async def get_doc_lines(layer: str, key: str):
    """返回文档的带行号、去除脚注的视图。

    供工作台的"显示行号"开关使用，使用户能看到与审计/去重 LLM 相同的行索引。
    脚注区块被省略，因为编辑操作不会直接引用它。
    """
    lyr = _validate_layer(layer)
    _validate_doc_key(lyr, key)
    from aidlearning.memory.shared import paths
    from aidlearning.memory.consolidator.line_doc import render_view
    from aidlearning.memory.long_term.document import Document, parse

    path = paths.l2_file(key) if lyr == "L2" else paths.l3_file(key)  # type: ignore[arg-type]
    doc = (
        parse(path.read_text(encoding="utf-8"))
        if path.exists()
        else Document(title=_default_title(lyr, key))
    )
    view = render_view(doc)
    return {
        "layer": lyr,
        "key": key,
        "lines": [
            {
                "number": line.number,
                "kind": line.kind,
                "text": line.text,
                "entry_id": line.entry_id,
                "section": line.section,
            }
            for line in view.lines
        ],
    }


# ── 设置 ────────────────────────────────────────────────────────────────────


@router.get("/settings")
async def get_memory_settings_endpoint():
    """返回当前 memory: 子树（含默认值合并）。"""
    from aidlearning.memory.settings import memory_settings_dict

    return memory_settings_dict()


@router.put("/settings")
async def put_memory_settings(payload: dict):
    """将请求体合并到 memory: 子树并持久化。"""
    from aidlearning.memory.settings import (
        memory_settings_dict,
        save_memory_settings,
    )

    save_memory_settings(payload)
    return memory_settings_dict()


def _default_title(layer: str, key: str) -> str:
    if layer == "L2":
        return f"{key} memory"
    return {
        "recent": "Recent summary",
        "profile": "User profile",
        "scope": "Knowledge scope",
        "preferences": "Preferences",
    }.get(key, f"{key} memory")


class ApplyOpsRequest(BaseModel):
    ops: list[dict]


@router.post("/doc/{layer}/{key}/apply")
async def apply_doc_ops(layer: str, key: str, payload: ApplyOpsRequest):
    """将一组预览过的操作原子性地提交到文档。"""
    lyr = _validate_layer(layer)
    _validate_doc_key(lyr, key)
    if lyr == "L3" and key == "preferences":
        raise HTTPException(
            status_code=405,
            detail="preferences is written by the write_memory tool, not consolidated",
        )
    if not payload.ops:
        return {"accepted": True, "reason": "no ops to apply", "results": []}

    report = await get_memory_store().apply_ops_payload(lyr, key, payload.ops)
    return {
        "accepted": report.accepted,
        "reason": report.reason,
        "results": [
            {
                "status": r.status,
                "entry_id": r.entry_id,
                "detail": r.detail,
            }
            for r in report.results
        ],
    }


# ── 追踪浏览器 ────────────────────────────────────────────────────────────


@router.get("/trace/{surface}")
async def get_trace(surface: str, limit: int = 200, offset: int = 0):
    surf = _validate_surface(surface)
    from aidlearning.memory.shared.trace import iter_since

    events = []
    for i, event in enumerate(iter_since(surf)):
        if i < offset:
            continue
        if len(events) >= max(1, min(limit, 1000)):
            break
        events.append(asdict(event))
    return {"surface": surf, "events": events, "offset": offset, "limit": limit}


@router.delete("/trace/{surface}")
async def clear_trace(surface: str):
    surf = _validate_surface(surface)
    removed = 0
    for path in paths.trace_dir(surf).glob("*.jsonl"):
        try:
            path.unlink()
            removed += 1
        except OSError:
            continue
    return {"surface": surf, "removed_files": removed}


@router.delete("/trace/{surface}/day/{day}")
async def clear_trace_day(surface: str, day: str):
    surf = _validate_surface(surface)
    try:
        parsed = date_cls.fromisoformat(day)
    except ValueError:
        raise HTTPException(status_code=400, detail="day must be YYYY-MM-DD")
    path = paths.trace_file(surf, parsed)
    if not path.exists():
        raise HTTPException(status_code=404, detail="no trace for that day")
    try:
        path.unlink()
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return {"surface": surf, "day": day, "deleted": True}


# ── 快照（L1 工作区镜像）──────────────────────────────────────────────────


@router.get("/snapshot/{surface}")
async def get_snapshot(surface: str):
    """返回工作区中指定 surface 的当前实体列表。

    快照始终在调用时从工作区实时派生。响应还包含 pending_changes——
    与上次持久化状态的差异。刷新操作将这些待定变更提交到 changes.jsonl。
    """
    surf = _validate_surface(surface)
    from aidlearning.memory import snapshot as snap

    entities = snap.read_snapshot(surf)
    pending = snap.pending_changes(surf, entities)
    state = snap.current_state(surf)
    return {
        "surface": surf,
        "entities": [e.to_dict() for e in entities],
        "last_refresh": state.get("last_refresh"),
        "pending_changes": [c.to_dict() for c in pending],
    }


@router.post("/snapshot/{surface}/refresh")
async def refresh_snapshot(surface: str):
    """将持久化状态与当前工作区对账；记录差异。"""
    surf = _validate_surface(surface)
    from aidlearning.memory import snapshot as snap

    changes = snap.refresh_snapshot(surf)
    state = snap.current_state(surf)
    return {
        "surface": surf,
        "changes": [c.to_dict() for c in changes],
        "last_refresh": state.get("last_refresh"),
    }


@router.get("/snapshot/{surface}/changes")
async def get_changes(surface: str, limit: int = 200, offset: int = 0):
    surf = _validate_surface(surface)
    from aidlearning.memory import snapshot as snap

    entries = snap.read_changes(surf, limit=limit, offset=offset)
    return {
        "surface": surf,
        "changes": [c.to_dict() for c in entries],
        "limit": limit,
        "offset": offset,
    }


@router.delete("/snapshot/{surface}/changes")
async def clear_snapshot_changes(surface: str):
    surf = _validate_surface(surface)
    from aidlearning.memory import snapshot as snap

    snap.clear_changes(surf)
    return {"surface": surf, "cleared": True}


# ── 调试：完整记忆状态 ──────────────────────────────────────────────


@router.get("/debug")
async def debug_memory_page():
    """提供记忆调试仪表盘 HTML 页面。"""
    from fastapi.responses import HTMLResponse
    from pathlib import Path

    html_path = Path(__file__).parent / "memory_debug.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>memory_debug.html not found</h1>", status_code=404)


@router.get("/debug/state")
async def debug_memory_state():
    """返回所有记忆层的完整状态。

    包括内存缓冲区、SQLite 消息、L2/L3 文档和 L1 追踪记录。
    适用于对话过程中的实时调试。
    """
    import re as _re
    import sqlite3 as _sqlite3
    from datetime import datetime, timezone

    result: dict[str, Any] = {}

    # ── 短期记忆（缓冲区）────────────────────────────────────────
    try:
        from aidlearning.memory.short_term.buffer_manager import get_buffer_manager
        mgr = get_buffer_manager()
        bufs: dict[str, Any] = {}
        for sid, buf in mgr._buffers.items():
            messages_preview = []
            for m in buf._messages[-5:]:
                messages_preview.append({
                    "id": m.msg_id,
                    "role": m.role,
                    "content": m.content[:200],
                    "tokens": m.tokens,
                    "flushed": m.flushed,
                })
            bufs[sid] = {
                "message_count": buf.message_count,
                "token_budget": buf.token_budget,
                "current_tokens": buf.total_tokens(),
                "summary": buf.summary[:500],
                "summary_tokens": buf.summary_tokens,
                "compressed_count": buf.total_compressed,
                "recent_messages": messages_preview,
            }
        result["short_term"] = {"active_buffers": len(bufs), "buffers": bufs}
    except Exception as exc:
        result["short_term"] = {"error": str(exc)}

    # ── 中期记忆（SQLite）───────────────────────────────────────────
    try:
        from aidlearning.services.path_service import get_path_service
        db_path = get_path_service().get_chat_history_db()
        if db_path.exists():
            conn = _sqlite3.connect(str(db_path))
            conn.row_factory = _sqlite3.Row
            msg_count = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
            sess_count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
            try:
                fts_count = conn.execute("SELECT COUNT(*) FROM messages_fts").fetchone()[0]
            except Exception:
                fts_count = 0

            recent = conn.execute(
                "SELECT m.session_id, s.title, m.role, substr(m.content,1,150) as content, "
                "m.created_at FROM messages m LEFT JOIN sessions s ON m.session_id = s.id "
                "ORDER BY m.created_at DESC LIMIT 10"
            ).fetchall()
            conn.close()
            result["mid_term"] = {
                "db_path": str(db_path),
                "total_messages": msg_count,
                "total_sessions": sess_count,
                "fts5_indexed": fts_count,
                "recent_messages": [
                    {
                        "session_id": r["session_id"],
                        "session_title": r["title"] or "",
                        "role": r["role"],
                        "content": r["content"],
                        "created_at": datetime.fromtimestamp(r["created_at"], tz=timezone.utc).isoformat(),
                    }
                    for r in recent
                ],
            }
        else:
            result["mid_term"] = {"error": "DB not found"}
    except Exception as exc:
        result["mid_term"] = {"error": str(exc)}

    # ── 长期记忆（L2/L3 Markdown）──────────────────────────────────
    try:
        from aidlearning.memory.shared.paths import memory_root, L2_TARGETS, L3_SLOTS
        mem_root = memory_root()

        l2_docs: dict[str, Any] = {}
        for target in L2_TARGETS:
            p = mem_root / "L2" / f"{target}.md"
            if p.exists():
                content = p.read_text(encoding="utf-8")
                entries = _re.findall(r"<!--m_", content)
                sections = _re.findall(r"^## (.+)$", content, _re.MULTILINE)
                l2_docs[target] = {
                    "exists": True,
                    "chars": len(content),
                    "entries": len(entries),
                    "sections": sections,
                    "content": content[:2000],
                }
            else:
                l2_docs[target] = {"exists": False}
        result["long_term_l2"] = l2_docs

        l3_docs: dict[str, Any] = {}
        for slot in L3_SLOTS:
            p = mem_root / "L3" / f"{slot}.md"
            if p.exists():
                content = p.read_text(encoding="utf-8")
                entries = _re.findall(r"<!--m_", content)
                l3_docs[slot] = {
                    "exists": True,
                    "chars": len(content),
                    "entries": len(entries),
                    "content": content[:2000],
                }
            else:
                l3_docs[slot] = {"exists": False}
        result["long_term_l3"] = l3_docs
    except Exception as exc:
        result["long_term"] = {"error": str(exc)}

    # ── L1 追踪记录 ────────────────────────────────────────────────
    try:
        from aidlearning.memory.shared.paths import memory_root
        td = memory_root() / "trace"
        traces: dict[str, Any] = {}
        if td.exists():
            for d in sorted(td.iterdir()):
                if d.is_dir():
                    files = list(d.glob("*.jsonl"))
                    total = sum(sum(1 for _ in open(f, encoding="utf-8")) for f in files)
                    traces[d.name] = {"files": len(files), "events": total}
        result["l1_traces"] = traces
    except Exception as exc:
        result["l1_traces"] = {"error": str(exc)}

    return result


@router.get("/debug/sessions")
async def debug_sessions():
    """返回所有会话及其消息数量，供调试仪表盘使用。"""
    import sqlite3 as _sqlite3
    from datetime import datetime, timezone

    try:
        from aidlearning.services.path_service import get_path_service
        from aidlearning.utils.sqlite_compat import sqlite3 as sqlite3c

        db_path = get_path_service().get_chat_history_db()
        if not db_path.exists():
            return {"sessions": []}

        conn = sqlite3c.connect(str(db_path))
        conn.row_factory = sqlite3c.Row
        rows = conn.execute(
            "SELECT s.id, s.title, s.created_at, s.updated_at, "
            "COUNT(m.id) as msg_count, "
            "s.compressed_summary, s.summary_up_to_msg_id "
            "FROM sessions s LEFT JOIN messages m ON s.id = m.session_id "
            "GROUP BY s.id ORDER BY s.updated_at DESC LIMIT 50"
        ).fetchall()

        sessions = []
        for r in rows:
            sessions.append({
                "id": r["id"],
                "title": r["title"] or "Untitled",
                "msg_count": r["msg_count"],
                "updated_at": datetime.fromtimestamp(r["updated_at"], tz=timezone.utc).isoformat(),
                "has_summary": bool(r["compressed_summary"]),
            })
        conn.close()
        return {"sessions": sessions}
    except Exception as exc:
        return {"sessions": [], "error": str(exc)}


@router.get("/debug/session/{session_id}")
async def debug_session_buffer(session_id: str):
    """强制将会话加载到缓冲区并返回其状态。

    从已初始化集合中移除该会话，使其从 SQLite 重新水合，
    从而获得缓冲区状态的最新视图。
    """
    from datetime import datetime, timezone

    try:
        from aidlearning.memory.short_term.buffer_manager import get_buffer_manager
        from aidlearning.services.session.sqlite_store import get_sqlite_session_store
        from aidlearning.utils.sqlite_compat import sqlite3 as sqlite3c

        sqlite_store = get_sqlite_session_store()
        buffer_mgr = get_buffer_manager()

        # 强制重新水合：从已初始化集合和现有缓冲区中移除
        buffer_mgr._initialized.discard(session_id)
        buffer_mgr._buffers.pop(session_id, None)

        # 将会话加载到缓冲区
        buf = await buffer_mgr.get_or_create(session_id, sqlite_store)

        # 获取会话信息
        db_path = sqlite_store.db_path
        conn = sqlite3c.connect(str(db_path))
        conn.row_factory = sqlite3c.Row
        session = conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()

        if not session:
            conn.close()
            return {"error": "Session not found"}

        title = session["title"] or "Untitled"
        conn.close()

        # 从缓冲区构建响应
        messages = buf.get_messages_for_context()
        msg_details = []
        for m in messages:
            msg_details.append({
                "id": m["id"],
                "role": m["role"],
                "content": m["content"][:200],
            })

        return {
            "session_id": session_id,
            "title": title,
            "buffer": {
                "message_count": buf.message_count,
                "token_budget": buf.token_budget,
                "current_tokens": buf.total_tokens(),
                "summary": buf.summary[:500],
                "summary_tokens": buf.summary_tokens,
                "compressed_count": buf.total_compressed,
                "messages": msg_details,
            },
        }
    except Exception as exc:
        return {"error": str(exc)}
