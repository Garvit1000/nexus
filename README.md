# Nexus - AI-Powered Linux Assistant

**Nexus** is an intelligent, terminal-based Linux assistant that combines multiple AI models, memory systems, and automation capabilities to help you manage your system, browse the web, and execute complex tasks through natural language.

## Key Features

- **Multi-Brain AI Architecture** - Specialized models for different tasks (routing, chat, browser, search)
- **Autonomous Web Browsing** - Automated tasks with browser-use
- **Persistent Memory** - RAG via Supermemory (BYOK — your key, your data)
- **Self-Healing Execution** - Auto-fix failed commands with dual-stage healing + auto-failover across 5 LLM providers
- **File Analysis & Summarization** - Read, summarize, explain, and analyze local files ("summarize this config", "explain what's in main.py")
- **Smart Context Condensation** - Large context is LLM-summarized instead of blindly truncated
- **Security First** - AST validation, path allowlists, `rm -rf /` heuristics, FTP credential blocking, mandatory confirmation gates ([details](docs/SECURITY.md))
- **Ephemeral Azure Sandboxing** - User-controlled cloud sandbox for untrusted commands
- **Runtime Settings** - `/settings` to switch models, update API keys, inspect system state
- **198 Automated Tests** - Full test suite with CI ([details](docs/TESTING.md))

## Architecture

```mermaid
%%{init: {"themeVariables": {"fontFamily": "monospace"}}}%%
graph TB
    classDef default fill:#fff,stroke:#000,stroke-width:3px,color:#000,font-weight:bold;
    classDef highlight fill:#ffe600,stroke:#000,stroke-width:3px,color:#000,font-weight:bold;
    classDef secondary fill:#ff4949,stroke:#000,stroke-width:3px,color:#000,font-weight:bold;
    classDef tertiary fill:#49baff,stroke:#000,stroke-width:3px,color:#000,font-weight:bold;
    classDef purple fill:#c77ae8,stroke:#000,stroke-width:3px,color:#000,font-weight:bold;
    subgraph "User Interface Layer"
        TUI[Terminal UI<br/>Rich Console + Prompt Toolkit]
        CLI[CLI Commands<br/>Typer Framework]
    end

    subgraph "Intelligence Layer - Multi-Brain System"
        Router[Decision Engine<br/>Groq: Kimi K2]:::secondary
        Chat[Chat Brain<br/>OpenRouter: GPT / Groq: Kimi]:::tertiary
        Planner[Task Planner<br/>Primary LLM Client]:::tertiary
        CmdGen[Command Generator<br/>Primary LLM Client]:::tertiary
    end

    subgraph "Memory System"
        Memory[Supermemory<br/>RAG + Context Storage]:::highlight
    end

    subgraph "Execution Layer"
        Orchestrator[Orchestrator<br/>Multi-Step Task Execution]:::purple
        Executor[Command Executor<br/>Safety Checks + Confirmation]
        Browser[Browser Manager<br/>browser-use + API Key Rotation]:::purple
        Package[Package Manager<br/>apt/dnf/pacman]
    end

    subgraph "Core Services"
        Config[Config Manager<br/>~/.config/nexus]
        System[System Detector<br/>OS + Package Manager]
        Security[Security Module<br/>Command Validation]
    end

    TUI --> Router
    CLI --> Router
    Router --> Chat
    Router --> Planner
    Router --> CmdGen

    Chat --> Memory
    Planner --> Memory
    CmdGen --> Memory

    Planner --> Orchestrator
    CmdGen --> Executor

    Orchestrator --> Browser
    Orchestrator --> Executor

    Executor --> Security
    Browser --> Executor
    Package --> Executor

    Config --> System
    System --> Package

```

## AI Model Map

| Component | Default Model | Purpose |
|-----------|--------------|---------|
| **Router** | Groq: Kimi K2 | Fast intent classification (~10-100ms) |
| **Chat** | OpenRouter: GPT | Conversations, command generation, planning |
| **Browser** | Gemini Flash | Web automation with vision |
| **Search** | Gemini 2.5 Flash | Web search with Google grounding |
| **Condenser** | Groq (fastest available) | Context compression for large inputs |

All models are switchable via `/settings model`. Router now supports all 5 providers (Groq, OpenRouter, Gemini, Anthropic, GroqGPT). See [model_usage_guide.md](docs/model_usage_guide.md) for details.

### Failover Chain

```
Chat/Planner: OpenRouter → Anthropic → GroqGPT → Groq Kimi → Gemini → Mock
Router:       Groq Kimi → (fallback to Chat Brain)
```

## Installation

### Quick Install (pipx)

```bash
sudo apt update && sudo apt install -y pipx
pipx ensurepath    # restart terminal after this
pipx install "nexus-linux-assistant[all]"
~/.local/pipx/venvs/nexus-linux-assistant/bin/python -m playwright install chromium
nexus
```

### Virtual Environment

```bash
python3 -m venv ~/venvs/nexus
source ~/venvs/nexus/bin/activate
pip install "nexus-linux-assistant[all]"
playwright install chromium
nexus
```

### From Source

```bash
git clone <repository-url>
cd nexus
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[all]"
playwright install chromium
nexus
```

**Extras:** `[all]` = full stack. `[ai]` = AI only. `[browser]` = browser only. `[dev]` = tests.

### Prerequisites
- Python 3.10+
- Ubuntu, Debian, Fedora, or Arch Linux

## Usage

### Interactive Mode
```bash
nexus                    # Launch TUI
```

### CLI Commands
```bash
nexus chat "How do I check disk space?"
nexus install htop
nexus remove firefox
nexus update
nexus do "find all python files larger than 1MB"
nexus browse "Find MrBeast on YouTube"
nexus search "best restaurants in Dubai"
```

### TUI Slash Commands

| Command | Description |
|---------|-------------|
| `/settings` | View/change models, API keys |
| `/settings model` | Interactive model picker |
| `/settings key` | Update API keys |
| `/browse <task>` | Web automation |
| `/search <query>` | Grounded web search |
| `/find <query>` | File/content search |
| `/read <path>` | Read file with syntax highlighting |
| `/do <request>` | Generate and run a shell command |
| `/think` | Toggle thinking/reasoning display |
| `/status` | System status |

### Settings & Model Selection

Nexus keeps one catalog of allowed models per task (`model_catalog.py`). Onboarding and `/settings model` both draw from it.

```bash
/settings model              # Interactive picker
/settings model chat gpt-4o  # Direct switch
/settings key openrouter      # Update API key
```

Saved to `~/.config/nexus/config.json`. Unknown model IDs in config are safely ignored at startup.

## Environment Variables

| Variable | Purpose | Required |
|----------|---------|----------|
| `GOOGLE_API_KEY` | Gemini models, search | For search |
| `OPENROUTER_API_KEY` | GPT models via OpenRouter | For best chat |
| `GROQ_API_KEY` | Fast routing decisions | Optional |
| `ANTHROPIC_API_KEY` | Claude models | Optional |
| `SUPERMEMORY_API_KEY` | Memory/RAG (BYOK) | Optional |
| `BROWSER_USE_API_KEY` | Cloud browser automation | Optional |

## Project Structure

```
nexus/
├── src/jarvis/
│   ├── ai/                      # AI clients and intelligence
│   │   ├── llm_client.py        # Model abstractions + prompt enrichment
│   │   ├── command_generator.py  # NL → shell with SafetyCheck
│   │   ├── context_condenser.py # Smart LLM-based context compression
│   │   ├── decision_engine.py   # Fast heuristic + slow LLM routing
│   │   └── memory_client.py     # Supermemory RAG integration
│   ├── core/                    # Core systems
│   │   ├── orchestrator.py      # Multi-step execution + self-healing
│   │   ├── executor.py          # Command execution + audit + secure sudo
│   │   ├── security.py          # AST validation + pattern blacklist
│   │   ├── config_manager.py    # API keys + preferences (chmod 600)
│   │   ├── model_catalog.py     # Task ↔ model catalog
│   │   └── ...                  # audit_logger, session, system_detector
│   ├── modules/                 # browser_manager, package_manager
│   ├── ui/                      # console_app (TUI), onboarding
│   └── main.py                  # CLI entry point (Typer)
├── tests/                       # 198 pytest tests
├── docs/                        # Detailed documentation
└── pyproject.toml
```

## Documentation

| Document | Content |
|----------|---------|
| [Architecture Overview](docs/architecture_overview.md) | Deep-dive with Mermaid diagrams |
| [Security Model](docs/SECURITY.md) | Threat model, defences, known limitations |
| [Test Suite](docs/TESTING.md) | Test coverage map with 198 test details |
| [Model Usage Guide](docs/model_usage_guide.md) | Which AI model is used where and why |
| [Future Scope](docs/FUTURE_SCOPE.md) | Roadmap, shipped features, backlog |
| [API Key Rotation](docs/API_KEY_ROTATION_GUIDE.md) | Google API key rotation setup |
| [Memory Persistence](docs/MEMORY_PERSISTENCE_GUIDE.md) | Supermemory integration guide |

## Roadmap

**Shipped:** Multi-brain architecture, Supermemory RAG, browser automation, self-healing execution, `DIRECT_EXECUTE`, `/settings` + model catalog, `LLM_PROCESS` (file analysis), Context Condenser, expanded router models, planner system-ops knowledge, path allowlists, FTP checks, Azure sandboxing, persistent sessions, audit logging, 198-test suite, CI.

**Up next:** Rollback checkpoints, `FILE_APPEND`/`FILE_PATCH`, LLM rate limiting & budgets, parallel step execution, model discovery.

**Long-term:** MCP integration, Git assistant, Docker management, natural language cron jobs.

See [FUTURE_SCOPE.md](docs/FUTURE_SCOPE.md) for full details.

## Releasing (maintainers)

1. Bump `version` in `pyproject.toml`.
2. Tag: `git tag v0.1.0 && git push origin v0.1.0`.
3. CI builds sdist + wheel, uploads to GitHub Release, publishes to PyPI via OIDC.

## Contributing

Contributions are welcome! This project is actively developed.

## License

[MIT](LICENSE)

## Author

Created by Garvit (garvitjoshi543@gmail.com)

---

**Nexus** - Your intelligent Linux companion, powered by multiple AI brains working in harmony.
