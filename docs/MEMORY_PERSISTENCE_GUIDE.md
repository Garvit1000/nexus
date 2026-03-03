# Memory Persistence Guide

## Overview

Nexus has **two types of memory**:

| Type | Persistence | Lifespan | Purpose | Storage |
|------|-------------|----------|---------|---------|
| **Session Context** | ❌ In-Memory (default)<br>✅ Disk (with PersistentSessionManager) | Current session<br>24 hours | Follow-up queries, cached results | RAM<br>~/.nexus/session.json |
| **Long-Term Memory** | ✅ Cloud Database | Forever | Learning, proven plans | Supermemory API |

---

## Default Behavior (After Restart)

### Session Context - ❌ LOST
```bash
# Session 1
User: "Show me HN posts"
Agent: [Executes]
User: "now show them"
Agent: ✅ Shows cached result

# App restart

# Session 2
User: "now show them"
Agent: ❌ "I don't have context about 'them'"
```

### Long-Term Memory - ✅ PRESERVED
```bash
# Session 1
User: "Show me HN posts"
Agent: [Saves to Supermemory: "fetch HN posts = success"]

# App restart

# Session 2
User: "Show me HN posts"
Agent: 🧠 "I recall doing this before"
Agent: ✅ Uses proven plan from memory
```

---

## Enable Session Persistence

To make session context survive restarts, use **PersistentSessionManager**:

### Step 1: Update console_app.py

```python
# In src/jarvis/ui/console_app.py

# OLD:
from ..core.session_manager import SessionManager
self.session_manager = SessionManager(max_history=50)

# NEW:
from ..core.persistent_session_manager import PersistentSessionManager
self.session_manager = PersistentSessionManager(max_history=50)
```

### Step 2: That's it!

The session will now:
- ✅ Save automatically after each turn
- ✅ Restore on app startup
- ✅ Keep last 24 hours of history
- ✅ Store in `~/.nexus/session.json`

---

## Comparison

### Without PersistentSessionManager (Default)

**Pros:**
- ✅ Faster (no disk I/O)
- ✅ No state pollution between sessions
- ✅ Clean start every time

**Cons:**
- ❌ Follow-up queries don't work after restart
- ❌ Cached results lost

### With PersistentSessionManager

**Pros:**
- ✅ Session survives restarts
- ✅ Follow-up queries work across sessions
- ✅ Cached results preserved (24h)

**Cons:**
- ⚠️ Slight overhead (disk writes)
- ⚠️ Old context might confuse agent (expires after 24h)

---

## Recommended Setup

**For Development:**
```python
# Use in-memory (default) for clean testing
SessionManager(max_history=50)
```

**For Production:**
```python
# Use persistent for better UX
PersistentSessionManager(max_history=50)
```

---

## File Locations

| Data Type | Location | Size | TTL |
|-----------|----------|------|-----|
| Session State | `~/.nexus/session.json` | ~10KB | 24 hours |
| Long-Term Memory | Supermemory Cloud | Unlimited | Forever |
| Config | `~/.nexus/config.json` | <1KB | Forever |

---

## Manual Session Management

### Clear old sessions
```bash
rm ~/.nexus/session.json
```

### View current session
```bash
cat ~/.nexus/session.json | jq
```

### Backup session
```bash
cp ~/.nexus/session.json ~/.nexus/session_backup_$(date +%Y%m%d).json
```

---

## Future Enhancements

- [ ] Session compression for large histories
- [ ] Multi-session management (switch between contexts)
- [ ] Cloud sync (session across devices)
- [ ] Automatic session summarization (convert old sessions to memory)

---

## Summary

**Current Implementation:**
- ✅ Supermemory: Persistent across restarts
- ❌ SessionManager: In-memory only (lost on restart)

**With PersistentSessionManager:**
- ✅ Supermemory: Persistent across restarts
- ✅ SessionManager: Persistent for 24 hours

**Trade-off:**
- In-memory: Faster, cleaner, but no follow-up after restart
- Persistent: Slightly slower, but better UX with context preservation
