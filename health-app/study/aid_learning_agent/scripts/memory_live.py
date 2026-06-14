"""AidLearning 实时内存监控器。

持续轮询所有内存层并显示变化。
在聊天时请在另一个终端窗口中运行此脚本。

用法：
    python scripts/memory_live.py [--interval 2]
"""

import sys
import os
import sqlite3
import re
import time
import argparse

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_state():
    """收集所有内存层的当前状态。"""
    state = {}

    # 中期记忆（SQLite）
    from aidlearning.services.path_service import get_path_service
    from aidlearning.utils.sqlite_compat import sqlite3 as sqlite3c

    db_path = get_path_service().get_chat_history_db()
    if db_path.exists():
        conn = sqlite3c.connect(str(db_path))
        conn.row_factory = sqlite3c.Row
        state["messages_count"] = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        state["sessions_count"] = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        try:
            state["fts_count"] = conn.execute("SELECT COUNT(*) FROM messages_fts").fetchone()[0]
        except Exception:
            state["fts_count"] = 0
        # 最近 3 条消息
        rows = conn.execute(
            "SELECT session_id, role, substr(content,1,80) as c, created_at "
            "FROM messages ORDER BY created_at DESC LIMIT 3"
        ).fetchall()
        state["recent_messages"] = [
            {"sid": r["session_id"][:12], "role": r["role"], "content": r["c"], "ts": r["created_at"]}
            for r in rows
        ]
        conn.close()

    # 长期记忆（Markdown）
    from aidlearning.memory.shared.paths import memory_root, L2_TARGETS, L3_SLOTS

    mem_root = memory_root()
    state["l2"] = {}
    for target in L2_TARGETS:
        p = mem_root / "L2" / f"{target}.md"
        if p.exists():
            c = p.read_text(encoding="utf-8")
            state["l2"][target] = {"chars": len(c), "entries": len(re.findall(r"<!--m_", c))}
        else:
            state["l2"][target] = None

    state["l3"] = {}
    for slot in L3_SLOTS:
        p = mem_root / "L3" / f"{slot}.md"
        if p.exists():
            c = p.read_text(encoding="utf-8")
            state["l3"][slot] = {"chars": len(c), "entries": len(re.findall(r"<!--m_", c))}
        else:
            state["l3"][slot] = None

    # L1 追踪
    td = mem_root / "trace"
    state["traces"] = {}
    if td.exists():
        for d in sorted(td.iterdir()):
            if d.is_dir():
                files = list(d.glob("*.jsonl"))
                total = sum(sum(1 for _ in open(f, encoding="utf-8")) for f in files)
                state["traces"][d.name] = {"files": len(files), "events": total}

    # 缓冲区（短期记忆）
    try:
        from aidlearning.memory.short_term.buffer_manager import get_buffer_manager
        mgr = get_buffer_manager()
        state["buffers"] = {}
        for sid, buf in mgr._buffers.items():
            state["buffers"][sid] = {
                "messages": buf.message_count,
                "summary_len": len(buf.summary),
                "compressed": buf.total_compressed,
            }
    except Exception:
        state["buffers"] = {}

    return state


def format_state(state, prev_state=None):
    """将状态格式化为显示字符串，高亮显示变化。"""
    lines = []
    lines.append("=" * 60)
    lines.append("  AidLearning Memory Live Monitor")
    lines.append("  Press Ctrl+C to stop")
    lines.append("=" * 60)

    # 短期记忆
    lines.append("")
    lines.append("[1] SHORT-TERM (Buffer)")
    lines.append("-" * 40)
    bufs = state.get("buffers", {})
    if not bufs:
        lines.append("  No active buffers")
    else:
        for sid, info in bufs.items():
            changed = ""
            if prev_state and sid in prev_state.get("buffers", {}):
                prev = prev_state["buffers"][sid]
                if info["messages"] != prev["messages"]:
                    changed = " *NEW*"
            lines.append(f"  Session: {sid}{changed}")
            lines.append(f"    Window: {info['messages']} msgs | Summary: {info['summary_len']} chars")

    # 中期记忆
    lines.append("")
    lines.append("[2] MID-TERM (SQLite)")
    lines.append("-" * 40)
    mc = state.get("messages_count", 0)
    fc = state.get("fts_count", 0)
    sc = state.get("sessions_count", 0)
    msg_changed = ""
    if prev_state and mc != prev_state.get("messages_count", 0):
        diff = mc - prev_state.get("messages_count", 0)
        msg_changed = f" (+{diff})" if diff > 0 else f" ({diff})"
    lines.append(f"  Messages: {mc}{msg_changed} | FTS5: {fc} | Sessions: {sc}")

    recent = state.get("recent_messages", [])
    if recent:
        lines.append("  Latest:")
        for r in recent:
            lines.append(f"    [{r['sid']}] {r['role']}: {r['content'][:60]}")

    # 长期记忆
    lines.append("")
    lines.append("[3] LONG-TERM (Markdown)")
    lines.append("-" * 40)
    for target, info in state.get("l2", {}).items():
        if info:
            changed = ""
            if prev_state and target in prev_state.get("l2", {}):
                prev_info = prev_state["l2"].get(target)
                if prev_info and info["entries"] != prev_info["entries"]:
                    changed = " *NEW*"
            lines.append(f"  L2/{target}.md: {info['entries']} entries, {info['chars']} chars{changed}")
        else:
            lines.append(f"  L2/{target}.md: NOT CREATED")

    for slot, info in state.get("l3", {}).items():
        if info:
            changed = ""
            if prev_state and slot in prev_state.get("l3", {}):
                prev_info = prev_state["l3"].get(slot)
                if prev_info and info["entries"] != prev_info["entries"]:
                    changed = " *NEW*"
            lines.append(f"  L3/{slot}.md: {info['entries']} entries, {info['chars']} chars{changed}")
        else:
            lines.append(f"  L3/{slot}.md: NOT CREATED")

    # L1 追踪
    lines.append("")
    lines.append("[4] L1 TRACES")
    lines.append("-" * 40)
    traces = state.get("traces", {})
    if not traces:
        lines.append("  No traces")
    else:
        for surface, info in traces.items():
            changed = ""
            if prev_state and surface in prev_state.get("traces", {}):
                prev_info = prev_state["traces"][surface]
                if info["events"] != prev_info["events"]:
                    changed = " *NEW*"
            lines.append(f"  {surface}/: {info['files']} files, {info['events']} events{changed}")

    lines.append("")
    lines.append(f"  Last update: {time.strftime('%H:%M:%S')}")
    lines.append("=" * 60)

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="实时内存监控器")
    parser.add_argument("--interval", type=float, default=2, help="轮询间隔（秒）")
    args = parser.parse_args()

    prev_state = None
    try:
        while True:
            state = get_state()
            output = format_state(state, prev_state)
            os.system("cls" if os.name == "nt" else "clear")
            print(output)
            prev_state = state
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n已停止。")


if __name__ == "__main__":
    main()
