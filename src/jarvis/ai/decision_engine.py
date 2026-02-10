from dataclasses import dataclass
from typing import Optional, Dict, Any
import re

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
    
    Enhanced with:
    - Session context awareness
    - Memory integration for better decisions
    - Few-shot learning examples
    """
    
    def __init__(self, llm_client=None, router_client=None, session_manager=None):
        self.llm_client = llm_client
        self.router_client = router_client
        self.session_manager = session_manager

    def analyze(self, user_input: str) -> Intent:
        """
        Decide what to do with the user input.
        
        Enhanced with session context and memory integration.
        """
        text = user_input.strip().lower()

        # --- Context Check: Is user referencing previous action? ---
        if self.session_manager:
            context = self.session_manager.get_context_for_decision(user_input)
            if context and context.get('last_result'):
                # User is asking about previous action
                return Intent(
                    action="SHOW_CACHED",
                    confidence=0.98,
                    reasoning=f"User referencing previous {context['last_action']} from {int(context['age_seconds'])}s ago",
                    cached_result=context['last_result']
                )

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

        # Transparency: Log model usage
        model_name = getattr(self.llm_client, "model_name", getattr(self.llm_client, "model", "Unknown Model"))
        print(f"[dim]🧠 Decision Engine Thinking with: {model_name}[/dim]")

        # --- Slow Path: LLM Analysis (LLM Reasoning) ---
        # Prefer the fast Router Client (Groq) if available, otherwise fallback to main LLM.
        active_client = self.router_client if self.router_client else self.llm_client
        
        if active_client:
            # Build enhanced prompt with examples and context
            prompt = f"""
You are Nexus, an autonomous AI agent designed for Linux systems.
You are NOT a chatbot. You are a DOER.

### YOUR MISSION
Understand the user's ACTUAL INTENT and choose the RIGHT ACTION to fulfill it.
Think deeply about what the user REALLY WANTS, not just the surface-level keywords.

### ACTION TYPES
- **PLAN**: Complex tasks, web data retrieval, multi-step operations, anything requiring browser or external data
- **COMMAND**: Simple system commands (install/remove/update packages)
- **SEARCH**: Quick fact lookups (who/what/when questions answerable by search)
- **CHAT**: ONLY greetings, philosophy, or explicit explanation requests

### INTELLIGENT ANALYSIS FRAMEWORK
For EVERY user request, ask yourself these questions IN ORDER:

1. **Data Source Check**:
   - Does this need LIVE/CURRENT data from the web? → PLAN
   - Examples: latest news, trending topics, current posts, real-time info
   
2. **Location/Context Check**:
   - Does the user mention a location ("in delhi", "near me", specific place)? → PLAN (need to handle location context)
   
3. **Quantity/List Check**:
   - Does the user want multiple items? ("top 10", "list of", "show all") → PLAN
   
4. **Action Complexity**:
   - Single system command? → COMMAND
   - Multiple steps or web interaction? → PLAN
   - Just a fact? → SEARCH
   - Just talking? → CHAT

{memory_context}{session_context}
### USER INPUT
"{text}"

### LEARNING EXAMPLES (Study these patterns carefully)

User: "show me latest news in delhi top 10 trending news"
→ {{"action": "PLAN", "confidence": 0.95, "reasoning": "User wants current news data from web, with location context (Delhi) and quantity (top 10). Requires web scraping and filtering."}}

User: "show me latest news near me top 10"
→ {{"action": "PLAN", "confidence": 0.95, "reasoning": "User wants current news with location awareness. Need to detect user location and fetch relevant news."}}

User: "Show me top 10 hacker news posts"
→ {{"action": "PLAN", "confidence": 0.95, "reasoning": "User wants live data from Hacker News website, requires web interaction"}}

User: "install docker"
→ {{"action": "COMMAND", "command": "/install docker", "confidence": 0.98, "reasoning": "Simple package installation command"}}

User: "what is docker?"
→ {{"action": "CHAT", "confidence": 0.90, "reasoning": "Informational question, user wants explanation not action"}}

User: "check my disk space"
→ {{"action": "PLAN", "confidence": 0.85, "reasoning": "Requires system check and formatted output"}}

User: "who is the CEO of Google?"
→ {{"action": "SEARCH", "confidence": 0.95, "reasoning": "Simple fact lookup"}}

User: "download latest VSCode"
→ {{"action": "PLAN", "confidence": 0.92, "reasoning": "Multi-step: find download link, download, potentially install"}}

User: "get weather in Mumbai"
→ {{"action": "PLAN", "confidence": 0.90, "reasoning": "Requires fetching current weather data for specific location"}}

User: "trending topics on twitter"
→ {{"action": "PLAN", "confidence": 0.93, "reasoning": "Needs real-time social media data"}}

### CRITICAL DECISION RULES (NEVER VIOLATE THESE)

1. **Web Data = PLAN**: If answer requires checking ANY website or getting current/live data → PLAN
2. **Location Context = PLAN**: If user specifies a place or says "near me" → PLAN (not SEARCH)
3. **Lists/Rankings = PLAN**: "top X", "latest Y", "trending Z" → PLAN (needs structured retrieval)
4. **Simple Facts = SEARCH**: "who is X", "what is Y", "when did Z" (historical facts) → SEARCH
5. **System Commands = COMMAND**: Only for package management (install/remove/update)
6. **Default to ACTION**: When uncertain between PLAN and CHAT → Choose PLAN

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

                action = str(intent_data.get("action", "CHAT")).upper()
                confidence = float(intent_data.get("confidence", 0.5))
                reasoning = str(intent_data.get("reasoning", ""))
                
                command_str = str(intent_data.get("command", "")) if intent_data.get("command") else ""
                cmd = None
                args = None
                
                if action == "COMMAND" and command_str:
                     parts = command_str.split(" ", 1)
                     cmd = parts[0]
                     args = parts[1] if len(parts) > 1 else ""

                return Intent(
                    action=action,
                    command=cmd,
                    args=args,
                    confidence=confidence,
                    reasoning=reasoning
                )

            except Exception as e:
                # If LLM logic fails completely
                pass


        
        # Default: PLAN (not CHAT) - Better to attempt action than just talk
        return Intent(
            action="PLAN",
            confidence=0.5,
            reasoning="No clear intent detected. Defaulting to PLAN to attempt forming an action plan."
        )
