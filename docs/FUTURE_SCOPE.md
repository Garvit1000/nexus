# Nexus — Future Scope

> This file tracks what's been shipped and what's still to build, ordered by priority.

---

## 🔴 High Priority — Next Sprint

*(Shipped work lives only under **Recently Shipped** below — nothing listed here is done yet.)*

### 1. Rollback Checkpoints
**Current state:** Zero rollback capability. A half-executed plan that fails mid-way can leave the system in a broken state.
**What to build:**
- `RollbackManager` class in `src/jarvis/core/rollback_manager.py`
- Before any `FILE_WRITE` step: `cp -a {file} ~/.nexus/rollback/{timestamp}/`
- Before any `SERVICE_MGT` step: record current `systemctl status` output
- Before destructive `TERMINAL` commands: snapshot installed package list
- Add `/undo` command in TUI that runs the most recent rollback manifest
- Store rollback manifests in `~/.nexus/rollback/` (last 5 plans)

### 2. Dynamic Slash Command Registry
**Current state:** Hardcoded `if/elif` handlers in `console_app.py`. Adding a new command requires editing the chain.
**What to build:**
- Dynamic command registry with decorator-based registration.
- Autocomplete support via `prompt_toolkit` completions.
- Plugin-style command loading so new commands don't touch core TUI code.

### 3. FILE_APPEND / FILE_PATCH Action
**Current state:** Nexus only has `FILE_WRITE` which overwrites the entire file. To append to a file (e.g., add a line to `.bashrc`, append config to `nginx.conf`), the LLM must use a `TERMINAL` action with `echo "..." >> file`, which is fragile and prone to shell injection.
**What to build:**
- New `FILE_APPEND` action type that opens the file in append mode (`"a"`) with the same path traversal protection as `FILE_READ`.
- Optional `FILE_PATCH` variant that inserts content at a specific line or after a pattern match.
- Safer than piping through shell — content is written directly via Python `open()`, no injection possible.

### 4. FTP Security Protection
FTP-related commands need safety checks (anonymous login, plaintext credential exposure) in `security.py`.

### 5. LLM Rate Limiting & Budget Tracking
**Current state:** No throttling — a user in rapid-fire mode can burn through API credits in minutes.
**What to build:**
- Per-minute rate limiter in `LLMClient.generate_response()`.
- Optional token budget tracker with configurable daily limits.

---

## 🟡 Medium Priority

### 1. Context Window Management for Long Plans
**Current state:** Plans with 6+ steps start hallucinating because accumulated step output fills the LLM context.
**What to build:**
- After each step, store only a summary (first 100 chars + RC) instead of full stdout.
- Truncate the Planner's context window to the last 3 step outputs when generating fix prompts.
- Cap raw output stored in `step.output` at 500 chars; full output redirected to `~/.nexus/logs/{plan_id}.log`.

### 2. Parallel Execution for Independent Steps
**Current state:** All plan steps are strictly sequential even when they have no dependencies.
**What to build:**
- Add optional `"parallel": true` and `"depends_on": [step_id]` fields to `TaskStep`.
- Planner prompt rule: *"Steps with no data dependency on previous steps MAY be marked parallel: true"*.
- Orchestrator runs parallel-flagged steps with `asyncio.gather()`.

### 3. Session File Security
**Current state:** `~/.nexus/session.json` stores conversation history (which may include sensitive command outputs) but has no file permissions set.
**What to build:**
- `os.chmod(session_file, 0o600)` after every write in `PersistentSessionManager`.

---

## 🔵 Strategic (Long-term)

### 1. Git Assistant
- Natural language git: squash commits, branch, diff since date, rebase.
- `GIT` action type with pre/post diff summary as Markdown.

### 2. Docker Management Mode
- `DOCKER_MGT` action: `ps`, `logs`, `restart`, `stats`, `prune`.
- Ergonomic chat: *"tail logs for nginx"*, *"stop all exited containers"*.

### 3. Cron Job Manager
- Named cron jobs stored in `~/.nexus/crontab.json`.
- Natural language → cron expression (LLM-validated).
- `/crons` TUI command to list/delete.

### 4. MCP Integration
- Expose `nexus.execute`, `nexus.plan`, `nexus.read_file` as MCP tool endpoints.
- Let Cursor/Claude Desktop/Windsurf delegate shell tasks to Nexus.

### 5. Natural Language Code Review
- `git diff` or `git show HEAD` → LLM security/bug/style review.
- *"audit my last commit for injection risks"*.

### 6. Interactive Desktop Avatar
- A small Electron-based or WebView companion that renders `nexusbot.svg`.
- Reacts to agent state (Thinking, Success, Failure) via WebSockets.
- Face animations synced with LLM output.

---

## ✅ Recently Shipped

### Closed — were High Priority (tracking only)

These used to sit in *High Priority*; they are **done** and described in detail in the dated sections below.

| Old backlog label | Where it shipped |
|-------------------|------------------|
| Small-task direct execution | **DIRECT_EXECUTE** intent — *System Operations Overhaul* |
| APP_INSTALL / local packages | Planner **`SYSTEM OPERATIONS REFERENCE`** + self-healer (`.deb`, AppImage, `.rpm`, archives, Snap, Flatpak) — *System Operations Overhaul*; no separate `APP_INSTALL` action |

### Reliability & safety pass (March 2026)
- **`rm -rf /` heuristics**: Root-delete detection no longer false-positives on `/tmp/...`, `/var/tmp/...`, or a **newline** between `/` and the rest of the path (wrapped shell lines). Stricter lookahead uses horizontal whitespace only where needed.
- **Command generator retries**: Same-provider backoff on 429/timeouts/5xx, then fallback clients; empty LLM output retries instead of raising immediately.
- **Orchestrator bugfix**: Removed inner `import os` inside `execute_plan` that shadowed the module and caused `UnboundLocalError` on `FILE_WRITE` self-heal when no `BROWSER` step had run.
- **Test suite**: **176** `pytest` tests (security regressions for `rm` heuristics, command-generator fallback/retry cases).

### System Operations Overhaul (March 2026)
- **DIRECT_EXECUTE Intent**: New `DIRECT_EXECUTE` action in the Decision Engine for simple, single-command operations (chmod, mkdir, cp, mv, tar, ls, df, free, etc.). Bypasses the full PLAN pipeline — no plan table, no confirmation, just generates and runs the command immediately. Heuristic regex patterns + LLM router awareness.
- **Planner System Operations Knowledge**: Planner prompt now includes a `SYSTEM OPERATIONS REFERENCE` section with correct procedures for AppImage (chmod + extract + desktop entry), .deb (dpkg -i), .rpm, .tar.gz, .zip, Snap, Flatpak, XDG standards, and desktop entries.
- **Isolated Shell Clarity**: Planner RULES section now includes explicit RIGHT/WRONG examples about shell isolation (cd has no effect between steps, always use absolute paths, chain with &&).
- **TaskStep cwd Field**: New optional `cwd` field on `TaskStep` allows TERMINAL steps to specify a working directory. Passed through to `executor.run()` and `executor.run_interactive()`.
- **Self-Healer Filesystem Fixes**: `reflect_and_fix()` now catches common filesystem errors without LLM calls: "Unable to locate package" on .deb/.AppImage/.rpm files (rewrites to dpkg/chmod/rpm), "No such file or directory" (creates parent dir), "Permission denied" (prepends sudo), "Is a directory" on cp (adds -r flag).
- **Planner Examples Expanded**: New examples for AppImage setup (with desktop entry extraction), .deb installation, and archive extraction.

### Audit Round (March 2026)
- **FILE_SEARCH Intelligent Filtering**: Smart noise filter excludes `site-packages`, `.venv`, `node_modules`, `__pycache__` from results. Prefers `fd`/`rg` over `find`/`grep`. Two-tier search with meaningful-result threshold.
- **TUI Slash Commands Fixed**: `/find`, `/read`, `/do` registered as first-class TUI commands. `/search` gracefully handles non-Google providers.
- **Azure Log Noise Eliminated**: Output marker (`===NEXUS_OUTPUT_START===`) separates bootstrap noise from command results. Only meaningful output shown to user.
- **Test Suite Expanded**: 176+ automated tests across 10+ test files covering executor, planner, security, decision engine, audit logger, config manager, session manager, command generator, LLM client, package manager, and orchestrator.
- **Security Hardened**: Shell injection fixed in FILE_SEARCH, `find` command, and AZURE_RUN. LLM-generated commands validated through SafetyCheck. Path traversal protection on `read`. Package name injection prevented. Config file permissions set to 0o600. Browser `disable_security` set to False.
- **Crash Bugs Fixed**: `ImportError` on `nexus read`, `AttributeError` on session save, `NameError` in PLAN fallback, `asyncio` nested loop in browser manager.
- **CI/CD Improved**: Dependency sync between `pyproject.toml` and `requirements.txt`. CI matrix for `[all]` extras. Ruff linting + `pip-audit` security scanning added.
- **API Key Wiring**: `APIKeyRotator` connected to LLM clients. Dummy `api_key="dummy"` replaced with real keys. Graceful browser error messages with setup instructions.

### Earlier Releases
- **Global Search Fallback**: High-performance global filesystem search using `locate` or `find /` when local matches are missing.
- **Ambiguity Handling (CLARIFY)**: Decision Engine detects low-confidence contexts (<0.7) and returns explicit multi-choice clarification options.
- **Interactive Program Handoff**: `run_interactive` cleanly suspends Rich live dashboard for TUI programs (Vim, Nano).
- **Terminal UX Update**: Migration to `prompt_toolkit` with history tracking and streaming.
- **Persistent Sessions**: Context-aware responses that survive restarts; last 24h of history restored on launch.
- **Audit Logging**: Tamper-evident `~/.nexus/audit.log` with `chmod 600`.
- **Self-Healing Execution**: Dual-stage (local heuristic + LLM) auto-fix with 3-attempt retry.
- **Exponential Backoff**: `2^n + jitter` delay between LLM fallback attempts.

---

*Updated: March 2026*
