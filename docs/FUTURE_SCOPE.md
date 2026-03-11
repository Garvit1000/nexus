# Nexus — Future Scope

> All P0 and P1 items (security hardening, audit log, self-healing, SERVICE_MGT, persistent session, exponential backoff) have been shipped.
> This file tracks everything still to build, ordered by priority.

---

## 🔴 High Priority — Next Sprint

### 1. Rollback Checkpoints
**Current state:** Zero. A half-executed plan that fails mid-way can leave the system in a broken state.

**What to build:**
- `RollbackManager` class in `src/jarvis/core/rollback_manager.py`
- Before any `FILE_WRITE` step: `cp -a {file} ~/.nexus/rollback/{timestamp}/`
- Before any `SERVICE_MGT` step: record current `systemctl status` output
- Before destructive `TERMINAL` commands: snapshot installed package list
- Add `/undo` command in TUI that runs the most recent rollback manifest
- Store rollback manifests in `~/.nexus/rollback/` (last 5 plans)

---

### 2. APP_INSTALL Action
**Current state:** Browser downloads `.deb`/`.AppImage` but the install step is ad-hoc TERMINAL, frequently fails.

**What to build:**
- New `APP_INSTALL` action type in `TaskStep`
- Orchestrator handler detects file extension and runs appropriate installer:
  - `.deb` → `dpkg -i {file}` (with sudo)
  - `.AppImage` → `chmod +x {file} && mv {file} ~/.local/bin/`  
  - `.rpm` → `rpm -i {file}` or `dnf install {file}`
- Planner prompt rule: *"If a BROWSER step downloads a binary, the NEXT step MUST be APP_INSTALL"*
- Post-install CHECK verifies the binary exists in PATH

---

## 🟡 Medium Priority

### 3. Context Window Management for Long Plans
**Current state:** Plans with 6+ steps start hallucinating because accumulated step output fills the LLM context.

**What to build:**
- After each step, instead of appending full stdout to the plan context, store only a **summary** (first 100 chars + RC)
- Truncate the Planner's context window to the last 3 step outputs when generating fix prompts
- Cap raw output stored in `step.output` at 500 chars; full output redirected to `~/.nexus/logs/{plan_id}.log`

---

### 4. Parallel Execution for Independent Steps
**Current state:** All plan steps are strictly sequential even when they have no dependencies.

**What to build:**
- Add optional `"parallel": true` and `"depends_on": [step_id]` fields to `TaskStep`
- Planner prompt rule: *"Steps with no data dependency on previous steps MAY be marked parallel: true"*
- Orchestrator runs parallel-flagged steps with `asyncio.gather()`

---

## ✅ Recently Shipped

- **Test Suite**: Shipped 61 automated tests covering `test_executor`, `test_planner`, `test_security`, and `test_decision_engine` via Pytest and CI workflows.
- **Ambiguity Handling (CLARIFY)**: Decision Engine now detects low-confidence contexts (<0.7) and returns explicit multi-choice clarification options to the user before guessing.
- **Interactive Program Handoff**: `run_interactive` cleanly suspends the Rich live dashboard for TUI programs (Vim, Nano) before restoring execution seamlessly.
- **Terminal UX Update**: Completed the migration to `prompt_toolkit`. Added history tracking and streaming capability for natural chat flow.

---

## 🔵 Strategic (Long-term)

### 9. Git Assistant
- Natural language git: squash commits, branch, diff since date, rebase
- `GIT` action type with pre/post diff summary as Markdown

### 10. Docker Management Mode
- `DOCKER_MGT` action: `ps`, `logs`, `restart`, `stats`, `prune`
- Ergonomic chat: *"tail logs for nginx"*, *"stop all exited containers"*

### 11. Cron Job Manager
- Named cron jobs stored in `~/.nexus/crontab.json`
- Natural language → cron expression (LLM-validated)
- `/crons` TUI command to list/delete

### 12. MCP Integration
- Expose `nexus.execute`, `nexus.plan`, `nexus.read_file` as MCP tool endpoints
- Let Cursor/Claude Desktop/Windsurf delegate shell tasks to Nexus

### 13. Natural Language Code Review
- `git diff` or `git show HEAD` → LLM security/bug/style review
- *"audit my last commit for injection risks"*

---

*Updated: March 2026*
