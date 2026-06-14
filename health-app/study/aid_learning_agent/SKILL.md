# AidLearning CLI Skill

> Teach your AI agent to configure, manage, and use AidLearning — an intelligent learning platform — entirely through the command line.

## When to Use

Use this skill when the user wants to:
- Set up or configure AidLearning
- Chat with AidLearning or run a capability (deep solve, quiz generation, deep research, math animation)
- Create, manage, or search knowledge bases
- Manage TutorBot instances
- View or manage learning memory, sessions, or notebooks
- Start the AidLearning API server

## Prerequisites

- Python 3.11+
- AidLearning installed: `pip install aidlearning` for the full Web app, `pip install aidlearning-cli` for CLI-only, or `pip install -e .` from a source checkout
- Run `aidlearning init` for first-time interactive setup (configures LLM, embedding, and search providers under `data/user/settings`)

## Commands

### Chat & Capabilities

```bash
# Interactive REPL
aidlearning chat
aidlearning chat --capability deep_solve --kb my-kb --tool rag --tool web_search

# One-shot capability execution
aidlearning run chat "Explain Fourier transform"
aidlearning run deep_solve "Solve x^2 = 4" --tool rag --kb textbook
aidlearning run deep_question "Linear algebra" --config num_questions=5
aidlearning run deep_research "Attention mechanisms" --kb papers

# Options for `run`:
#   --session <id>         Resume existing session
#   --tool/-t <name>       Enable tool (repeatable): rag, web_search, code_execution, reason, brainstorm, paper_search
#   --kb <name>            Knowledge base (repeatable)
#   --notebook-ref <ref>   Notebook reference (repeatable)
#   --history-ref <id>     Referenced session id (repeatable)
#   --language/-l <code>   Response language (default: en)
#   --config <key=value>   Capability config (repeatable)
#   --config-json <json>   Capability config as JSON
#   --format/-f <fmt>      Output format: rich | json
```

### Knowledge Bases

```bash
aidlearning kb list                              # List all knowledge bases
aidlearning kb info <name>                       # Show knowledge base details
aidlearning kb create <name> --doc file.pdf      # Create from documents (--doc repeatable)
aidlearning kb add <name> --doc more.pdf         # Add documents incrementally
aidlearning kb search <name> "query text"        # Search a knowledge base
aidlearning kb set-default <name>                # Set as default KB
aidlearning kb delete <name> [--force]           # Delete a knowledge base
```

### TutorBot

```bash
aidlearning bot list                             # List all TutorBot instances
aidlearning bot create <id> --name "My Tutor"    # Create and start a new bot
aidlearning bot start <id>                       # Start a bot
aidlearning bot stop <id>                        # Stop a bot
```

### Memory

```bash
aidlearning memory show [summary|profile|all]    # View learning memory
aidlearning memory clear [summary|profile|all]   # Clear memory (--force to skip confirm)
```

### Sessions

```bash
aidlearning session list [--limit 20]            # List sessions
aidlearning session show <id>                    # View session messages
aidlearning session open <id>                    # Resume session in REPL
aidlearning session rename <id> --title "..."    # Rename a session
aidlearning session delete <id>                  # Delete a session
```

### Notebooks

```bash
aidlearning notebook list                        # List notebooks
aidlearning notebook create <name>               # Create a notebook
aidlearning notebook show <id>                   # View notebook records
aidlearning notebook add-md <id> <file.md>       # Import markdown as record
aidlearning notebook replace-md <id> <rec> <f>   # Replace a markdown record
aidlearning notebook remove-record <id> <rec>    # Remove a record
```

### System

```bash
aidlearning config show                          # Print current configuration
aidlearning plugin list                          # List registered tools and capabilities
aidlearning plugin info <name>                   # Show tool/capability details
aidlearning provider login <provider>            # OAuth login (openai-codex, github-copilot)
aidlearning serve [--port 8001] [--reload]       # Start API server
```

## REPL Slash Commands

Inside `aidlearning chat`, use these:

| Command | Effect |
|:---|:---|
| `/quit` | Exit REPL |
| `/session` | Show current session id |
| `/new` | Start a new session |
| `/tool on\|off <name>` | Toggle a tool |
| `/cap <name>` | Switch capability |
| `/kb <name>\|none` | Set or clear knowledge base |
| `/history add <id>` / `/history clear` | Manage history references |
| `/notebook add <ref>` / `/notebook clear` | Manage notebook references |
| `/refs` | Show active references |
| `/config show\|set\|clear` | Manage capability config |

## Typical Workflows

**First-time setup:**
```bash
cd AidLearning
pip install -e .
aidlearning init    # Interactive guided setup
```

**Daily learning:**
```bash
aidlearning chat --kb textbook --tool rag --tool web_search
```

**Build a knowledge base from documents:**
```bash
aidlearning kb create physics --doc ch1.pdf --doc ch2.pdf
aidlearning run chat "Explain Newton's third law" --kb physics --tool rag
```

**Generate quiz questions:**
```bash
aidlearning run deep_question "Thermodynamics" --kb physics --config num_questions=5
```
