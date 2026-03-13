# ⚡ Nexus: The AI-Powered Linux Assistant ⚡

**Nexus** is an autonomous, terminal-based AI assistant. It doesn't just chat — it *does* things. By acting as a super-smart middleman between you and your Linux OS, it can manage your system, browse the web, write code, and even run dangerous commands safely in isolated cloud sandboxes — all via plain natural language.

---

## 1. The Multi-Brain System

Nexus is smart because it doesn't rely on a single AI model. It routes your request to the best "brain" for the job:

| Brain | Model | Role |
|---|---|---|
| **Router Brain** | Groq: Kimi K2 | Ultra-fast intent classifier — decides what kind of request this is in milliseconds |
| **Chat Brain** | OpenRouter / Groq | Handles conversations, explanations, and coding questions |
| **Planner Brain** | Primary LLM | The architect — breaks complex tasks into step-by-step plans |
| **Browser Agent** | Gemini Flash | Spins up a real web browser and navigates the internet using AI vision |
| **Search Tool** | Gemini 2.5 Flash | Searches Google and returns factual answers with citations |

---

## 2. How it Processes a Command (The Orchestrator Pipeline)

Whenever you ask Nexus to do something multi-step, it follows a strict 4-phase pipeline:

1. **Analyze** — Classifies your input into an intent (`COMMAND`, `PLAN`, `BROWSE`, `SEARCH`, `CHAT`).
2. **Plan** — The Planner Brain builds a step-by-step checklist of actions (e.g., `CHECK if nginx exists` → `TERMINAL install nginx` → `FILE_WRITE config` → `CHECK service status`). It always asks you for a `[y/N]` approval before touching anything.
3. **Execute (Safety First)** — Runs commands through an AST-based Defensive Security Module that validates shell syntax, blocks fork bombs (`:(){ :|:& };:`), and zeroizes memory when handling `sudo` passwords.
4. **Remember (Supermemory)** — Writes what worked into a vector database. Next time you ask for the same thing, Nexus recalls the exact successful steps — no re-querying the LLM needed.

---

## 3. Ephemeral Azure Sandboxing (`AZURE_RUN`)

Sometimes you need to run scripts, clone unknown repos, or compile code that might corrupt your local environment. This is where `AZURE_RUN` comes in.

### How it works:

When Nexus is about to execute a `TERMINAL` command that looks like it fetches or compiles external code (e.g., `git clone`, `wget`, `curl`, `bash -c`, `tar -x`), it **pauses and asks you**:

```
⚠️  Security Alert: This command fetches or compiles external code.
Command: git clone https://github.com/some-unknown-repo.git

Do you want to securely sandbox this in Azure instead of running it locally? (y/N):
```

- **Press Enter (No)** — The command runs normally on your local machine. Perfect for normal, trusted repos.
- **Type `y` (Yes)** — Nexus hot-swaps the action to `AZURE_RUN` and does the following:
  1. Spins up a disposable **Ubuntu 22.04** container in Microsoft Azure cloud.
  2. Automatically installs a full dev environment (`git`, `curl`, `wget`, `build-essential`, `python3`, `nodejs`, `cmake`, etc.).
  3. Runs your command inside this completely isolated sandbox.
  4. Streams the execution logs back to your terminal in real time.
  5. **Permanently destroys** the container when it finishes.

> Your personal laptop remains 100% safe, untouched, and unpolluted!

### Key design principle:
Nexus does **not** decide for you that something is "sketchy". It simply flags commands that _could_ fetch or execute external code, and gives you the choice. Normal `git clone` on a repo you trust? Just hit Enter — it runs locally as expected. Unknown script from the internet? Press `y` — it runs in the cloud disposable box and your machine never sees it.

---

## 4. Self-Healing Execution (Auto-Fix)

What happens if an installation fails because a tool is missing or a command is wrong?

Nexus has a **Dual-Stage Self-Healing System**:

- **Stage 1 (Pattern-Based):** If stderr says `command not found`, Nexus instantly knows to install it via your OS package manager (`apt`/`dnf`/`pacman`) without burning API tokens.
- **Stage 2 (LLM Reflection):** For deeper errors, Nexus wraps the `stderr` logs and sends them to the LLM, asking it to act as a "Senior DevOps Engineer" to rewrite the failing command. It auto-retries the fixed command up to **3 times** before safely halting.
- **Stage 3 (Azure Heal):** If an `AZURE_RUN` step fails, the same reflection loop runs inside the sandbox context — the healer can also re-provision and retry the container.

---

## 5. Continuous Chat Context

Nexus remembers your active session state so conversations flow naturally.

If you just ran `Install curl`, you can follow up with `"do the same for wget"` or `"now test it"` and Nexus will perfectly understand the context. The Orchestrator automatically fetches the last 3 turns of your conversation and includes them in every LLM call.

No more robotic restatement of facts!

---

## 6. Persistent Memory (Supermemory + RAG)

Beyond session context, Nexus stores long-term memories:

- Every successful plan is stored in a vector database alongside its embedding.
- When you make a similar request in a future session, the Planner retrieves the closest past plan via RAG (Retrieval-Augmented Generation) and uses it as a template — making future executions faster and more reliable.

---

## 7. Autonomous Web Browsing

Nexus can browse the internet like a human using `browser-use` and Gemini Flash vision:

- Navigate websites, fill forms, extract data, and click buttons.
- Used automatically when Nexus determines a task requires live web interaction that a simple search can't answer.
- Supports API key rotation for rate-limit resilience.

## 8. Azure Sandbox

🚀 1. Provisioning Lifecycle
Unique Identity: Nexus generates a random container ID (e.g., nexus-sandbox-a1b2c3d4) to ensure no overlaps.
Environment Isolation: It uses Azure Container Instances (ACI) to spin up a fresh Ubuntu 22.04 image. To ensure reliability, it pulls from Microsoft’s local mirror (mcr.microsoft.com) rather than public Docker Hub to avoid rate limits.
Hardware Allocation: The sandbox is allocated 1 CPU core and 1.5 GB of RAM, providing enough power for building or testing software without bloat.
📦 2. Pre-Installed Development Stack
Before your command even runs, Nexus executes a "Prime and Prep" script that installs a full development toolchain. This ensures that most developer tasks (cloning, building, installing dependencies) work out of the box.

The following tools are installed via apt-get:

Version Control: git (to clone and manage repos).
Network Tools: curl and wget (to download files/scripts).
C/C++ Build Tools: build-essential (which includes gcc, g++, and make) plus cmake.
Python Ecosystem: python3-pip and python3-venv (to run Python scripts or install requirements).
Web Ecosystem: nodejs and npm (for JS/TS projects).
🛠️ 3. Execution & Destruction
Live Injection: Once the environment is primed, your specific command is executed. Nexus streams the logs live to your terminal as if it were running locally.
Self-Healing: If the command fails inside the sandbox, the Auto-Healer triggers, reflects on the error, and tries up to 3 times to fix the command within that same isolated context.
Automatic Cleanup: Regardless of whether the task succeeded or failed, Nexus immediately sends a delete signal to Azure to destroy the container. Nothing persists, ensuring no malware or temporary files ever touch your host machine