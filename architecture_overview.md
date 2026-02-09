# Nexus Architecture Overview

This document provides a detailed architectural analysis of the Nexus AI-powered Linux assistant.

## System Architecture

Nexus implements a sophisticated multi-brain AI architecture where specialized models handle different cognitive tasks, similar to how different parts of the human brain specialize in different functions.

### Component Hierarchy

```mermaid
graph TB
    subgraph "Layer 1: User Interface"
        A[TUI - Terminal UI]
        B[CLI - Command Line]
    end
    
    subgraph "Layer 2: Intelligence - Multi-Brain System"
        C[Router Brain<br/>Groq: Kimi K2<br/>⚡ Fast Decisions]
        D[Chat Brain<br/>OpenRouter: GPT<br/>🧠 Reasoning]
        E[Task Planner<br/>Strategic Thinking]
        F[Command Generator<br/>Code Generation]
    end
    
    subgraph "Layer 3: Memory & Context"
        G[Supermemory<br/>RAG System<br/>📚 Learning]
    end
    
    subgraph "Layer 4: Execution"
        H[Orchestrator<br/>Multi-Step Coordination]
        I[Command Executor<br/>🛡️ Safety Layer]
    end
    
    subgraph "Layer 5: Specialized Modules"
        J[Browser Manager<br/>Gemini Flash<br/>🌐 Web Automation]
        K[Video Manager<br/>Gemini 2.5 Flash<br/>🎬 Code Generation]
        L[Package Manager<br/>apt/dnf/pacman<br/>📦 System Packages]
    end
    
    A --> C
    B --> C
    C --> D
    C --> E
    C --> F
    D --> G
    E --> G
    F --> G
    E --> H
    F --> I
    H --> I
    H --> J
    I --> J
    I --> K
    I --> L
```

## AI Model Distribution

### The Multi-Brain Philosophy

Nexus doesn't rely on a single AI model. Instead, it uses specialized models for different cognitive tasks:

| Brain Component | Model | Strengths | Use Cases |
|----------------|-------|-----------|-----------|
| **Limbic System (Router)** | Groq: Kimi K2 | Ultra-fast inference (10-100ms) | Intent classification, quick decisions |
| **Cortex (Chat)** | OpenRouter: GPT-4o | Deep reasoning, context understanding | Complex conversations, explanations |
| **Motor Cortex (Commands)** | Primary LLM | Code generation, shell expertise | Natural language → shell commands |
| **Prefrontal Cortex (Planning)** | Primary LLM | Strategic thinking, task breakdown | Multi-step task orchestration |
| **Visual Cortex (Browser)** | Gemini Flash | Vision + fast inference | Web UI understanding, automation |
| **Creative Cortex (Video)** | Gemini 2.5 Flash | Code generation, low latency | React/Remotion code generation |

### Model Selection Logic

```mermaid
flowchart TD
    Start[User Input] --> Router{Router Available?}
    Router -->|Yes| Groq[Groq: Kimi K2<br/>⚡ 10-100ms]
    Router -->|No| Fallback[Use Chat Brain]
    
    Groq --> Decision{Intent Type?}
    
    Decision -->|CHAT| ChatBrain{Chat Brain Priority}
    ChatBrain -->|1st| OpenRouter[OpenRouter: GPT]
    ChatBrain -->|2nd| GroqChat[Groq: Kimi]
    ChatBrain -->|3rd| Gemini[Google: Gemini]
    ChatBrain -->|4th| Mock[Mock Mode]
    
    Decision -->|COMMAND| CmdGen[Command Generator<br/>Primary LLM]
    Decision -->|PLAN| Planner[Task Planner<br/>Primary LLM]
    Decision -->|BROWSE| Browser[Browser Manager<br/>Gemini Flash]
    Decision -->|VIDEO| Video[Video Manager<br/>Gemini 2.5 Flash]
    Decision -->|SEARCH| Search[Search Tool<br/>Gemini 2.5 Flash]
    
    CmdGen --> Memory[(Supermemory<br/>RAG)]
    Planner --> Memory
    
    style Groq fill:#ff6b6b
    style OpenRouter fill:#4ecdc4
    style Memory fill:#95e1d3
    style Browser fill:#aa96da
    style Video fill:#fcbad3
```

## Data Flow Analysis

### 1. Simple Command Execution

```mermaid
sequenceDiagram
    participant U as User
    participant DE as Decision Engine
    participant R as Router (Groq)
    participant E as Executor
    participant S as Security
    
    U->>DE: "install htop"
    
    rect rgb(200, 220, 255)
        Note over DE: Fast Path (Heuristics)
        DE->>DE: Regex: install + package
        DE-->>U: Intent(COMMAND, /install, htop)
    end
    
    U->>E: Execute /install htop
    E->>S: check_command()
    S-->>E: ✅ Safe
    E->>E: Confirm with user
    E->>E: sudo apt-get install -y htop
    E-->>U: ✅ Success
```

### 2. Complex Task with Planning

```mermaid
sequenceDiagram
    participant U as User
    participant DE as Decision Engine
    participant R as Router (Groq)
    participant P as Planner
    participant M as Memory
    participant O as Orchestrator
    participant B as Browser
    participant E as Executor
    
    U->>DE: "Install Postman"
    
    rect rgb(255, 220, 200)
        Note over DE,R: Slow Path (AI Analysis)
        DE->>R: Classify intent
        R->>R: JSON: {action: "PLAN"}
        R-->>DE: Intent(PLAN)
    end
    
    DE->>O: execute_plan("Install Postman")
    O->>P: create_plan()
    
    P->>M: Query: "proven plan postman"
    M-->>P: RAG: Similar past installations
    
    P->>P: Generate steps:<br/>1. CHECK<br/>2. BROWSER<br/>3. TERMINAL
    P-->>O: TaskStep[]
    
    loop For each step
        alt Step 1: CHECK
            O->>E: which postman
            E-->>O: Exit code 1 (not found)
        end
        
        alt Step 2: BROWSER
            O->>B: Download Postman
            B->>B: Gemini Flash navigates UI
            B-->>O: ~/Downloads/postman.tar.gz
        end
        
        alt Step 3: TERMINAL
            O->>E: tar -xzf postman.tar.gz
            E-->>O: ✅ Success
        end
    end
    
    O->>M: Save successful plan
    O-->>U: ✅ Postman installed
```

### 3. Memory-Enhanced Command Generation

```mermaid
sequenceDiagram
    participant U as User
    participant CG as Command Generator
    participant M as Memory (Supermemory)
    participant LLM as Primary LLM
    participant E as Executor
    
    U->>CG: "find large python files"
    
    CG->>M: query_memory("feedback find files")
    M->>M: Vector search
    M-->>CG: Proven solutions:<br/>- find . -name "*.py" -size +1M<br/>- Success rate: 95%
    
    CG->>LLM: Prompt + RAG context
    LLM-->>CG: find . -name "*.py" -size +1M -exec ls -lh {} \;
    
    CG->>M: add_memory("User requested: 'find large python files'...")
    
    CG-->>E: Generated command
    E->>E: Execute with confirmation
    E-->>U: Results
    
    E->>M: add_memory("Feedback: Success")
```

## Key Design Patterns

### 1. Idempotency in Task Planning

Every complex task starts with a CHECK step:

```python
# Example plan for "Install Postman"
[
  {
    "action": "CHECK",
    "command": "which postman",
    "description": "Check if already installed"
  },
  # If CHECK succeeds (exit code 0), skip remaining steps
  {
    "action": "BROWSER",
    "command": "Download Postman...",
  },
  {
    "action": "TERMINAL",
    "command": "tar -xzf <DOWNLOADED_FILE>",
  }
]
```

### 2. Self-Healing Execution

When a command fails, Nexus attempts auto-recovery:

```python
# Orchestrator.py - reflect_and_fix()
if step.status == "failed":
    error_context = f"{step.output}\n(Context: {context})"
    fixed_command = llm.generate_response(
        f"Fix this command: {step.command}\nError: {error_context}"
    )
    # Retry with fixed command
```

### 3. Smart Download Tracking

Browser downloads are automatically tracked and injected:

```python
# Orchestrator.py - _wait_for_download()
before_files = set(os.listdir("~/Downloads"))
# ... browser downloads file ...
after_files = set(os.listdir("~/Downloads"))
new_file = (after_files - before_files)[0]

# Inject into next step
step.command = step.command.replace("<DOWNLOADED_FILE>", new_file)
```

### 4. RAG-Enhanced Prompts

All AI interactions are enriched with memory:

```python
# llm_client.py - enrich_prompt()
def enrich_prompt(self, prompt: str) -> str:
    if self.memory_client:
        context = self.memory_client.query_memory(prompt[:500])
        return f"--- MEMORY CONTEXT ---\n{context}\n\n{prompt}"
    return prompt
```

## Security Architecture

```mermaid
graph LR
    subgraph "Security Layers"
        A[User Input] --> B[Command Generator]
        B --> C[Security Check]
        C --> D{Dangerous?}
        D -->|Yes| E[Block/Warn]
        D -->|No| F[Sudo Check]
        F --> G{Requires Sudo?}
        G -->|Yes| H[User Confirmation]
        G -->|No| I[Execute]
        H --> I
    end
    
    style C fill:#ff6b6b
    style H fill:#f9ca24
```

### Safety Checks

1. **Blacklist Patterns**: Blocks `rm -rf /`, `dd if=/dev/zero`, etc.
2. **Sudo Detection**: Auto-adds `sudo` for system operations
3. **User Confirmation**: Required for all potentially dangerous operations
4. **Dry-Run Mode**: Test commands without execution

## Performance Characteristics

| Operation | Latency | Model Used | Notes |
|-----------|---------|------------|-------|
| Intent Classification | 10-100ms | Groq: Kimi K2 | Ultra-fast routing |
| Simple Chat | 500ms-2s | OpenRouter: GPT | Depends on model |
| Command Generation | 1-3s | Primary LLM | Includes RAG lookup |
| Task Planning | 2-5s | Primary LLM | Complex reasoning |
| Browser Automation | 10-60s | Gemini Flash | Depends on task |
| Video Generation | 30-120s | Gemini 2.5 Flash | Code gen + render |

## Technology Stack

### Core Technologies
- **Language**: Python 3.10+
- **CLI Framework**: Typer
- **UI Library**: Rich + Prompt Toolkit
- **Async**: asyncio

### AI/ML
- **LLM Clients**: google-genai, openai, groq
- **Browser Automation**: browser-use, playwright
- **Memory**: supermemory (RAG)
- **Video**: Remotion (React/TypeScript)

### System Integration
- **Package Detection**: distro
- **Config Management**: JSON + environment variables
- **Security**: Custom validation layer

## Future Architecture Enhancements

### Planned Improvements

1. **MCP Integration**: Model Context Protocol for extended tooling
2. **Plugin System**: Modular skill extensions
3. **Distributed Execution**: Remote command execution
4. **Advanced Memory**: Hierarchical memory with forgetting curves
5. **Multi-Agent Collaboration**: Specialized sub-agents for domains

---

**Architecture Philosophy**: Nexus combines the speed of heuristics, the intelligence of multiple AI models, and the reliability of hardcoded logic to create a robust, intelligent assistant that learns and improves over time.
