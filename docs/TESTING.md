# Nexus — Test Suite

> **198 automated pytest tests** across 12 test files covering every critical code path.

## Running Tests

```bash
# Install dev dependencies (first time only)
pip install -e ".[dev]"

# Run all tests
pytest

# Run with verbose output
pytest -v

# Run a single test file
pytest tests/test_executor.py -v
```

## CI / Continuous Integration

Tests run automatically on every push via GitHub Actions (`.github/workflows/ci.yml`):
- Python **3.10**, **3.11**, **3.12** (matrix build)
- `[dev]` and `[all,dev]` extras tested in CI
- **Lint job**: `ruff check`, `ruff format --check`, `pip-audit --strict`
- Branches: `main`, `mvp`

---

## Test Coverage Map

### `tests/test_security.py` — 32 tests
**What it checks:** The `CommandValidator` and `SafetyCheck` layer that sits before every command execution.

| Test Group | Checks |
|---|---|
| `TestCommandValidatorBlocked` | `rm -rf /` and fork bombs are hard-blocked and return `is_valid=False` |
| `TestCommandValidatorWarnings` | `curl ... \| sh` is allowed but raises a warning; `ls` has zero warnings |
| `TestCommandValidatorSyntax` | Mismatched quotes and unbalanced parentheses are caught as syntax errors |
| `TestSafetyCheckIntegration` | `SafetyCheck.check_command()` raises `SecurityViolation` on blocked commands, returns `True` on safe ones |
| `TestSudoDetection` | `apt`, `systemctl`, writing to `/etc/` are correctly flagged as requiring sudo; `chmod` on user paths is not forced interactive |
| `TestRmRfHeuristics` | `rm -rf /tmp/...` and similar are **not** misread as `rm -rf /`; newline after `/` does not false-positive |
| `TestPathWithinRoots` | File read/write allowlists use proper path subtrees (e.g. `/home/user2` is not under `/home/user`) |
| `TestFtpSecurity` | FTP passwords in URLs, `wget --ftp-password`, `lftp -u user,pass`, and anonymous FTP are rejected in strict mode |

**Why it matters:** This is the last line of defence against AI-hallucinated destructive commands.

---

### `tests/test_audit_logger.py` — 8 tests
**What it checks:** The forensic audit log written to `~/.nexus/audit.log`.

| Test Group | Checks |
|---|---|
| `TestAuditLogCreation` | Log file is created on construction; file permissions are `0o600` (owner-only read/write) |
| `TestAuditLogEntries` | Successful commands log `STATUS=OK`; failures log `STATUS=FAIL(rc)`; unconfirmed logs `CONFIRMED=NO(auto)`; stdout excerpts are included; skipped commands log `STATUS=SKIPPED`; multiple entries append correctly |

**Why it matters:** The audit log is the only tamper-evident record of what Nexus ran on your machine.

---

### `tests/test_executor.py` — 18 tests
**What it checks:** The `CommandExecutor` — the central class that runs every shell command.

| Test Group | Checks |
|---|---|
| `TestExecutorSafeCommands` | `echo` returns RC=0 and correct stdout; `false` returns RC!=0; pipelines work |
| `TestExecutorBlockedCommands` | `rm -rf /` and fork bombs return RC=-1 without executing; blocked commands write SKIPPED to audit log |
| `TestExecutorDryRun` | Dry-run returns RC=0 without touching disk; `touch` doesn't create a file; audit log shows SKIPPED |
| `TestExecutorAuditIntegration` | Successful and failed executions both write entries to the audit log |
| `TestExecutorSudoPasswordClearing` | `bytearray` is zeroed on auth failure; password cache is never a plain `str` |
| `TestShellModeScoping` | Simple commands use `shell=False` + list args; commands with `\|` use `shell=True` + string |

**Why it matters:** The executor is the most security-critical component.

---

### `tests/test_planner.py` — 12 tests
**What it checks:** The `Planner` class that converts natural language into structured `TaskStep` lists.

| Test Group | Checks |
|---|---|
| `TestPlannerParsing` | Valid JSON produces correct `TaskStep` objects; multi-step plans parse all steps; IDs are sequential; malformed JSON returns `[]`; markdown code fences stripped |
| `TestPlannerFallback` | Fallback LLM tried when primary raises; all clients failing returns `[]`; backoff delay >= 2.0s between attempts |

---

### `tests/test_decision_engine.py` — 13 tests
**What it checks:** The `DecisionEngine` — Nexus's "brain" that classifies user input.

| Test Group | Checks |
|---|---|
| `TestHeuristicFastPath` | `"update"`, `"install git"`, `"remove nginx"` resolve without LLM call; case-insensitive |
| `TestSlowPathLLM` | Ambiguous inputs fall through to router LLM; returned action is used |
| `TestSessionContextAwareness` | Recent context returns `SHOW_CACHED` immediately; `None` context falls through normally |

---

### Other Test Files

| File | Tests | Coverage |
|---|---|---|
| `test_config_manager.py` | 13 | Config persistence, env var overrides, corrupted file recovery, file permissions |
| `test_model_catalog.py` | 6 | Onboarding/settings catalog, `apply_stored_task_models`, shared client behavior |
| `test_session_manager.py` | 29 | Turn tracking, history trimming, context detection, semantic filtering, summaries |
| `test_command_generator.py` | 16 | LLM cleanup, SafetyCheck validation, memory integration, fallback/retry |
| `test_llm_client.py` | 11 | Prompt enrichment, skip/double-enrichment guards, `MockLLMClient`, `search()` |
| `test_package_manager.py` | 22 | Package name validation (injection), install/remove/update for APT/DNF/Pacman |
| `test_orchestrator.py` | 24 | Missing binary extraction, self-healer, plan view, `execute_plan`, Azure `AZURE_RUN` |

---

*Updated: March 2026*
