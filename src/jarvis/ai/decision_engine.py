from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple, List
import re
import time
import hashlib
from threading import Lock


@dataclass
class Intent:
    action: str  # COMMAND, CHAT, SEARCH, BROWSE, PLAN, SHOW_CACHED, CLARIFY
    command: Optional[str] = None
    args: Optional[str] = None
    confidence: float = 0.0
    reasoning: str = ""
    cached_result: Optional[str] = None  # For SHOW_CACHED action
    clarification_options: Optional[List[str]] = None  # For CLARIFY action
    plan_steps: Optional[List[Any]] = None  # For PLAN action


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

    CACHE_SIZE = 256  # max distinct entries
    CACHE_TTL = 300  # seconds (5 min)

    def __init__(self, llm_client=None, router_client=None, session_manager=None):
        self.llm_client = llm_client
        self.router_client = router_client
        self.session_manager = session_manager
        self.last_action_result = None
        self.last_action_type = "CHAT"  # default
        # /think toggle — show the thinking block by default
        self._show_thinking: bool = True
        # Intent routing cache: {cache_key: (Intent, timestamp)}
        self._cache: Dict[str, Tuple["Intent", float]] = {}
        self._cache_lock = Lock()
        self._cache_hits = 0
        self._cache_misses = 0
        # Response content cache: {cache_key: (response_text, timestamp)}
        # Stores the actual LLM-generated response so repeats show SHOW_CACHED
        self._response_cache: Dict[str, Tuple[str, float]] = {}
        # Runtime heuristics injected from main entry
        self._external_heuristics = []

    def add_heuristic(self, heuristic_fn):
        """Register a custom heuristic function at runtime."""
        self._external_heuristics.append(heuristic_fn)

    def _cache_key(self, text: str) -> str:
        """Normalised cache key — collapses whitespace and removes politeness markers."""
        # Strip politeness and common prefixes to increase cache hit rate
        t = text.lower().strip()
        t = re.sub(r"^(nexus|jarvis|please|can\s+you|hey|okay|now)\b", "", t).strip()
        normalised = " ".join(t.split())
        return hashlib.md5(normalised.encode(), usedforsecurity=False).hexdigest()

    def _get_cached(self, key: str) -> Optional["Intent"]:
        """Return a SHOW_CACHED intent if the exact query was answered before."""
        with self._cache_lock:
            # Check response cache first — if we have the actual answer, show it
            resp_entry = self._response_cache.get(key)
            if resp_entry and (time.monotonic() - resp_entry[1]) < self.CACHE_TTL:
                self._cache_hits += 1
                return Intent(
                    action="SHOW_CACHED",
                    confidence=1.0,
                    reasoning="Exact query seen before — showing cached response.",
                    cached_result=resp_entry[0],
                )
            if resp_entry:  # expired
                self._response_cache.pop(key, None)

            # Fallback: routing-only cache (no response text stored yet)
            entry = self._cache.get(key)
            if entry and (time.monotonic() - entry[1]) < self.CACHE_TTL:
                # We have a routing decision cached but no response text.
                # Return the original action so it executes normally.
                return entry[0]
            if entry:  # expired
                self._cache.pop(key, None)
        return None

    def _set_cached(self, key: str, intent: "Intent") -> None:
        """Cache the routing intent (CHAT/PLAN/etc.) for this key."""
        with self._cache_lock:
            if len(self._cache) >= self.CACHE_SIZE:
                oldest = min(self._cache, key=lambda k: self._cache[k][1])
                self._cache.pop(oldest, None)
            self._cache[key] = (intent, time.monotonic())
            self._cache_misses += 1

    def store_response(self, user_input: str, response_text: str) -> None:
        """
        Store the actual LLM response for a query so subsequent identical
        queries return SHOW_CACHED instead of re-calling the LLM.

        Call this from the UI layer after a successful CHAT or SEARCH response.
        Do not use for PLAN/COMMAND outputs.
        """
        if not response_text or not response_text.strip():
            return
        key = self._cache_key(user_input)
        with self._cache_lock:
            if len(self._response_cache) >= self.CACHE_SIZE:
                oldest = min(
                    self._response_cache, key=lambda k: self._response_cache[k][1]
                )
                self._response_cache.pop(oldest, None)
            self._response_cache[key] = (response_text.strip(), time.monotonic())

    def get_cache_stats(self) -> Dict[str, int]:
        with self._cache_lock:
            return {
                "hits": self._cache_hits,
                "misses": self._cache_misses,
                "size": len(self._cache),
                "response_cache_size": len(self._response_cache),
            }

    def invalidate_cache(self) -> None:
        """Clear the intent cache (e.g. when session resets)."""
        with self._cache_lock:
            self._cache.clear()
            self._response_cache.clear()

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
            if context and context.get("last_result"):
                return Intent(
                    action="SHOW_CACHED",
                    confidence=0.98,
                    reasoning=f"User referencing previous {context['last_action']} from {int(context['age_seconds'])}s ago",
                    cached_result=context["last_result"],
                )

        # --- Cache check (before touching any LLM) ---
        cache_key = self._cache_key(user_input)
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        # --- Fast Path: External Runtime Heuristics ---
        for h_fn in self._external_heuristics:
            try:
                h_intent = h_fn(user_input)
                if h_intent:
                    return h_intent
            except Exception:
                pass

        # --- Fast Path: Heuristics ---

        # 1. System Update
        if text in [
            "update",
            "update system",
            "upgrade system",
            "update my pc",
            "upgrade packages",
            "update all",
        ]:
            return Intent(
                action="COMMAND",
                command="/update",
                confidence=0.99,
                reasoning="Precise match for system update request.",
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
                reasoning=f"User explicitly asked to install '{pkg}'.",
            )

        # 3. Remove Package
        # Matches: "remove git", "uninstall docker", "delete nginx"
        remove_match = re.search(
            r"\b(remove|uninstall|delete)\s+([a-zA-Z0-9\-_]+)$", text
        )
        if remove_match:
            pkg = remove_match.group(2)
            return Intent(
                action="COMMAND",
                command="/remove",
                args=pkg,
                confidence=0.95,
                reasoning=f"User explicitly asked to remove '{pkg}'.",
            )

        if text.startswith("search for") or text.startswith("google "):
            query = text.replace("search for", "").replace("google ", "").strip()
            return Intent(
                action="COMMAND", command="/search", args=query, confidence=0.9
            )

        # 4. File / Directory Search (local + global)
        file_search_patterns = [
            r"^find\s+(me\s+)?(the\s+)?(file|folder|directory|path)",
            r"^search\s+(for\s+)?(file|folder|directory)",
            r"^(where\s+is|locate)\s+",
            r"^find\s+.*\b(folder|directory|file|path)\b",
            r"\bfind\s+.*\b(in|inside|under)\b.*\b(directory|folder)\b",
        ]
        if any(re.search(pat, text) for pat in file_search_patterns):
            return Intent(
                action="PLAN",
                confidence=1.0,
                reasoning="Direct request to search filesystem — will use FILE_SEARCH.",
            )

        # 5. File Content Inspection / Summarization / Analysis
        file_read_patterns = [
            r"^(read|cat|show|display|open|view)\s+(file|the file|contents of|content of)\b",
            r"^cat\s+",
            r"\b(summarize|summarise|summary of|explain|analyze|analyse|describe)\s+(this\s+)?(file|document|config|log|script|code)\b",
            r"\b(summarize|summarise|summary of|explain|analyze|analyse|describe)\s+.+\.(txt|py|js|ts|json|yaml|yml|toml|md|cfg|conf|ini|log|csv|xml|html|sh|bash|zsh)\b",
            r"\b(what'?s?\s+in|what\s+does|contents?\s+of|tell\s+me\s+about)\s+.+\.(txt|py|js|ts|json|yaml|yml|toml|md|cfg|conf|ini|log|csv|xml|html|sh|bash|zsh)\b",
            r"\b(read|show|get)\s+.+\.(txt|py|js|ts|json|yaml|yml|toml|md|cfg|conf|ini|log|csv|xml|html|sh|bash|zsh)\s*(and|then)?\s*(summarize|explain|analyze|tell me)?\b",
            r"\b(what\s+is\s+in|what'?s?\s+inside)\s+\S+\.(txt|py|js|ts|json|yaml|yml|toml|md|cfg|conf|ini|log|csv|xml|html|sh|bash|zsh)\b",
            r"^(read|show)\s+(me\s+)?(/|~/)",
            r"\b(summarize|summarise|explain|analyze|analyse)\s+(/|~/)",
        ]
        if any(re.search(pat, text) for pat in file_read_patterns):
            return Intent(
                action="PLAN",
                confidence=1.0,
                reasoning="Direct request to read/analyze local file content.",
            )

        # 5b. FTP URL — route to planner so it uses lftp (not the broken basic ftp)
        ftp_match = re.search(r"(?i)\bftp://(?:([^:@\s]+):([^@\s]+)@)?([^\s/:]+)(?::(\d+))?(/\S*)?", text)
        if ftp_match:
            return Intent(
                action="PLAN",
                confidence=1.0,
                reasoning="FTP URL detected — route to planner for proper lftp-based connection.",
            )

        # 6. Direct Execute — simple single-command operations that skip the planner
        direct_execute_patterns = [
            # Filesystem operations with clear targets
            r"^(make|chmod)\s+.*(executable|writable|readable|\+[rwx])",
            r"^(create|make|mkdir)\s+(a\s+)?(directory|folder|dir)\s+",
            r"^(list|show|ls)\s+(files|directories|folders|contents)",
            r"^(show|display|print|get|check)\s+(disk|memory|cpu|uptime|hostname|ip\b|ram|swap|storage)",
            r"^(show|check|get|display)\s+(which|where|path|version|info)\b",
            r"^(extract|unzip|untar|decompress|unpack)\s+\S+",
            r"^(copy|cp)\s+\S+\s+\S+",
            r"^(move|mv|rename)\s+\S+\s+\S+",
            r"^(delete|rm|remove)\s+(file|folder|directory)\s+",
            r"^(create|touch)\s+(file|a file)\s+",
            r"^(show|get|check)\s+(file\s+)?size\s+",
            r"^(change|set)\s+(permissions?|owner|group)\s+",
            # System info one-liners
            r"^(disk\s+usage|disk\s+space|free\s+space|memory\s+usage)",
            r"^(what\s+is\s+my\s+ip|my\s+ip|current\s+directory|pwd|whoami|who am i)",
            r"^(show|get|check)\s+(system\s+)?(info|information|specs|details|status)$",
            r"^(kill|stop)\s+(process|pid)\s+",
            r"^(check|test|verify)\s+(if\s+)?(file|directory|folder|port)\s+.*\s+(exists|open|running|available)",
        ]
        if any(re.search(pat, text) for pat in direct_execute_patterns):
            return Intent(
                action="DIRECT_EXECUTE",
                confidence=0.92,
                reasoning="Simple single-command operation — direct execution without planning.",
            )

        # --- Memory Context: Retrieve relevant past actions ---
        memory_context = ""
        if (
            self.llm_client
            and hasattr(self.llm_client, "memory_client")
            and self.llm_client.memory_client
        ):
            try:
                # Query memory for relevant past actions (with temporal bias)
                query_text = str(text)
                if len(query_text) > 100:
                    query_text = query_text[:100]
                recent_actions = self.llm_client.memory_client.query_memory(
                    f"recent task action {query_text}", limit=2
                )
                if recent_actions:
                    memory_context = (
                        f"\n### RECENT MEMORY\n{str(recent_actions)[:500]}\n"
                    )
            except Exception:
                pass  # Silent fail if memory unavailable

        # --- Session History Context ---
        session_context = ""
        if self.session_manager:
            recent_history = self.session_manager.get_recent_history(limit=3)
            if recent_history:
                history_lines = []
                for turn in recent_history:
                    truncated_user = str(turn.get("user_input", ""))
                    # Explicit indexing to avoid slice lints
                    if len(truncated_user) > 50:
                        truncated_user = truncated_user[:50]
                    history_lines.append(
                        f"- {truncated_user} → {turn.get('intent_action', 'UNKNOWN')} ({turn.get('success') and 'success' or 'failed'})"
                    )
                session_context = (
                    "\n### RECENT CONVERSATION\n" + "\n".join(history_lines) + "\n"
                )

        # --- Slow Path: LLM Analysis (LLM Reasoning) ---
        # Prefer the fast Router Client (Groq) if available, otherwise fallback to main LLM.
        active_client = self.router_client if self.router_client else self.llm_client

        if active_client:
            # Build enhanced prompt with examples and context
            prompt = f"""Nexus intent router. Classify the user's request into one action.
{memory_context}{session_context}
ACTIONS:
- COMMAND: single-step internal TUI commands (/install /remove /update /search /settings). Use "command":"..."
- DIRECT_EXECUTE: simple filesystem/system operations that need ONE shell command (chmod, mkdir, cp, mv, tar, ls, df, free, etc.)
- PLAN: multi-step tasks, web data, complex file ops, app setup (AppImage/deb/rpm), anything requiring 2+ steps
- SEARCH: factual questions that need the live web — current events, news, sports results/scores, elections, stock/crypto prices, "who won", "latest", "today", "this year", recent dates, or any fact that changes over time. Static trivia ("capital of France") can be SEARCH or CHAT; prefer SEARCH when recency matters.
- CHAT: greeting, opinion, creative writing, conceptual explanations that do not require up-to-the-minute facts
- CLARIFY: if intent is very ambiguous (confidence<0.70), provide clarification_options

RULES:
- "install X" (package name) → COMMAND. "install /path/to/file.deb" → PLAN (needs dpkg).
- Simple single-command ops (chmod, mkdir, cp, mv, extract, system info) → DIRECT_EXECUTE
- "setup/configure AppImage/deb" → PLAN (multi-step with desktop entry, icons, etc.)
- "show me/get/fetch/find/check/download X" (files, apps, system) → PLAN. When in doubt → PLAN.
- Time-sensitive or "current state of the world" questions → SEARCH (not CHAT).

INPUT: "{text}"

EXAMPLES:
"install docker" → {{"action":"COMMAND","command":"/install docker","confidence":0.98,"reasoning":"package install"}}
"show me HN posts" → {{"action":"PLAN","confidence":0.95,"reasoning":"web data retrieval"}}
"what is docker?" → {{"action":"CHAT","confidence":0.90,"reasoning":"informational"}}
"who is CEO of Google?" → {{"action":"SEARCH","confidence":0.95,"reasoning":"fact lookup"}}
"who won the men's T20 World Cup 2026?" → {{"action":"SEARCH","confidence":0.98,"reasoning":"current sports result needs web"}}
"find my bashrc" → {{"action":"PLAN","confidence":0.95,"reasoning":"file search task"}}
"make file.sh executable" → {{"action":"DIRECT_EXECUTE","confidence":0.95,"reasoning":"single chmod command"}}
"show disk usage" → {{"action":"DIRECT_EXECUTE","confidence":0.95,"reasoning":"single df command"}}
"extract archive.tar.gz" → {{"action":"DIRECT_EXECUTE","confidence":0.90,"reasoning":"single tar command"}}
"setup this AppImage" → {{"action":"PLAN","confidence":0.95,"reasoning":"multi-step AppImage installation with desktop integration"}}
"install /home/user/app.deb" → {{"action":"PLAN","confidence":0.95,"reasoning":"local deb install needs dpkg + dependency fix"}}
"list files in /etc" → {{"action":"DIRECT_EXECUTE","confidence":0.95,"reasoning":"single ls command"}}
"check memory usage" → {{"action":"DIRECT_EXECUTE","confidence":0.95,"reasoning":"single free command"}}

JSON ONLY:
{{"action":"PLAN|COMMAND|DIRECT_EXECUTE|CHAT|SEARCH|CLARIFY","command":"only if COMMAND","confidence":0.0-1.0,"reasoning":"...","clarification_options":["only","if","CLARIFY"]}}
"""
            try:
                # We use a lower temperature if possible, but our client interface is simple.
                response_text = active_client.generate_response(prompt).strip()

                # Default fallback - prefer PLAN over CHAT
                intent_data = {
                    "action": "PLAN",
                    "confidence": 0.5,
                    "reasoning": "Failed to parse Brain response, attempting to form action plan.",
                }

                # Try to parse JSON. Kimi/GPT might wrap in markdown blocks.
                import json

                clean_response = (
                    response_text.replace("```json", "").replace("```", "").strip()
                )
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
                            "reasoning": "Raw command parsed from non-JSON output.",
                        }

                action = str(intent_data.get("action", "PLAN")).upper()
                confidence = float(intent_data.get("confidence", 0.5))
                reasoning = str(intent_data.get("reasoning", ""))
                clarification_options = intent_data.get("clarification_options", None)

                # Enforce CLARIFY for low confidence
                if confidence < 0.70 and action != "CLARIFY":
                    action = "CLARIFY"
                    clarification_options = [
                        "Could you provide more details?",
                        "Are you looking to view system state?",
                        "Something else?",
                    ]

                command_str = (
                    str(intent_data.get("command", ""))
                    if intent_data.get("command")
                    else ""
                )
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
                    reasoning=reasoning,
                    clarification_options=clarification_options,
                )
                # Cache the LLM result so next identical query is instant
                self._set_cached(cache_key, result)
                return result

            except Exception as e:
                # Return the actual error so the user and developer can see why routing hit a wall
                return Intent(
                    action="PLAN", confidence=0.5, reasoning=f"Groq API Error: {str(e)}"
                )

        # Default: PLAN (not CHAT) - Better to attempt action than just talk
        return Intent(
            action="PLAN",
            confidence=0.5,
            reasoning="Intelligent System Routing: Initializing multi-step execution plan.",
        )
