# API Key Rotation Setup Guide

## Overview

The API Key Rotator allows Nexus to automatically switch between multiple Google API keys when one hits rate limits or quota exhaustion.

---

## Setup Instructions

### Step 1: Add Multiple API Keys to `.env`

Edit your `.env` file:

```bash
# Primary Google API key
GOOGLE_API_KEY=AIzaSy...your-primary-key...

# Additional backup keys (add as many as you want)
GOOGLE_API_KEY_2=AIzaSy...your-backup-key-1...
GOOGLE_API_KEY_3=AIzaSy...your-backup-key-2...
GOOGLE_API_KEY_4=AIzaSy...your-backup-key-3...
# ... add more as needed
```

### Step 2: Restart Nexus

```bash
# Stop current instance
Ctrl+C

# Start again
python3 -m src.jarvis.main
```

---

## How It Works

### Automatic Rotation

1. **Starts with primary key** (`GOOGLE_API_KEY`)
2. **On failure**, automatically switches to next key (`GOOGLE_API_KEY_2`)
3. **Continues** through all keys until one succeeds
4. **Tracks failures** - marks keys as "exhausted" after 3 failures
5. **Cooldown period** - Retries exhausted keys after 60 minutes

### Example Flow

```
Request: "Show me MrBeast video"

Attempt 1: primary key → Rate limit error (429)
  ↓ Auto-rotate
Attempt 2: backup-1 key → Success! ✅
  ↓ Task completes

Next request uses backup-1 (last successful key)
```

---

## Features

### Smart Failure Detection

Automatically detects quota/rate limit errors:
- `429 Too Many Requests`
- `Resource Exhausted`
- `Quota Exceeded`
- `404 NOT_FOUND` (model not available)

### Health Monitoring

Check status at any time:
```python
health = browser_manager.key_rotator.get_health_status()
# Returns:
{
  "total_keys": 4,
  "active_keys": 3,
  "exhausted_keys": 1,
  "current_key": "backup-1",
  "keys": [...]
}
```

---

## Configuration

### Cooldown Period

Change how long before retrying exhausted keys:

**File:** [`api_key_rotator.py`](src/jarvis/core/api_key_rotator.py)

```python
# Default: 60 minutes
APIKeyRotator(keys, names, cooldown_minutes=60)

# Change to 30 minutes:
APIKeyRotator(keys, names, cooldown_minutes=30)
```

### Max Retries

Change how many keys to try per request:

**File:** [`browser_manager.py`](src/jarvis/modules/browser_manager.py)

```python
# Default: 4 attempts
def run_task(self, ..., max_retries: int = 4)

# Change to try all available keys:
def run_task(self, ..., max_retries: int = 10)
```

---

## Benefits

### 1. Increased Quota
- 4 keys = 4x quota (e.g., 60 requests/min × 4 = 240 requests/min)

### 2. High Availability
- If one key fails, others automatically take over
- No manual intervention needed

### 3. Smart Recovery
- Exhausted keys auto-reset after cooldown
- Continuous operation even during heavy usage

---

## Monitoring

### Console Logs

You'll see rotation in action:

```
🔑 Using API key: primary (attempt 1/4)
❌ Key primary failed: 429 rate limit
🔑 Using API key: backup-1 (attempt 2/4)
✅ Key backup-1 succeeded
```

### Status Check

```python
# In Python console:
from src.jarvis.main import browser_manager

if browser_manager and browser_manager.key_rotator:
    health = browser_manager.key_rotator.get_health_status()
    print(f"Active keys: {health['active_keys']}/{health['total_keys']}")
    print(f"Current: {health['current_key']}")
```

---

## Troubleshooting

### "No Google API keys found in environment"

**Solution:** Make sure `.env` has `GOOGLE_API_KEY` set

### "All API keys exhausted"

**Solutions:**
1. Wait 60 minutes for cooldown
2. Add more keys to `.env`
3. Increase cooldown period

### Key not rotating

**Check:**
1. Did you restart Nexus?
2. Is error actually a quota error? (Check console logs)
3. Are multiple keys configured in `.env`?

---

## Example `.env` File

```bash
# Core API Keys
GROQ_API_KEY=gsk_...
GROQ_GPT_API_KEY=gsk_...
OPENROUTER_API_KEY=sk-or-...

# Google API Keys (for Browser Tasks)
GOOGLE_API_KEY=AIzaSy...primary...
GOOGLE_API_KEY_2=AIzaSy...backup-1...
GOOGLE_API_KEY_3=AIzaSy...backup-2...
GOOGLE_API_KEY_4=AIzaSy...backup-3...

# Memory
SUPERMEMORY_API_KEY=sm_...

# Optional
BROWSER_USE_API_KEY=bu_...
```

---

## Summary

✅ **Automatic rotation** - No manual switching  
✅ **4+ keys supported** - Scale as needed  
✅ **Smart failure detection** - Only rotates on quota errors  
✅ **Auto-recovery** - Cooldown and retry  
✅ **Zero config** - Just add keys to `.env`  

**Result:** Uninterrupted browser automation even under heavy load! 🚀
