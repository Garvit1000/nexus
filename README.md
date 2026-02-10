# Nexus - AI-Powered Linux Assistant

**Nexus** is an intelligent, multilingual terminal-based Linux assistant that combines multiple AI models, memory systems, and automation capabilities to help you manage your system, browse the web, generate videos, and execute complex tasks through natural language.

## ✨ Key Features

- 🧠 **Multi-Brain AI Architecture** - Specialized models for different tasks
- 🌐 **Multilingual Support** - 9+ Indic languages via Sarvam.ai integration
- 🎤 **Voice Commands** - Speech-to-text and text-to-speech
- 🤖 **Autonomous Web Browsing** - Automated tasks with browser-use
- 🎬 **AI Video Generation** - Create videos from text descriptions
- 💾 **Persistent Memory** - RAG-based context retention with Supermemory
- 🔄 **Self-Healing Execution** - Auto-fix failed commands
- 🎯 **Intelligent Intent Recognition** - Context-aware decision making
- 🔐 **Security First** - Command validation and confirmation

## 🏗️ Architecture Overview

Nexus follows a modular, multi-brain architecture with robust decision-making:

```mermaid
graph TB
    subgraph "User Interface Layer"
        TUI[Terminal UI<br/>Rich Console + Multilingual]
        CLI[CLI Commands<br/>Typer Framework]
        Voice[Voice Interface<br/>Sarvam STT/TTS]
    end
    
    subgraph "Intelligence Layer - Multi-Brain System"
        Session[Session Manager<br/>Context Tracking]
        Router[Decision Engine<br/>Groq: Kimi K2 + Semantic Matching]
        Chat[Chat Brain<br/>OpenRouter: GPT / Groq: Kimi]
        Planner[Task Planner<br/>Primary LLM Client]
        CmdGen[Command Generator<br/>Primary LLM Client]
    end
    
    subgraph "Language Services"
        Sarvam[Sarvam.ai Client<br/>Translation + Speech]
        Translator[Translator Module<br/>Auto-detect + Preserve Terms]
        MultiUI[Multilingual UI<br/>Bilingual Display]
    end
    
    subgraph "Memory System"
        Memory[Supermemory<br/>RAG + Context Storage]
    end
    
    subgraph "Execution Layer"
        Orchestrator[Orchestrator<br/>Multi-Step Task Execution]
        Executor[Command Executor<br/>Safety Checks + Confirmation]
        Browser[Browser Manager<br/>browser-use + API Key Rotation]
        Video[Video Manager<br/>Remotion + AI Code Gen]
        Package[Package Manager<br/>apt/dnf/pacman]
    end
    
    subgraph "Core Services"
        Config[Config Manager<br/>API Key Rotation]
        System[System Detector<br/>OS + Package Manager]
        Security[Security Module<br/>Command Validation]
    end
    
    TUI --> Session
    CLI --> Session
    Voice --> Translator
    
    Session --> Router
    Router --> Chat
    Router --> Planner
    Router --> CmdGen
    
    Translator --> Sarvam
    MultiUI --> TUI
    Sarvam --> Voice
    
    Chat --> Memory
    Planner --> Memory
    CmdGen --> Memory
    
    Planner --> Orchestrator
    CmdGen --> Executor
    
    Orchestrator --> Browser
    Orchestrator --> Executor
    
    Executor --> Security
    Browser --> Executor
    Video --> Executor
    Package --> Executor
    
    Config --> System
    System --> Package
    
    style Router fill:#ff6b6b
    style Chat fill:#4ecdc4
    style Memory fill:#95e1d3
    style Orchestrator fill:#f38181
    style Browser fill:#aa96da
    style Video fill:#fcbad3
    style Sarvam fill:#ffd93d
    style Session fill:#6c5ce7
```

## 🧠 AI Model Usage Map

Nexus uses different AI models for specialized tasks, creating an intelligent "multi-brain" system:

| Component | Model Used | Purpose | Why This Model? |
|-----------|------------|---------|-----------------|
| **Router / Decision Engine** | **Groq: Kimi K2** (`moonshotai/kimi-k2-instruct-0905`) | Fast intent classification & routing | Ultra-fast inference (⚡ Groq), robust decision framework |
| **Chat Brain** | **OpenRouter: GPT** (default) or **Groq: Kimi** | Natural language conversations | Best reasoning & context understanding |
| **Command Generator** | Primary LLM Client | Convert natural language → shell commands | Strong code generation capabilities |
| **Task Planner** | Primary LLM Client | Break complex tasks into steps | Strategic thinking & planning with smart CHECK logic |
| **Browser Agent** | **Gemini Flash** (`gemini-flash-latest`) | Web automation & navigation | Vision support + fast inference for UI understanding |
| **Video Code Generator** | **Gemini 2.5 Flash** | Generate React/Remotion code | Excellent at code generation with low latency |
| **Search Tool** | **Gemini 2.5 Flash** | Web search with citations | Native Google Search integration |
| **Translation Engine** | **Sarvam.ai** | Multilingual translation + speech | Native Indic language support, TTS/STT |

## 🌐 Multilingual Support (NEW!)

Nexus now supports **9+ Indic languages** via Sarvam.ai integration:

- **Translation**: Auto-detect and translate between English and Hindi, Tamil, Telugu, Bengali, Malayalam, Kannada, Gujarati, Marathi, Punjabi
- **Voice Commands**: Speech-to-text in your preferred language
- **Voice Responses**: Text-to-speech output in regional languages
- **Technical Term Preservation**: Keeps terms like "Docker", "MySQL" intact during translation
- **Code-Mixed Support**: Handles Hinglish and similar mixed languages

### Quick Multilingual Commands

```bash
# Set preferred language
nexus lang hi-IN

# Translate text
nexus translate "नमस्ते" --to en

# Voice command (Hindi)
nexus voice --lang hi-IN --duration 5

# Text-to-speech
nexus speak "Hello" --lang ta-IN
```

See [SARVAM_INTEGRATION.md](SARVAM_INTEGRATION.md) for detailed multilingual usage.

## 🎯 Intelligent Decision Making

### Enhanced Context-Aware System

Nexus features a **robust decision engine** with semantic understanding:

1. **Smart Context Detection**
   - Distinguishes between new requests and references to previous actions
   - "show me latest news in delhi" → NEW request (detailed query)
   - "show me that" → CONTEXT reference (pronoun-based)

2. **Semantic Similarity Matching**
   - Prevents false cache matches between unrelated queries
   - Uses keyword overlap (30% threshold) for relatedness
   - Example: Won't confuse "download video" with "show news"

3. **Intelligent Planning**
   - Distinguishes static (files) vs dynamic (news/weather) data
   - Only adds CHECK steps when logically appropriate
   - Minimal plans focused on user's actual request

See [ROBUSTNESS_FIXES.md](ROBUSTNESS_FIXES.md) for technical details.

## 📊 System Flow Diagrams

### 1. Enhanced User Input Processing Flow

```mermaid
sequenceDiagram
    participant User
    participant Session
    participant Translator
    participant DecisionEngine
    participant Router
    participant Orchestrator
    
    User->>Session: Input (any language)
    
    alt Non-English Input
        Session->>Translator: Detect language
        Translator->>Translator: Auto-translate to English
        Translator-->>Session: Translated text
    end
    
    Session->>Session: Check context reference
    
    alt Context Reference Detected
        Session->>Session: Semantic similarity check
        alt Related to previous query
            Session-->>User: Return cached result
        end
    end
    
    Session->>DecisionEngine: Analyze intent
    
    alt Fast Path: Heuristic Match
        DecisionEngine-->>Session: Intent(COMMAND)
    else Slow Path: LLM Analysis
        DecisionEngine->>Router: Classify with framework
        Router-->>DecisionEngine: Intent + Reasoning
    end
    
    alt Action: PLAN
        Session->>Orchestrator: Create smart plan
        Orchestrator-->>User: Execute with minimal steps
    end
```

### 2. Multilingual Interaction Flow

```mermaid
sequenceDiagram
    participant User
    participant Voice
    participant Translator
    participant Sarvam
    participant Agent
    participant MultilingualUI
    
    alt Voice Input
        User->>Voice: Speak command (Hindi)
        Voice->>Sarvam: STT (hi-IN)
        Sarvam-->>Voice: Transcribed text
    end
    
    Voice->>Translator: "सिस्टम अपडेट करो"
    Translator->>Sarvam: Detect language
    Sarvam-->>Translator: hi-IN detected
    
    Translator->>Sarvam: Translate to English
    Sarvam-->>Translator: "Update system"
    
    Translator->>Agent: Execute command
    Agent-->>Translator: Result
    
    Translator->>Sarvam: Translate response to hi-IN
    Sarvam-->>Translator: Hindi response
    
    Translator->>MultilingualUI: Display bilingual
    MultilingualUI-->>User: English + Hindi side-by-side
    
    opt Voice Output
        MultilingualUI->>Sarvam: TTS (hi-IN)
        Sarvam-->>User: Audio output
    end
```

### 3. API Key Rotation System

```mermaid
sequenceDiagram
    participant Browser
    participant Rotator
    participant API1 as Gemini Key 1
    participant API2 as Gemini Key 2
    participant API3 as Gemini Key 3
    
    Browser->>Rotator: Request with current key
    Rotator->>API1: Execute task (Key 1)
    
    alt Success
        API1-->>Rotator: Result
        Rotator->>Rotator: Mark success
        Rotator-->>Browser: Return result
    else Rate Limit / Quota Error
        API1-->>Rotator: 429 Error
        Rotator->>Rotator: Mark Key 1 exhausted
        Rotator->>API2: Retry with Key 2
        
        alt Success
            API2-->>Rotator: Result
            Rotator-->>Browser: Return result
        else All Keys Exhausted
            Rotator-->>Browser: Error message
        end
    end
```

## 🔧 Component Details

### AI Clients (`src/jarvis/ai/`)

#### `llm_client.py` - LLM Abstraction Layer
- **`LLMClient`** (Abstract Base): Memory integration, prompt enrichment
- **`GoogleGenAIClient`**: Gemini models with Google Search grounding
- **`OpenRouterClient`**: Access to GPT models via OpenRouter
- **`GroqClient`**: Ultra-fast inference for routing decisions
- **`MockLLMClient`**: Fallback when no API keys configured

#### `sarvam_client.py` - Multilingual AI Client (NEW!)
- Translation between English and 9 Indic languages
- Speech-to-text (STT) for voice commands
- Text-to-speech (TTS) for audio responses
- Language detection with script analysis
- Technical term preservation during translation

#### `decision_engine.py` - Intelligent Intent Classification
- **Enhanced Prompt**: Location awareness, news queries, trending data
- **Intelligent Analysis Framework**: Data Source → Location → Quantity → Complexity
- **Fast Path**: Regex-based heuristics for common commands
- **Slow Path**: LLM-based intent analysis with robust examples
- Routes to: COMMAND, CHAT, PLAN, SEARCH, BROWSE, VIDEO

#### `memory_client.py` - Supermemory Integration
- Stores: System context, command feedback, successful plans
- Retrieves: Relevant context for RAG-enhanced prompts
- Enables learning from past successes/failures

### Core Systems (`src/jarvis/core/`)

#### `session_manager.py` - Context & Cache Management (ENHANCED!)
- **Smart Context Detection**: Distinguishes new requests from references
- **Semantic Similarity**: 30% keyword overlap threshold
- **Recent History Tracking**: 10-minute context window
- **Bilingual Session Support**: Tracks language preferences

#### `orchestrator.py` - Multi-Step Task Execution (IMPROVED!)
- **Intelligent Planner**: Task-type recognition (data retrieval vs downloads)
- **Smart CHECK Logic**: Only when appropriate for static resources
- **Minimal Plans**: One step if possible, no over-engineering
- **Self-Healing**: Auto-fixes failed commands using LLM reflection
- **Live UI**: Real-time progress tracking with Rich tables

#### `api_key_rotator.py` - API Key Management (NEW!)
- Automatic rotation across multiple API keys
- Quota exhaustion detection (429, 404 errors)
- Success/failure tracking per key
- Configurable max retries

#### `executor.py` - Safe Command Execution
- Security checks via `SafetyCheck` module
- User confirmation for dangerous commands
- Dry-run mode support
- Interactive mode for tools like `apt`, `npm`

#### `config_manager.py` - Configuration Management
- Stores API keys, preferences in `~/.config/jarvis/config.json`
- Environment variable overrides
- Multiple API key support for rotation
- Language preferences

### Modules (`src/jarvis/modules/`)

#### `translator.py` - Translation Orchestration (NEW!)
- Auto-detect input language
- Translate to/from English
- Preserve technical terms (Docker, MySQL, etc.)
- Handle code-mixed text (Hinglish)
- Voice command processing pipeline

#### `browser_manager.py` - Web Automation (ENHANCED!)
- **Local Mode**: browser-use library with Playwright
- **Cloud Mode**: BrowserUse SDK for headless execution
- **API Key Rotation**: Automatic failover on quota errors
- **Smart Downloads**: ~/Downloads tracking with pattern matching
- Uses Gemini Flash for vision-based UI understanding

#### `video_manager.py` - AI Video Generation
- Creates Remotion workspace automatically
- Generates React/TypeScript code using Gemini 2.5 Flash
- Validation loop: TypeScript compilation → Auto-fix → Retry
- Renders videos using Remotion CLI

#### `package_manager.py` - System Package Management
- Unified interface for apt/dnf/pacman
- Install, remove, update operations
- Automatic sudo handling

### UI Layer (`src/jarvis/ui/`)

#### `multilingual_ui.py` - Multilingual Display (NEW!)
- Beautiful bilingual output (side-by-side)
- Language-specific styling and fonts
- Translation result panels
- Voice status indicators

#### `console_app.py` - Terminal User Interface (ENHANCED!)
- **Rich Console**: Panels, tables, markdown rendering
- **Prompt Toolkit**: Async input with syntax highlighting
- **Auto-Translation**: Transparent multilingual support
- **Session Management**: Context-aware responses
- **Command Handlers**: `/video`, `/browse`, `/search`, `/translate`, `/voice`, etc.

#### `onboarding.py` - First-Run Setup
- Collects API keys (Google, OpenRouter, Groq, Sarvam)
- Configures Supermemory integration
- Language preference setup
- Multiple key support for rotation

## 🚀 Installation

### Prerequisites
- Python 3.10 or higher
- Node.js (for video generation)
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

### Optional: Voice Support

For voice commands, install PyAudio:

```bash
# Ubuntu/Debian
sudo apt-get install portaudio19-dev python3-pyaudio

# Then install Python dependencies
pip install -r requirements.txt
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
Launches the full Terminal UI with decision engine, memory, and multilingual support.

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

#### Video Generation
```bash
nexus video "Create a 5-second countdown timer"
```

#### Web Search
```bash
nexus search "best restaurants in Dubai"
```

#### Translation (NEW!)
```bash
nexus translate "नमस्ते, मैं कैसे मदद कर सकता हूं?"
nexus translate "Hello" --to hi-IN
```

#### Voice Commands (NEW!)
```bash
nexus voice --lang hi-IN --duration 5
nexus speak "नमस्ते" --lang hi-IN
```

#### Language Settings (NEW!)
```bash
nexus lang hi-IN       # Set Hindi
nexus langs            # List supported languages
```

## 🧪 Advanced Features

### Multilingual Voice Assistant
Nexus supports full voice interaction in 9+ languages:
- Record voice commands in your language
- Automatic transcription and translation
- Execute commands from voice input
- Audio responses in your preferred language

### Robust Context Management
- Semantic understanding prevents false cache matches
- Distinguishes new requests from context references
- Keyword-based similarity checking (30% threshold)
- 10-minute context window for recent actions

### Intelligent Task Planning
- Data type awareness (static vs dynamic)
- Minimal step generation
- Appropriate use of CHECK steps
- Focus on user's actual intent

### API Key Rotation
- Automatic failover across multiple keys
- Quota exhaustion detection
- Per-key success/failure tracking
- Supports up to 4 keys per service

### Memory System
Nexus remembers:
- **System Context**: OS, package manager
- **Command Feedback**: Success/failure of past commands
- **Proven Plans**: Multi-step tasks that worked
- **User Preferences**: Language, learned from interactions

### Self-Healing Execution
If a command fails, Nexus:
1. Analyzes the error
2. Asks LLM to fix the command
3. Retries automatically

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
│   │   ├── sarvam_client.py   # Multilingual AI (NEW!)
│   │   ├── command_generator.py
│   │   ├── decision_engine.py  # Enhanced with robust logic
│   │   └── memory_client.py
│   ├── core/                  # Core systems
│   │   ├── orchestrator.py    # Smart planning (IMPROVED!)
│   │   ├── session_manager.py # Context tracking (ENHANCED!)
│   │   ├── api_key_rotator.py # Key rotation (NEW!)
│   │   ├── executor.py
│   │   ├── config_manager.py
│   │   ├── system_detector.py
│   │   └── security.py
│   ├── modules/               # Feature modules
│   │   ├── translator.py      # Translation module (NEW!)
│   │   ├── browser_manager.py # With key rotation
│   │   ├── video_manager.py
│   │   └── package_manager.py
│   ├── ui/                    # User interfaces
│   │   ├── console_app.py     # TUI with multilingual
│   │   ├── multilingual_ui.py # Bilingual display (NEW!)
│   │   └── onboarding.py
│   └── main.py               # CLI entry point
├── pyproject.toml
├── README.md                 # This file
├── SARVAM_INTEGRATION.md     # Multilingual guide
├── ROBUSTNESS_FIXES.md       # Architecture improvements
├── test_robustness_fixes.py  # Validation tests
└── .env.example              # Environment template
```

## 🔑 Environment Variables

| Variable | Purpose | Required |
|----------|---------|----------|
| `GOOGLE_API_KEY` | Gemini models, search | For search feature |
| `GOOGLE_API_KEY_2`, `_3`, `_4` | Key rotation | Optional |
| `OPENROUTER_API_KEY` | GPT models via OpenRouter | For best chat quality |
| `GROQ_API_KEY` | Fast routing decisions | Optional (fallback) |
| `SARVAM_API_KEY` | Multilingual translation + speech | Optional |
| `SUPERMEMORY_API_KEY` | Memory/RAG system | Optional |
| `BROWSER_USE_API_KEY` | Cloud browser automation | Optional |

## 🧪 Testing

Run robustness validation tests:

```bash
python3 test_robustness_fixes.py
```

Tests cover:
- Session manager context detection
- Semantic similarity matching
- Decision engine heuristics
- Prompt quality validation

## 🛣️ Roadmap

Recent Additions:
- ✅ Sarvam.ai multilingual integration (9+ languages)
- ✅ Voice commands (STT/TTS)
- ✅ API key rotation system
- ✅ Robust context management
- ✅ Intelligent task planning
- ✅ Semantic similarity matching

Coming Soon:
- 🔄 AppImage support
- 🔄 .deb file installation
- 🔄 MCP (Model Context Protocol) integration
- 🔄 Git assistant
- 🔄 Docker management
- 🔄 Natural language cron jobs
- 🔄 More language support (beyond Indic)

See [plan.md](plan.md) for detailed roadmap.

## 📚 Documentation

- [SARVAM_INTEGRATION.md](SARVAM_INTEGRATION.md) - Complete multilingual guide
- [ROBUSTNESS_FIXES.md](ROBUSTNESS_FIXES.md) - Architecture improvements & technical details
- [TESTING_GUIDE.md](TESTING_GUIDE.md) - Testing procedures
- [API_KEY_ROTATION_GUIDE.md](API_KEY_ROTATION_GUIDE.md) - Key rotation setup

## 🤝 Contributing

Contributions are welcome! This project is actively developed.

Areas for contribution:
- Additional language support
- New AI model integrations
- Enhanced security features
- Performance optimizations

## 📄 License

[Add your license here]

## 👤 Author

Created by Garvit (garvitjoshi543@gmail.com)

---

**Nexus** - Your intelligent multilingual Linux companion, powered by multiple AI brains working in harmony.
