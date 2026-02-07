from dataclasses import dataclass
from typing import Optional, Dict, Any
import re

@dataclass
class Intent:
    action: str  # COMMAND, CHAT, SEARCH, BROWSE
    command: Optional[str] = None
    args: Optional[str] = None
    confidence: float = 0.0
    reasoning: str = ""

class DecisionEngine:
    """
    The 'Brain' of Nexus. 
    Analyzes user input to decide the best course of action.
    Uses a mix of heuristic rules (fast) and LLM reasoning (smart).
    """
    
    def __init__(self, llm_client=None, router_client=None):
        self.llm_client = llm_client
        self.router_client = router_client

    def analyze(self, user_input: str) -> Intent:
        """
        Decide what to do with the user input.
        """
        text = user_input.strip().lower()

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

        # Transparency: Log model usage
        model_name = getattr(self.llm_client, "model_name", "Unknown Model")
        print(f"[dim]🧠 Decision Engine Thinking with: {model_name}[/dim]")

        # --- Slow Path: LLM Analysis ---(LLM Reasoning) ---
        # Prefer the fast Router Client (Groq) if available, otherwise fallback to main LLM.
        active_client = self.router_client if self.router_client else self.llm_client
        
        if active_client:
            # We ask the LLM to classify the intent.
            # We want a structured response (or distinct format).
            
            prompt = f"""
You are the Brain of Nexus, a Linux Assistant.
Analyze this user input and decide the best action. The user might want to run a command or just chat.

USER INPUT: "{text}"

AVAILABLE COMMANDS:
- /install <package> : Install tools (e.g. "install git", "I need python")
- /remove <package>  : Remove tools
- /update            : Update system/packages (e.g. "update my pc", "fix broken packages")
- /search <query>    : Google search (e.g. "who is ...", "weather in ...")
- /video <prompt>    : Generate video
- /browse <task>     : Browser automation
- PLAN               : Complex requests requiring multiple steps (e.g. "download X and run it", "extract this and move it").
- CHAT               : General conversation.

RULES:
1. If the user wants to PERFORM an action supported by a command, return the command.
2. If the user just wants to chat or ask "how to", return CHAT.
3. If the request implies a sequence of actions (browser + terminal), return PLAN.
4. BE AGGRESSIVE about mapping to commands if the intent is clear.

OUTPUT FORMAT:
Return a JSON object with:
{{
  "action": "COMMAND", "PLAN", or "CHAT",
  "command": "/command args" (if action is COMMAND, else null),
  "confidence": <float 0.0-1.0>,
  "reasoning": "<brief explanation>"
}}
"""
            try:
                # We use a lower temperature if possible, but our client interface is simple.
                response_text = active_client.generate_response(prompt).strip()
                
                # Default fallback
                intent_data = {"action": "CHAT", "confidence": 0.5, "reasoning": "Failed to parse Brain response."}

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

                action = intent_data.get("action", "CHAT").upper()
                confidence = float(intent_data.get("confidence", 0.5))
                reasoning = intent_data.get("reasoning", "")
                
                command_str = intent_data.get("command", "")
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

            except Exception as e:
                # If LLM fails, fall back to chat
                pass
        
        # Default: Chat
        return Intent(action="CHAT", confidence=0.5, reasoning="No intent detected. Defaulting to Chat.")
