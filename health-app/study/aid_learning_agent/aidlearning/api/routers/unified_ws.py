"""
Unified WebSocket Endpoint — 统一 WebSocket 接口
================================================
订阅某个时间流的意思就是监控这个对话流将其实时输出而
执行逻辑在services.session
    

调用链路：
  unified_ws.py → TurnRuntimeManager.start_turn() → _run_turn()
    → ContextBuilder + 上下文构建 → ChatOrchestrator.handle()
      → Capability.run() → Agent + 工具调用 → StreamEvent 流式返回
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/ws")
async def unified_websocket(ws: WebSocket) -> None:
    """
    统一 WebSocket 主入口 — 所有对话功能的唯一入口。

    流程：
      1. 鉴权（在 accept 之前）
      2. accept 连接
      3. 进入消息循环，根据 msg_type 分发到对应处理逻辑
      4. 断开时清理所有订阅任务和用户上下文

    内部定义了 4 个闭包函数：
      - safe_send(): 安全发送 JSON（连接关闭时不抛异常）
      - stop_subscription(): 取消并清理订阅任务
      - subscribe_turn(): 订阅某个 turn 的事件流
      - subscribe_session(): 订阅某个 session 的活跃 turn 事件流
    """
    from aidlearning.api.routers.auth import ws_auth_failed, ws_require_auth
    from aidlearning.multi_user.context import reset_current_user

    # 步骤1: WebSocket 鉴权（在 accept 之前，失败则关闭连接）
    user_token = await ws_require_auth(ws)
    if user_token is ws_auth_failed:
        return

    # 步骤2: 接受连接
    await ws.accept()
    closed = False
    # 所有活跃的订阅任务（key → asyncio.Task），用于断开时清理
    subscription_tasks: dict[str, asyncio.Task[None]] = {}

    async def safe_send(data: dict[str, Any]) -> None:
        """
        安全发送 JSON 数据到客户端。

        如果连接已关闭或发送失败，设置 closed=True 而不是抛异常。
        所有对外发送都应通过此函数，避免 WebSocket 断开时的级联错误。
        """
        nonlocal closed
        if closed:
            return
        try:
            await ws.send_json(data)
        except Exception:
            closed = True

    async def stop_subscription(key: str) -> None:
        """
        取消并清理指定的订阅任务。

        从 subscription_tasks 中移除任务，取消其 asyncio.Task，
        等待任务结束（CancelledError 被静默捕获）。
        """
        task = subscription_tasks.pop(key, None)
        if task is None:
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    async def subscribe_turn(turn_id: str, after_seq: int = 0) -> None:
        """
        订阅某个 turn 的事件流。

        创建后台任务，从 TurnRuntimeManager.subscribe_turn() 持续读取事件，
        并通过 safe_send() 推送给客户端。

        支持 after_seq 参数实现断点续传（重连时跳过已收到的事件）。
        如果该 turn 已有订阅，先取消旧订阅再创建新的。
        """
        from aidlearning.services.session import get_turn_runtime_manager

        async def _forward() -> None:
            """后台转发任务：持续读取 turn 事件并推送给客户端。"""
            runtime = get_turn_runtime_manager()
            async for event in runtime.subscribe_turn(turn_id, after_seq=after_seq):
                await safe_send(event)

        # 先取消该 turn 的旧订阅
        await stop_subscription(turn_id)
        # 创建新的后台转发任务
        subscription_tasks[turn_id] = asyncio.create_task(_forward())

    async def subscribe_session(session_id: str, after_seq: int = 0) -> None:
        """
        订阅某个 session 的活跃 turn 事件流。

        与 subscribe_turn 类似，但通过 session_id 查找其活跃 turn。
        订阅 key 为 "session:{session_id}"，避免与 turn_id 冲突。
        """
        from aidlearning.services.session import get_turn_runtime_manager

        async def _forward() -> None:
            """后台转发任务：持续读取 session 事件并推送给客户端。"""
            runtime = get_turn_runtime_manager()
            async for event in runtime.subscribe_session(session_id, after_seq=after_seq):
                await safe_send(event)

        key = f"session:{session_id}"
        await stop_subscription(key)
        subscription_tasks[key] = asyncio.create_task(_forward())

    # =====================================================================
    # 消息循环 — 根据 msg_type 分发到对应处理逻辑
    # =====================================================================
    try:
        while not closed:
            # 接收客户端消息
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await safe_send({"type": "error", "content": "Invalid JSON."})
                continue

            msg_type = msg.get("type")

            # ----------------------------------------------------------
            # message / start_turn — 开始新一轮对话
            # ----------------------------------------------------------
            # 前端发送用户消息时使用此类型，携带完整的上下文：
            #   capability: 对话模式（chat/deep_solve/deep_question/deep_research）
            #   tools: 启用的工具列表（web_search/code_execution/brainstorm 等）
            #   knowledge_bases: 知识库列表
            #   attachments: 附件列表（图片/文档）
            #   notebook_references / history_references: Space 引用
            #   skills / memory_references: 技能和记忆引用
            #   llm_selection: 模型选择
            #   config: 能力配置（Quiz/Research 等的表单配置）
            #
            # 调用链：runtime.start_turn() → _run_turn() → ChatOrchestrator → Capability
            # ----------------------------------------------------------
            if msg_type in {"message", "start_turn"}:
                from aidlearning.services.session import get_turn_runtime_manager

                runtime = get_turn_runtime_manager()
                try:
                    _, turn = await runtime.start_turn(msg)
                except RuntimeError as exc:
                    # 启动失败（如配置校验不通过、模型权限不足等）
                    await safe_send(
                        {
                            "type": "error",
                            "source": "unified_ws",
                            "stage": "",
                            "content": str(exc),
                            "metadata": {"turn_terminal": True, "status": "rejected"},
                            "session_id": str(msg.get("session_id") or ""),
                            "turn_id": "",
                            "seq": 0,
                        }
                    )
                    continue
                # Turn 创建成功，订阅其事件流
                await subscribe_turn(turn["id"], after_seq=0)
                continue

            # ----------------------------------------------------------
            # ping — 客户端心跳
            # ----------------------------------------------------------
            # 客户端定期发送 ping 保持连接活跃。
            # 服务端回复 pong，客户端刷新 lastReceivedAt 但不展示为用户事件。
            if msg_type == "ping":
                await safe_send({"type": "pong"})
                continue

            # ----------------------------------------------------------
            # subscribe_turn — 订阅指定 turn 的事件流
            # ----------------------------------------------------------
            # 用于：断线重连后重新订阅、或订阅其他客户端发起的 turn。
            # after_seq: 从哪个 seq 开始（跳过已收到的事件）。
            if msg_type == "subscribe_turn":
                turn_id = str(msg.get("turn_id") or "").strip()
                if not turn_id:
                    await safe_send({"type": "error", "content": "Missing turn_id."})
                    continue
                await subscribe_turn(turn_id, after_seq=int(msg.get("after_seq") or 0))
                continue

            # ----------------------------------------------------------
            # subscribe_session — 订阅指定 session 的活跃 turn
            # ----------------------------------------------------------
            # 不需要知道具体 turn_id，自动查找该 session 的活跃 turn。
            if msg_type == "subscribe_session":
                session_id = str(msg.get("session_id") or "").strip()
                if not session_id:
                    await safe_send({"type": "error", "content": "Missing session_id."})
                    continue
                await subscribe_session(session_id, after_seq=int(msg.get("after_seq") or 0))
                continue

            # ----------------------------------------------------------
            # resume_from — 断线重连后从指定 seq 恢复
            # ----------------------------------------------------------
            # 客户端记录上次收到的 seq，重连后从该位置继续接收。
            if msg_type == "resume_from":
                turn_id = str(msg.get("turn_id") or "").strip()
                if not turn_id:
                    await safe_send({"type": "error", "content": "Missing turn_id."})
                    continue
                await subscribe_turn(turn_id, after_seq=int(msg.get("seq") or 0))
                continue

            # ----------------------------------------------------------
            # unsubscribe — 取消订阅
            # ----------------------------------------------------------
            # 可同时取消 turn 和 session 的订阅。
            if msg_type == "unsubscribe":
                turn_id = str(msg.get("turn_id") or "").strip()
                if turn_id:
                    await stop_subscription(turn_id)
                session_id = str(msg.get("session_id") or "").strip()
                if session_id:
                    await stop_subscription(f"session:{session_id}")
                continue

            # ----------------------------------------------------------
            # cancel_turn — 取消正在运行的 turn
            # ----------------------------------------------------------
            # 用户点击"停止生成"时发送。
            # 调用 runtime.cancel_turn() → 取消 asyncio.Task → 发送 error + done 事件。
            if msg_type == "cancel_turn":
                turn_id = str(msg.get("turn_id") or "").strip()
                if not turn_id:
                    await safe_send({"type": "error", "content": "Missing turn_id."})
                    continue
                from aidlearning.services.session import get_turn_runtime_manager

                runtime = get_turn_runtime_manager()
                cancelled = await runtime.cancel_turn(turn_id)
                if not cancelled:
                    await safe_send({"type": "error", "content": f"Turn not found: {turn_id}"})
                continue

            # ----------------------------------------------------------
            # submit_user_reply — 用户回复 ask_user 工具的暂停等待
            # ----------------------------------------------------------
            # 当 Agent 调用 ask_user 工具时，agentic loop 会暂停并等待用户回复。
            # 用户在前端输入回复后，通过此消息类型提交。
            #
            # 支持两种格式：
            #   - text: 单条自由文本回复（旧版兼容）
            #   - answers: 结构化回复列表 [{questionId, text}, ...]（v2 多问题）
            # 允许空文本（用户表示"没有答案"）。
            if msg_type == "submit_user_reply":
                turn_id = str(msg.get("turn_id") or "").strip()
                if not turn_id:
                    await safe_send({"type": "error", "content": "Missing turn_id."})
                    continue
                # 解析 text 字段（旧版单条回复）
                text = msg.get("text")
                text_str = str(text) if text is not None else None
                # 解析 answers 字段（v2 结构化多问题回复）
                answers_raw = msg.get("answers")
                answers: list[dict[str, Any]] | None = None
                if isinstance(answers_raw, list):
                    cleaned: list[dict[str, Any]] = []
                    for entry in answers_raw:
                        if not isinstance(entry, dict):
                            continue
                        qid = str(entry.get("questionId") or entry.get("id") or "").strip()
                        if not qid:
                            continue
                        cleaned.append({"questionId": qid, "text": str(entry.get("text") or "")})
                    answers = cleaned or None
                from aidlearning.services.session import get_turn_runtime_manager

                runtime = get_turn_runtime_manager()
                # 将回复推入 reply_queue，唤醒正在等待的 agentic loop
                accepted = await runtime.submit_user_reply(turn_id, text=text_str, answers=answers)
                if not accepted:
                    await safe_send(
                        {
                            "type": "error",
                            "content": (f"Turn {turn_id} is not awaiting a user reply."),
                        }
                    )
                continue

            # ----------------------------------------------------------
            # regenerate — 重新生成上一轮回复
            # ----------------------------------------------------------
            # 用户点击"重新生成"时发送。
            # 流程：
            #   1. 删除上一条 assistant 消息
            #   2. 复用上一条 user 消息的 content、attachments、capability 等
            #   3. 创建新的 turn 重新执行（_persist_user_message=False，不重复保存用户消息）
            #
            # 可选 overrides 字段覆盖参数：
            #   capability, tools, knowledge_bases, language, config,
            #   notebook_references, history_references, llm_selection
            #
            # 错误：
            #   regenerate_busy — 该 session 有正在运行的 turn
            #   nothing_to_regenerate — 没有可重新生成的用户消息
            if msg_type == "regenerate":
                session_id = str(msg.get("session_id") or "").strip()
                if not session_id:
                    await safe_send({"type": "error", "content": "Missing session_id."})
                    continue
                from aidlearning.services.session import get_turn_runtime_manager

                runtime = get_turn_runtime_manager()
                overrides = msg.get("overrides") if isinstance(msg.get("overrides"), dict) else None
                try:
                    _, turn = await runtime.regenerate_last_turn(
                        session_id,
                        overrides=overrides,
                    )
                except RuntimeError as exc:
                    await safe_send(
                        {
                            "type": "error",
                            "source": "unified_ws",
                            "stage": "",
                            "content": str(exc),
                            "metadata": {
                                "turn_terminal": True,
                                "status": "rejected",
                                "reason": str(exc),
                            },
                            "session_id": session_id,
                            "turn_id": "",
                            "seq": 0,
                        }
                    )
                    continue
                # 新 turn 创建成功，订阅其事件流
                await subscribe_turn(turn["id"], after_seq=0)
                continue

            # ----------------------------------------------------------
            # 未知消息类型
            # ----------------------------------------------------------
            await safe_send({"type": "error", "content": f"Unknown type: {msg_type}"})

    except WebSocketDisconnect:
        logger.debug("Client disconnected from /ws")
    except Exception as exc:
        logger.error("Unified WS error: %s", exc, exc_info=True)
        await safe_send({"type": "error", "content": str(exc)})
    finally:
        # 清理：关闭连接、取消所有订阅、重置用户上下文
        closed = True
        for key in list(subscription_tasks.keys()):
            await stop_subscription(key)
        if user_token is not None:
            reset_current_user(user_token)
