# Jarvis Assistant Future Roadmap

This document outlines the planned features and expansion capabilities for the Jarvis Linux Assistant. Use this as a living document to track ideas and architectural decisions.

## 1. Agentic Capabilities & MCP Integration
Connect Jarvis to the Model Context Protocol (MCP) to expand its toolset beyond the local machine.

- **MCP Client Architecture**: Implement a client within Jarvis to connect to local or remote MCP servers.
- **Browser Use (Local)**:
    - Use the open-source `browser-use` library (not the SDK).
    - **Live View**: Run with `headless=False` so the user can watch the browser.
    - **Search**: "Find MrBeast on YouTube" opens a real Chrome window and clicks the links.
- **Firecrawl MCP**: Use Firecrawl for converting websites into LLM-ready markdown, useful for "Reading documentation pages" commands.
- **Filesystem MCP**: Expose specific sandboxed directories to the agent for safer file operations.

## 2. Advanced Package & Application Management
Expand beyond system repositories (`apt`, `dnf`) to handle standalone Linux formats.

- **.deb File Handler**:
    - **Command**: `jarvis install ./package.deb`
    - **Logic**: Automate `sudo dpkg -i package.deb` and handle dependency errors with `sudo apt-get install -f`.
- **AppImage Integration**:
    - **Command**: `jarvis run ./app.AppImage` or `jarvis install-appimage ./app.AppImage`
    - **Logic**: 
        - Automatically apply executable permissions (`chmod +x`).
        - (Optional) Move to a centralized `~/Applications` folder.
        - **Shell Integration**: Safely edit `.bashrc` / `.zshrc` to add the `~/Applications` folder to `$PATH` or create a specific alias.
        - Create `.desktop` entries for system menu integration.
        - Run with optional sandboxing (Firejail) integration.
- **Flatpak & Snap Support**: specialized wrappers for `flatpak` and `snap` commands.
- **Universal Application Updater**:
    - **Command**: `jarvis update-app <app_name>`
    - **Goal**: Update any standalone application (AppImage, binary, .deb) not managed by the system package manager.
    - **Strategies**:
        - **GitHub Releases**: Automatically find and download the latest asset from a GitHub repository.
        - **URL Monitoring**: Check a download URL for file size/hash changes or version numbers.
        - **In-App Updaters**: Trigger built-in update mechanisms if available.
    - *Example Usage*: `jarvis update-app obsidian`, `jarvis update-app cursor`, `jarvis update-app my-tool`.

## 3. Enhanced File System Operations
Build robust tools for file management that go beyond basic shell commands.

- **Smart Search**: Find files by content or "vague description" using vector search or simple `grep`/`find` combinations. 
    - *Example*: "Find that python script I wrote last week about backups."
- **Bulk Operations**: Intelligent bulk renaming or organizing.
    - *Example*: "Rename all screenshots in this folder to include the date."
- **Safe Delete**: Implement a "Trash" mechanism instead of `rm` to allow recovery.

## 4. System Intelligence & Monitoring
Turn Jarvis into a proactive system admin.

- **Resource Monitoring**:
    - "Why is my laptop slow?" -> Check CPU/RAM usage, identify resource-hogging processes.
    - **Action**: "Kill the process consuming the most memory."
- **Log Analysis**:
    - "Check system logs for errors from the last hour." -> Parse `/var/log/syslog` or `journalctl` and summarize errors.
- **Network Tools**:
    - Quick speed test.
    - Port scanning (local `nmap` wrapper) to see what's running on localhost.
    - "What is running on port 8000?"

## 5. Developer Workflow Tools
Features specifically for software development.

- **Git Assistant**:
    - "Generate a commit message for these changes."
    - "Explain the difference between this branch and main."
- **Docker Management**:
    - "List running containers."
    - "Show logs for the redis container."
    - "Prune unused images."
- **Project Scaffolding**:
    - "Create a new Python project with venv and a basic Flask app."

## 6. Automation & Scripting
- **Natural Language Cron**:
    - "Run this backup script every day at 3 AM." -> Generates and installs the cron job.
## 7. Comparison: Jarvis vs. General AI Agents (Claude Code, Open Interpreter)

| Feature | General AI Agents (Claude/Open Interpreter) | Jarvis Assistant |
| :--- | :--- | :--- |
| **Primary Interface** | Chat / REPL | Integrated CLI Commands (`jarvis install`, `jarvis update`) |
| **State Persistence** | Ephemeral (forgets context after session) | Persistent (remembers config, installed apps, cron jobs) |
| **Workflow Logic** | Re-generated every time (prone to hallucinations) | Hardcoded, reliable logic for critical tasks (installers, updaters) |
| **Safety** | High risk (can hallucinate destructive commands) | Guardrails & specific permission scopes |
| **Speed** | Slow (needs to "think" for every action) | Instant (for built-in commands like `install` or `info`) |

**Core Philosophy**: Use AI to *generate* the command, but use code to *execute* and *manage* it reliably.

## 8. Memory & Context
Store user preferences and history to make Jarvis smarter over time.

- **Short-Term Memory**:
    - **Session Context**: Remember the last few commands in the current session (e.g., "undo that").
    - **Implementation**: Simple in-memory list or local JSON file.
- **Long-Term Memory**:
    - **User Preferences**: Store CLI flags or preferred tools (e.g., "Always use `ls -la`").
    - **Task History**: Log successfully executed complex tasks for re-use.
    - **Knowledge Base**: simple vector store (like ChromaDB or FAISS) to remember specific user instructions ("My server IP is 10.0.0.5").

