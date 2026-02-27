# Nexus - AI-Powered Linux Assistant

**Nexus** is an intelligent, terminal-based Linux assistant that combines multiple AI models, memory systems, and automation capabilities to help you manage your system, browse the web, generate videos, and execute complex tasks through natural language.

## ✨ Key Features

- 🧠 **Multi-Brain AI Architecture** - Specialized models for different tasks
- 🤖 **Autonomous Web Browsing** - Automated tasks with browser-use
- 💾 **Persistent Memory** - RAG-based context retention with Supermemory
- 🔄 **Self-Healing Execution** - Auto-fix failed commands and auto-failover LLM routing
- 🎯 **Intelligent Intent Recognition** - Context-aware decision making
- 🔐 **Security First** - AST-based defensive command validation and user confirmation

## 🏗️ Architecture Overview

Nexus follows a modular, multi-brain architecture where different AI models handle specialized tasks:

```mermaid
graph TB
    subgraph "User Interface Layer"
        TUI[Terminal UI<br/>Rich Console + Prompt Toolkit]
        CLI[CLI Commands<br/>Typer Framework]
    end
    
    subgraph "Intelligence Layer - Multi-Brain System"
        Router[Decision Engine<br/>Groq: Kimi K2]
        Chat[Chat Brain<br/>OpenRouter: GPT / Groq: Kimi]
        Planner[Task Planner<br/>Primary LLM Client]
        CmdGen[Command Generator<br/>Primary LLM Client]
    end
    
    subgraph "Memory System"
        Memory[Supermemory<br/>RAG + Context Storage]
    end
    
    subgraph "Execution Layer"
        Orchestrator[Orchestrator<br/>Multi-Step Task Execution]
        Executor[Command Executor<br/>Safety Checks + Confirmation]
        Browser[Browser Manager<br/>browser-use + API Key Rotation]
        Package[Package Manager<br/>apt/dnf/pacman]
    end
    
    subgraph "Core Services"
        Config[Config Manager<br/>~/.config/jarvis]
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
    
    style Router fill:#ff6b6b
    style Chat fill:#4ecdc4
    style Memory fill:#95e1d3
    style Orchestrator fill:#f38181
    style Browser fill:#aa96da
    style Session fill:#6c5ce7
```

## 🧠 AI Model Usage Map

Nexus uses different AI models for different purposes, creating a specialized "multi-brain" system:

| Component | Model Used | Purpose | Why This Model? |
|-----------|------------|---------|-----------------|
| **Router / Decision Engine** | **Groq: Kimi K2** (`moonshotai/kimi-k2-instruct-0905`) | Fast intent classification & routing | Ultra-fast inference (⚡ Groq), robust decision framework |
| **Chat Brain** | **OpenRouter: GPT** (default) or **Groq: Kimi** | Natural language conversations | Best reasoning & context understanding |
| **Command Generator** | Primary LLM Client | Convert natural language → shell commands | Strong code generation capabilities |
| **Task Planner** | Primary LLM Client | Break complex tasks into steps | Strategic thinking & planning with smart CHECK logic |
| **Browser Agent** | **Gemini Flash** (`gemini-flash-latest`) | Web automation & navigation | Vision support + fast inference for UI understanding |
| **Search Tool** | **Gemini 2.5 Flash** | Web search with citations | Native Google Search integration |

### Model Priority & Auto-Failover System

Nexus implements a robust failover chain for critical components to ensure maximum uptime, seamlessly bypassing API rate limits (e.g. 429 errors from free-tier models).

```mermaid
graph LR
    subgraph "Decision/Router Brain"
        R1[Groq: Kimi K2] --> R2[Fallback to Chat Brain]
    end
    
    subgraph "Chat & Planner Priority (Auto-Failover)"
        C1[OpenRouter: GPT] --> C2[Groq: Kimi] --> C3[Google: Gemini] --> C4[Mock Mode]
    end
    
    subgraph "Specialized Tasks"
        S1[Browser: Gemini Flash]
        S2[Video: Gemini 2.5 Flash]
        S3[Search: Gemini 2.5 Flash]
    end
    
    R2 --> C1
    
    style R1 fill:#ff6b6b
    style C1 fill:#4ecdc4
    style S1 fill:#aa96da
    style S2 fill:#fcbad3
    style S3 fill:#95e1d3
```

## 📊 System Flow Diagrams

### 1. User Input Processing Flow

```mermaid
sequenceDiagram
    participant User
    participant TUI
    participant DecisionEngine
    participant Router as Router Brain<br/>(Groq: Kimi)
    participant ChatBrain
    participant Orchestrator
    participant Executor
    
    User->>TUI: Input text
    TUI->>DecisionEngine: analyze(input)
    
    alt Fast Path: Heuristic Match
        DecisionEngine->>DecisionEngine: Regex patterns<br/>(install, remove, update)
        DecisionEngine-->>TUI: Intent(COMMAND)
    else Slow Path: AI Analysis
        DecisionEngine->>Router: Classify intent
        Router-->>DecisionEngine: JSON response
        DecisionEngine-->>TUI: Intent(COMMAND/CHAT/PLAN)
    end
    
    alt Action: COMMAND
        TUI->>Executor: Execute command
        Executor-->>User: Result
    else Action: CHAT
        TUI->>ChatBrain: generate_response()
        ChatBrain-->>User: Response
    else Action: PLAN
        TUI->>Orchestrator: execute_plan()
        Orchestrator-->>User: Multi-step execution
    end
```

### 2. Complex Task Orchestration Flow

```mermaid
sequenceDiagram
    participant User
    participant Orchestrator
    participant Planner
    participant Memory
    participant Browser
    participant Executor
    
    User->>Orchestrator: "Install Postman"
    Orchestrator->>Planner: create_plan(request)
    
    Planner->>Memory: Query proven plans
    Memory-->>Planner: RAG context
    
    Planner->>Planner: Generate step-by-step plan
    Planner-->>Orchestrator: [CHECK, BROWSER, TERMINAL]
    
    loop For each step
        alt Step: CHECK
            Orchestrator->>Executor: which postman
            alt Already installed
                Executor-->>Orchestrator: Exit code 0
                Orchestrator-->>User: ✅ Already installed, skipping
            else Not found
                Executor-->>Orchestrator: Exit code 1
                Orchestrator->>Orchestrator: Continue to next step
            end
        else Step: BROWSER
            Orchestrator->>Browser: Download Postman
            Browser-->>Orchestrator: File path
        else Step: TERMINAL
            Orchestrator->>Executor: Install downloaded file
            Executor-->>Orchestrator: Success/Failure
        end
        
        alt Step failed
            Orchestrator->>Planner: reflect_and_fix(error)
            Planner-->>Orchestrator: Fixed command
            Orchestrator->>Executor: Retry
        end
    end
    
    Orchestrator->>Memory: Save successful plan
    Orchestrator-->>User: ✅ Task complete
```

### 3. Memory System Integration

```mermaid
graph TB
    subgraph "Input Sources"
        UserReq[User Requests]
        CmdResult[Command Results]
        Plans[Successful Plans]
        SysInfo[System Context]
    end
    
    subgraph "Supermemory Storage"
        Memory[(Supermemory<br/>Vector Database)]
    end
    
    subgraph "RAG Retrieval"
        Query[Query Memory]
        Context[Enrich Prompts]
    end
    
    subgraph "AI Components"
        Chat[Chat Brain]
        CmdGen[Command Generator]
        Planner[Task Planner]
    end
    
    UserReq --> Memory
    CmdResult --> Memory
    Plans --> Memory
    SysInfo --> Memory
    
    Chat --> Query
    CmdGen --> Query
    Planner --> Query
    
    Query --> Memory
    Memory --> Context
    Context --> Chat
    Context --> CmdGen
    Context --> Planner
    
    style Memory fill:#95e1d3
    style Context fill:#f9ca24
```

## 🔧 Component Details

### AI Clients (`src/jarvis/ai/`)

#### `llm_client.py` - LLM Abstraction Layer
- **`LLMClient`** (Abstract Base): Memory integration, prompt enrichment
- **`GoogleGenAIClient`**: Gemini models with Google Search grounding
- **`OpenRouterClient`**: Access to GPT models via OpenRouter
- **`GroqClient`**: Ultra-fast inference for routing decisions
- **`MockLLMClient`**: Fallback when no API keys configured

#### `command_generator.py` - Natural Language → Shell Commands
- Converts user requests to executable shell commands
- Uses RAG to retrieve proven solutions from memory
- Implements safety guidelines and idempotency principles

#### `decision_engine.py` - Intent Classification
- **Fast Path**: Regex-based heuristics for common commands
- **Slow Path**: LLM-based intent analysis with robust examples
- Routes to: COMMAND, CHAT, PLAN, SEARCH, BROWSE

#### `memory_client.py` - Supermemory Integration
- Stores: System context, command feedback, successful plans, user preferences
- Retrieves: Relevant context for RAG-enhanced prompts
- Enables learning from past successes/failures

### Core Systems (`src/jarvis/core/`)

#### `orchestrator.py` - Multi-Step Task Execution
- **Planner**: Breaks complex requests into steps (CHECK → BROWSER → TERMINAL)
- **Smart Resume**: Checks if files already exist before downloading
- **Self-Healing**: Auto-fixes failed commands using LLM reflection
- **Live UI**: Real-time progress tracking with Rich tables

#### `executor.py` & `security.py` - Safe Command Execution
- **AST-Based Command Validation**: Deep analysis of shell syntax to catch obfuscated attacks (e.g. `eval`, `cd / && rm -rf *`).
- Strict blacklist filtering (blocks `rm -rf /`, `mkfs`, fork bombs `:(){ :|:& };:`).
- User confirmation mandatory for dangerous or `sudo` operations.
- Dry-run mode support.

#### `config_manager.py` - Configuration Management
- Stores API keys, preferences in `~/.config/jarvis/config.json`
- Environment variable overrides
- Onboarding state tracking

#### `system_detector.py` - OS Detection
- Detects: Ubuntu, Debian, Fedora, Arch, etc.
- Identifies package manager: apt, dnf, pacman
- Provides system context to AI models

### Modules (`src/jarvis/modules/`)

#### `browser_manager.py` - Web Automation
- **Local Mode**: `browser-use` library with Playwright (headless=false for live view)
- **Cloud Mode**: BrowserUse SDK for headless execution
- Smart download handling (~/Downloads tracking)
- Uses Gemini Flash for vision-based UI understanding

#### `package_manager.py` - System Package Management
- Unified interface for apt/dnf/pacman
- Install, remove, update operations
- Automatic sudo handling

### UI Layer (`src/jarvis/ui/`)

#### `console_app.py` - Terminal User Interface
- **Rich Console**: Panels, tables, markdown rendering
- **Prompt Toolkit**: Async input with syntax highlighting
- **Session Management**: Context-aware responses
- **Command Handlers**: `/browse`, `/search`, etc.

#### `onboarding.py` - First-Run Setup
- Collects API keys (Google, OpenRouter, Groq)
- Configures Supermemory integration
- Saves to config file

## 🚀 Installation

### Prerequisites
- Python 3.10 or higher
- Supported OS: Ubuntu, Debian, Fedora, Arch Linux

### Setup

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd nexus
   ```

2. **Create virtual environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install package**:
   ```bash
   pip install -e .
   ```

4. **Configure API keys**:
   ```bash
   cp .env.example .env
   # Edit .env and add your API keys
   ```

5. **Run onboarding** (first-time only):
   ```bash
   nexus
   ```

### Global Access

Add to `~/.bashrc` or `~/.zshrc`:
```bash
alias nexus='/path/to/nexus/.venv/bin/nexus'
```

## 📖 Usage

### Interactive Mode (TUI)
```bash
nexus
```
Launches the full Terminal UI with decision engine, memory, and all features.

### CLI Commands

#### Chat
```bash
nexus chat "How do I check disk space?"
```

#### Package Management
```bash
nexus install htop
nexus remove firefox
nexus update
```

#### Natural Language Execution
```bash
nexus do "find all python files larger than 1MB"
```

#### Browser Automation
```bash
nexus browse "Find MrBeast on YouTube"
nexus browse --cloud "Download latest Chrome .deb"
```

#### Web Search
```bash
nexus search "best restaurants in Dubai"
```

## 🧪 Advanced Features

### Memory System
Nexus remembers:
- **System Context**: OS, package manager
- **Command Feedback**: Success/failure of past commands
- **Proven Plans**: Multi-step tasks that worked
- **User Preferences**: Learned from interactions

### Multi-Step Task Planning
Example: "Install Postman"
1. **CHECK**: `which postman` (idempotency)
2. **BROWSER**: Download from official site
3. **TERMINAL**: Extract and install

### Self-Healing & Fallback Execution
Nexus is built to gracefully handle failures at both the software and API level:
1. **Auto-Failover LLM Routing**: If the primary AI model timeouts or hits a rate limit (429) during planning, Nexus instantly intercepts the exception and reroutes the generation request to the next available fallback model (e.g., OpenRouter → Groq).
2. **Auto-Fix Commands**: If a terminal command fails, Nexus analyzes the `stderr`, asks the LLM to reflect and rewrite the command, and retries automatically.

### Smart Download Tracking
- Monitors `~/Downloads` for new files
- Filters out `.crdownload`, `.part`, `.tmp`
- Injects filenames into subsequent commands

## 🔐 Security

### Safety Checks
- Blocks destructive commands (`rm -rf /`)
- Requires confirmation for sudo operations
- Validates commands before execution
- Dry-run mode available

### Configuration
```bash
# Enable dry-run mode
export JARVIS_DRY_RUN=1

# Disable confirmations (not recommended)
# Set dangerous_mode: true in config
```

## 📁 Project Structure

```
nexus/
├── src/jarvis/
│   ├── ai/                    # AI clients and intelligence
│   │   ├── llm_client.py      # Model abstractions
│   │   ├── command_generator.py
│   │   ├── decision_engine.py
│   │   └── memory_client.py
│   ├── core/                  # Core systems
│   │   ├── orchestrator.py    # Multi-step execution
│   │   ├── executor.py        # Command execution
│   │   ├── config_manager.py
│   │   ├── system_detector.py
│   │   └── security.py
│   ├── modules/               # Feature modules
│   │   ├── browser_manager.py # With key rotation
│   │   └── package_manager.py
│   ├── ui/                    # User interfaces
│   │   ├── console_app.py     # TUI
│   │   └── onboarding.py
│   └── main.py               # CLI entry point
├── pyproject.toml
└── README.md
```

## 🔑 Environment Variables

| Variable | Purpose | Required |
|----------|---------|----------|
| `GOOGLE_API_KEY` | Gemini models, search | For search feature |
| `OPENROUTER_API_KEY` | GPT models via OpenRouter | For best chat quality |
| `GROQ_API_KEY` | Fast routing decisions | Optional (fallback to others) |
| `SUPERMEMORY_API_KEY` | Memory/RAG system | Optional |
| `BROWSER_USE_API_KEY` | Cloud browser automation | Optional |

## 🛣️ Roadmap

See [plan.md](plan.md) for detailed future features:
- ✅ Multi-brain AI architecture
- ✅ Memory system integration
- ✅ Browser automation
- ✅ Video generation
- 🔄 AppImage support
- 🔄 .deb file installation
- 🔄 MCP (Model Context Protocol) integration
- 🔄 Git assistant
- 🔄 Docker management
- 🔄 Natural language cron jobs

## 🤝 Contributing

Contributions are welcome! This project is actively developed.

## 📄 License

[Add your license here]

## 👤 Author

Created by Garvit (garvitjoshi543@gmail.com)

---

**Nexus** - Your intelligent Linux companion, powered by multiple AI brains working in harmony.
