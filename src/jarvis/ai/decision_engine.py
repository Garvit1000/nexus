from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple
import re
import time
import hashlib
from threading import Lock

@dataclass
class Intent:
    action: str  # COMMAND, CHAT, SEARCH, BROWSE, PLAN, SHOW_CACHED
    command: Optional[str] = None
    args: Optional[str] = None
    confidence: float = 0.0
    reasoning: str = ""
    cached_result: Optional[str] = None  # For SHOW_CACHED action

class DecisionEngine:
    """
    The 'Brain' of Nexus.
    Analyzes user input to decide the best course of action.
    Uses a mix of heuristic rules (fast) and LLM reasoning (smart).

    Speed features:
    - Fast heuristic regex path (always tried first, <1ms)
    - LRU intent cache: identical/normalised queries skip the LLM entirely
    - Cache entries expire after CACHE_TTL seconds so context stays fresh
    """

    CACHE_SIZE = 256   # max distinct entries
    CACHE_TTL  = 300   # seconds (5 min)

    def __init__(self, llm_client=None, router_client=None, session_manager=None):
        self.llm_client     = llm_client
        self.router_client  = router_client
        self.session_manager = session_manager
        # {cache_key: (Intent, timestamp)}
        self._cache: Dict[str, Tuple["Intent", float]] = {}
        self._cache_lock = Lock()
        self._cache_hits = 0
        self._cache_misses = 0

    def _cache_key(self, text: str) -> str:
        """Normalised cache key — case-insensitive, whitespace-collapsed."""
        normalised = " ".join(text.lower().split())
        return hashlib.md5(normalised.encode(), usedforsecurity=False).hexdigest()

    def _get_cached(self, key: str) -> Optional["Intent"]:
        with self._cache_lock:
            entry = self._cache.get(key)
            if entry and (time.monotonic() - entry[1]) < self.CACHE_TTL:
                self._cache_hits += 1
                return entry[0]
            if entry:                       # expired
                del self._cache[key]
        return None

    def _set_cached(self, key: str, intent: "Intent") -> None:
        with self._cache_lock:
            # Evict oldest entry when full
            if len(self._cache) >= self.CACHE_SIZE:
                oldest = min(self._cache, key=lambda k: self._cache[k][1])
                del self._cache[oldest]
            self._cache[key] = (intent, time.monotonic())
            self._cache_misses += 1

    def get_cache_stats(self) -> Dict[str, int]:
        with self._cache_lock:
            return {
                "hits": self._cache_hits,
                "misses": self._cache_misses,
                "size": len(self._cache),
            }

    def invalidate_cache(self) -> None:
        """Clear the intent cache (e.g. when session resets)."""
        with self._cache_lock:
            self._cache.clear()

    def analyze(self, user_input: str) -> "Intent":
        """
        Decide what to do with the user input.
        Fast path: regex heuristics + LRU cache.
        Slow path: LLM router (only on cache miss for ambiguous inputs).
        """
        text = user_input.strip().lower()

        # --- Context Check: Is user referencing previous action? ---
        # NOTE: session-context intents are NOT cached (they depend on live state)
        if self.session_manager:
            context = self.session_manager.get_context_for_decision(user_input)
            if context and context.get('last_result'):
                return Intent(
                    action="SHOW_CACHED",
                    confidence=0.98,
                    reasoning=f"User referencing previous {context['last_action']} from {int(context['age_seconds'])}s ago",
                    cached_result=context['last_result']
                )

        # --- Cache check (before touching any LLM) ---
        cache_key = self._cache_key(user_input)
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        # --- Fast Path: Heuristics ---

        # 1. System Update
        if text in ["update", "update system", "upgrade system", "update my pc", "upgrade packages", "update all"]:
            return Intent(
                action="COMMAND",
                command="/update",
                confidence=0.99,
                reasoning="Precise match for system update request."
            )
            
        # 2. Install Package
        # Matches: "install git", "add nginx", "please install docker"
        install_match = re.search(r"\b(install|add)\s+([a-zA-Z0-9\-_]+)$", text)
        if install_match:
            pkg = install_match.group(2)
            return Intent(
                action="COMMAND",
                command="/install",
                args=pkg,
                confidence=0.95,
                reasoning=f"User explicitly asked to install '{pkg}'."
            )

        # 3. Remove Package
        # Matches: "remove git", "uninstall docker", "delete nginx"
        remove_match = re.search(r"\b(remove|uninstall|delete)\s+([a-zA-Z0-9\-_]+)$", text)
        if remove_match:
            pkg = remove_match.group(2)
            return Intent(
                action="COMMAND",
                command="/remove",
                args=pkg,
                confidence=0.95,
                reasoning=f"User explicitly asked to remove '{pkg}'."
            )
            
        if text.startswith("search for") or text.startswith("google "):
            query = text.replace("search for", "").replace("google ", "").strip()
            return Intent(action="COMMAND", command="/search", args=query, confidence=0.9)

        # --- Memory Context: Retrieve relevant past actions ---
        memory_context = ""
        if self.llm_client and hasattr(self.llm_client, "memory_client") and self.llm_client.memory_client:
            try:
                # Query memory for relevant past actions (with temporal bias)
                recent_actions = self.llm_client.memory_client.query_memory(
                    f"recent task action {text[:100]}",
                    limit=2
                )
                if recent_actions:
                    memory_context = f"\n### RECENT MEMORY\n{recent_actions}\n"
            except Exception:
                pass  # Silent fail if memory unavailable
        
        # --- Session History Context ---
        session_context = ""
        if self.session_manager:
            recent_history = self.session_manager.get_recent_history(limit=3)
            if recent_history:
                history_lines = []
                for turn in recent_history:
                    history_lines.append(
                        f"- {turn['user_input'][:50]} → {turn['intent_action']} ({turn['success'] and 'success' or 'failed'})"
                    )
                session_context = f"\n### RECENT CONVERSATION\n" + "\n".join(history_lines) + "\n"

        # --- Slow Path: LLM Analysis (LLM Reasoning) ---
        # Prefer the fast Router Client (Groq) if available, otherwise fallback to main LLM.
        active_client = self.router_client if self.router_client else self.llm_client
        
        if active_client:
            # Build enhanced prompt with examples and context
            prompt = f"""
You are Nexus, an autonomous AI agent designed for Linux systems.
You are NOT a chatbot. You are a DOER.

### YOUR MENTAL MODEL
1. **Analyze First**: Understand the user's *true intent*.
2. **Action Over Talk**: If the user asks to "check", "get", "show me", "monitor", or "install" something, you MUST DO IT, not talk about it.
3. **NO CHAT SCRIPTS**: Never just *print* a script in CHAT.
   - If user asks "Write a script to X", use `PLAN` to CREATE the file (e.g. `write_to_file`).
   - actual *execution* is better than a script.

### ACTION PROTOCOLS
- **COMMAND**: Trivial, single-step tasks (e.g. "update system", "install git").
- **PLAN**: Complex tasks, web interactions, or multi-step verifications.
- **SEARCH**: Simple fact lookups (e.g. "who is CEO of Google?").
- **CHAT**: ONLY for greeting, philosophy, or when the user explicitly asks for an explanation/opinion.
{memory_context}{session_context}
### USER INPUT
"{text}"

### FEW-SHOT EXAMPLES (Learn from these patterns)
User: "Show me top 10 hacker news posts"
→ {{"action": "PLAN", "confidence": 0.95, "reasoning": "User wants live data from web, requires scraping"}}

User: "install docker"
→ {{"action": "COMMAND", "command": "/install docker", "confidence": 0.98, "reasoning": "Simple package installation"}}

User: "what is docker?"
→ {{"action": "CHAT", "confidence": 0.90, "reasoning": "Informational question, no action needed"}}

User: "check my disk space"
→ {{"action": "PLAN", "confidence": 0.85, "reasoning": "Requires checking system state and formatting output"}}

User: "who is the CEO of Google?"
→ {{"action": "SEARCH", "confidence": 0.95, "reasoning": "Simple fact lookup, use Google search"}}

User: "download the latest version of VSCode"
→ {{"action": "PLAN", "confidence": 0.92, "reasoning": "Multi-step: find download link, download, install"}}

User: "now check if it is running and close it if it is"
→ {{"action": "PLAN", "confidence": 0.95, "reasoning": "Follow-up sysadmin action requesting state check and service management"}}

### DECISION HEURISTICS
To make your decision, ask yourself:
1. "Is the user asking me to perform an action?" → Yes = PLAN or COMMAND.
2. "Does this require checking a website (e.g. 'show me HN', 'fetch posts')?" → Yes = PLAN.
3. "Is this a simple fact lookup?" → Yes = SEARCH.
4. "Is this just a chat/explanation?" → Yes = CHAT.

### CRITICAL RULES
- If the user says "Show me X", "Get X", "Display X", "Give me X", "Fetch X" → ALWAYS choose PLAN, NEVER CHAT.
- If the user asks for "posts", "data", "results", "list", "top 10", "latest" → PLAN (they want live data).
- NEVER return a script/code in CHAT unless explicitly asked "write a script" or "show me the code".
- When in doubt: Choose PLAN over CHAT (it's better to attempt action than just talk).
- If user says "now X" or references "it/them/that" → They likely want follow-up action on previous task.

OUTPUT FORMAT (JSON ONLY):
{{
  "action": "PLAN" | "COMMAND" | "CHAT" | "SEARCH",
  "command": "/command args" (only if action is COMMAND),
  "confidence": <float 0.0-1.0>,
  "reasoning": "<brief explanation>"
}}
"""
            try:
                # We use a lower temperature if possible, but our client interface is simple.
                response_text = active_client.generate_response(prompt).strip()
                
                # Default fallback - prefer PLAN over CHAT
                intent_data = {"action": "PLAN", "confidence": 0.5, "reasoning": "Failed to parse Brain response, attempting to form action plan."}

                # Try to parse JSON. Kimi/GPT might wrap in markdown blocks.
                import json
                clean_response = response_text.replace("```json", "").replace("```", "").strip()
                try:
                    intent_data = json.loads(clean_response)
                except json.JSONDecodeError:
                    # Fallback helper if JSON fails but text looks like a command
                    if response_text.startswith("/"):
                         parts = response_text.split(" ", 1)
                         intent_data = {
                             "action": "COMMAND",
                             "command": response_text,
                             "confidence": 0.7,
                             "reasoning": "Raw command parsed from non-JSON output."
                         }

                action = str(intent_data.get("action", "PLAN")).upper()
                confidence = float(intent_data.get("confidence", 0.5))
                reasoning = str(intent_data.get("reasoning", ""))
                
                command_str = str(intent_data.get("command", "")) if intent_data.get("command") else ""
                cmd = None
                args = None
                
                if action == "COMMAND" and command_str:
                     parts = command_str.split(" ", 1)
                     cmd = parts[0]
                     args = parts[1] if len(parts) > 1 else ""

                result = Intent(
                    action=action,
                    command=cmd,
                    args=args,
                    confidence=confidence,
                    reasoning=reasoning
                )
                # Cache the LLM result so next identical query is instant
                self._set_cached(cache_key, result)
                return result

            except Exception:
                pass


        
        # Default: PLAN (not CHAT) - Better to attempt action than just talk
        return Intent(
            action="PLAN",
            confidence=0.5,
            reasoning="No clear intent detected. Defaulting to PLAN to attempt forming an action plan."
        )
