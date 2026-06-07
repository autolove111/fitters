"""Real-time memory monitor for AidLearning.

Run this script to see the current state of all memory layers.

Usage:
    python scripts/memory_monitor.py
"""

import sys
import os
import sqlite3
import re

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def monitor():
    print("=" * 60)
    print("AidLearning Memory Monitor")
    print("=" * 60)

    # ── 1. Short-term ─────────────────────────────────────────────
    print()
    print("[1] SHORT-TERM MEMORY (ConversationBuffer)")
    print("-" * 40)
    from aidlearning.memory.short_term.buffer_manager import get_buffer_manager

    mgr = get_buffer_manager()
    print(f"Active buffers: {len(mgr._buffers)}")
    if not mgr._buffers:
        print("  (no active conversations in this process)")
    for sid, buf in mgr._buffers.items():
        print(f"  Session: {sid}")
        print(f"    Window: {buf.message_count} messages")
        print(f"    Summary: {len(buf.summary)} chars")
        print(f"    Compressed: {buf.total_compressed} messages")
        if buf.summary:
            print(f"    Summary: {buf.summary[:100]}...")
        for m in buf._messages[-3:]:
            print(f"    [{m.msg_id}] {m.role}: {m.content[:60]}")

    # ── 2. Mid-term ───────────────────────────────────────────────
    print()
    print("[2] MID-TERM MEMORY (SQLite messages)")
    print("-" * 40)
    from aidlearning.services.path_service import get_path_service
    from aidlearning.utils.sqlite_compat import sqlite3 as sqlite3c

    # Initialize store to ensure FTS5 table exists
    from aidlearning.services.session.sqlite_store import get_sqlite_session_store
    _ = get_sqlite_session_store()

    db_path = get_path_service().get_chat_history_db()
    print(f"DB: {db_path}")
    if not db_path.exists():
        print("  DB not found")
    else:
        conn = sqlite3c.connect(str(db_path))
        conn.row_factory = sqlite3c.Row
        count = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        print(f"Total messages: {count}")

        # FTS5 status
        try:
            fts = conn.execute("SELECT COUNT(*) FROM messages_fts").fetchone()[0]
            print(f"FTS5 indexed: {fts}")
        except Exception:
            print("FTS5: not available (using LIKE fallback)")

        # Session count
        sessions = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        print(f"Sessions: {sessions}")

        # Recent messages
        rows = conn.execute(
            "SELECT session_id, role, substr(content,1,60) as c "
            "FROM messages ORDER BY created_at DESC LIMIT 5"
        ).fetchall()
        print("Recent messages:")
        for r in rows:
            print(f"  [{r['session_id'][:15]}] {r['role']}: {r['c']}")

        conn.close()

    # ── 3. Long-term ──────────────────────────────────────────────
    print()
    print("[3] LONG-TERM MEMORY (L2/L3 Markdown)")
    print("-" * 40)
    from aidlearning.memory.shared.paths import memory_root, L2_TARGETS, L3_SLOTS

    mem_root = memory_root()
    print(f"Root: {mem_root}")

    for target in L2_TARGETS:
        p = mem_root / "L2" / f"{target}.md"
        if p.exists():
            c = p.read_text(encoding="utf-8")
            n = len(re.findall(r"<!--m_", c))
            sections = re.findall(r"^## (.+)$", c, re.MULTILINE)
            print(f"  L2/{target}.md: {len(c)} chars, {n} entries")
            for s in sections:
                print(f"    Section: {s}")
        else:
            print(f"  L2/{target}.md: NOT CREATED")

    for slot in L3_SLOTS:
        p = mem_root / "L3" / f"{slot}.md"
        if p.exists():
            c = p.read_text(encoding="utf-8")
            n = len(re.findall(r"<!--m_", c))
            print(f"  L3/{slot}.md: {len(c)} chars, {n} entries")
        else:
            print(f"  L3/{slot}.md: NOT CREATED")

    # ── 4. L1 traces ──────────────────────────────────────────────
    print()
    print("[4] L1 TRACE EVENTS")
    print("-" * 40)
    td = mem_root / "trace"
    if td.exists():
        found = False
        for d in sorted(td.iterdir()):
            if d.is_dir():
                files = list(d.glob("*.jsonl"))
                if files:
                    total = 0
                    for f in files:
                        total += sum(1 for _ in open(f, encoding="utf-8"))
                    print(f"  {d.name}/: {len(files)} files, {total} events")
                    found = True
        if not found:
            print("  No trace events")
    else:
        print("  Trace directory not found")

    # ── 5. Skills ─────────────────────────────────────────────────
    print()
    print("[5] PROCEDURAL MEMORY (Skills)")
    print("-" * 40)
    from aidlearning.services.path_service import get_path_service

    skills_dir = get_path_service().get_workspace_dir() / "skills"
    if skills_dir.exists():
        skill_dirs = [d for d in skills_dir.iterdir() if d.is_dir()]
        print(f"Skills: {len(skill_dirs)}")
        for d in skill_dirs:
            skill_file = d / "SKILL.md"
            if skill_file.exists():
                c = skill_file.read_text(encoding="utf-8")
                # Extract name from frontmatter
                m = re.search(r"^name:\s*(.+)$", c, re.MULTILINE)
                name = m.group(1).strip() if m else d.name
                print(f"  - {name}")
    else:
        print("  No skills directory")

    print()
    print("=" * 60)


if __name__ == "__main__":
    monitor()
