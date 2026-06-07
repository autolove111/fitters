# AidLearning — Agent-Native Architecture

## Overview

AidLearning is an **agent-native** intelligent learning companion organized
around a two-layer plugin model — single-shot **Tools** invoked by the
LLM, and multi-stage **Capabilities** that take over a turn — exposed
through three entry points: CLI, WebSocket API, and Python SDK.

## Architecture

```
Entry Points:  CLI (Typer)  |  WebSocket /api/v1/ws  |  Python SDK
                    ↓                   ↓                   ↓
              ┌─────────────────────────────────────────────────┐
              │              ChatOrchestrator                    │
              │   routes UnifiedContext → selected Capability    │
              │   (defaults to `chat`)                           │
              └──────────┬──────────────┬───────────────────────┘
                         │              │
              ┌──────────▼──┐  ┌────────▼──────────┐
              │ ToolRegistry │  │ CapabilityRegistry │
              │  (Level 1)   │  │   (Level 2)        │
              └──────────────┘  └────────────────────┘
```

All capabilities emit on a shared `StreamBus`; the orchestrator fans
events out to consumers. Runtime settings live in
`data/user/settings/*.json` — project-root `.env` files are intentionally
ignored.

### Level 1 — Tools

Single-function tools the LLM picks on demand. The chat capability auto-mounts
context-gated tools (rag, read_source, read_memory, write_memory, list_notebook,
write_note, web_fetch, github, ask_user); five user-toggleable tools surface in
`/settings/tools`:

| Tool             | Description                                              |
| ---------------- | -------------------------------------------------------- |
| `brainstorm`     | Breadth-first idea exploration with rationale            |
| `web_search`     | Web search with citations                                |
| `paper_search`   | arXiv preprint search                                    |
| `code_execution` | Sandboxed Python (NL intent → code → run)                |
| `reason`         | Dedicated deep-reasoning LLM call                        |

Always-on, context-gated tools: `rag`, `read_source`, `read_memory`,
`write_memory`, `web_fetch`, `list_notebook`, `write_note`, `github`,
`ask_user` (pauses the turn and resumes with the user's reply).
`geogebra_analysis` is parked under `COMING_SOON_TOOL_TYPES`.

### Level 2 — Capabilities

Multi-stage pipelines that own the turn:

| Capability       | Stages                                                |
| ---------------- | ----------------------------------------------------- |
| `chat`           | thinking → acting → observing → responding (agentic loop, default) |
| `auto`           | analyzing → delegating → synthesizing (routes to another capability) |
| `deep_solve`     | planning → reasoning → writing                        |
| `deep_question`  | ideation → generation                                 |
| `deep_research`  | rephrasing → decomposing → researching → reporting    |

All capabilities converge on `emit_capability_result()` in
`aidlearning/capabilities/_shared.py` so every turn emits the same envelope
(response payload + `cost_summary` from `UsageTracker`). Status copy and
prompts are i18n'd via `capabilities/prompts/{en,zh}/<name>.yaml`.

## CLI Usage

```bash
# Install
pip install aidlearning      # Full app (CLI + Web/API + packaged Web assets)
pip install aidlearning-cli  # CLI-only

# Run any capability
aidlearning run chat "Explain Fourier transform"
aidlearning run deep_solve "Solve x^2=4" -t rag --kb my-kb
aidlearning run auto "Animate sine wave"   # picks the right capability

# Interactive REPL
aidlearning chat
# (inside the REPL: /regenerate or /retry re-runs the last user message)

# Knowledge bases, memory, server
aidlearning kb list
aidlearning kb create my-kb --doc textbook.pdf
aidlearning memory show
aidlearning serve --port 8001
```

## Key Files

| Path                                       | Purpose                              |
| ------------------------------------------ | ------------------------------------ |
| `aidlearning/runtime/orchestrator.py`        | `ChatOrchestrator` — unified entry   |
| `aidlearning/runtime/launcher.py`            | Backend + frontend lifecycle / port discovery |
| `aidlearning/runtime/registry/`              | Tool + Capability registries         |
| `aidlearning/runtime/bootstrap/builtin_capabilities.py` | Built-in capability class paths |
| `aidlearning/services/config/runtime_settings.py` | JSON settings + process-env overrides |
| `aidlearning/core/stream.py`, `stream_bus.py` | StreamEvent protocol + async fan-out |
| `aidlearning/core/tool_protocol.py`          | `BaseTool` + `ToolDefinition`         |
| `aidlearning/core/capability_protocol.py`    | `BaseCapability` + `CapabilityManifest` |
| `aidlearning/core/context.py`                | `UnifiedContext` dataclass            |
| `aidlearning/tools/builtin/__init__.py`      | All built-in tool wrappers           |
| `aidlearning/capabilities/`                  | Built-in capability implementations  |
| `aidlearning_cli/main.py`                    | Typer CLI entry point                |
| `aidlearning/api/routers/unified_ws.py`      | Unified WebSocket endpoint           |

## Dependency Layers

Public install paths and source extras are defined in `pyproject.toml`.
Requirements files mirror the same dependency groups for Docker/CI installs.

```
pip install aidlearning      — Full app (CLI + Web/API + packaged Web assets)
pip install aidlearning-cli  — CLI-only (LLM + RAG + providers + document parsing)
pip install -e .           — Source install for development
.[tutorbot]       — Full app + TutorBot agent engine + channel SDKs
.[matrix]         — Matrix channel for TutorBot (matrix-nio[e2e]; needs libolm)
.[math-animator]  — Manim addon (powers `visualize` Manim renders + `aidlearning animate`)
.[dev]            — Full app + test/lint tools
.[all]            — Everything above
```
