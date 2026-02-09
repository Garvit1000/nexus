"""
Session Manager - Maintains conversation context across turns.

This module provides stateful tracking of user interactions, enabling
the agent to maintain context and reference previous actions.
"""

import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta


@dataclass
class SessionTurn:
    """Represents a single interaction turn in the conversation."""
    user_input: str
    intent_action: str  # CHAT, COMMAND, PLAN, SEARCH, etc.
    intent_reasoning: str
    result: Optional[str] = None
    success: bool = True
    timestamp: float = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()
    
    def age_seconds(self) -> float:
        """Returns how many seconds ago this turn occurred."""
        return time.time() - self.timestamp
    
    def is_recent(self, max_age_seconds: int = 300) -> bool:
        """Check if this turn is recent (default: within 5 minutes)."""
        return self.age_seconds() < max_age_seconds


class SessionManager:
    """
    Maintains conversation context across multiple user turns.
    
    Key Features:
    - Tracks conversation history
    - Detects context references ("it", "them", "now")
    - Caches results for fast retrieval
    - Provides temporal awareness
    """
    
    def __init__(self, max_history: int = 50):
        self.history: List[SessionTurn] = []
        self.max_history = max_history
        self.cached_results: Dict[str, Any] = {}
        
    def add_turn(self, user_input: str, intent_action: str, intent_reasoning: str, 
                 result: Optional[str] = None, success: bool = True) -> None:
        """
        Records a new turn in the conversation.
        
        Args:
            user_input: The user's input text
            intent_action: The detected action (CHAT, PLAN, etc.)
            intent_reasoning: Why this action was chosen
            result: The output/result of the action
            success: Whether the action succeeded
        """
        turn = SessionTurn(
            user_input=user_input,
            intent_action=intent_action,
            intent_reasoning=intent_reasoning,
            result=result,
            success=success
        )
        
        self.history.append(turn)
        
        # Trim history if too long
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]
        
        # Cache successful results for quick retrieval
        if success and result:
            cache_key = f"{intent_action}:{hash(user_input)}"
            self.cached_results[cache_key] = {
                'result': result,
                'timestamp': time.time()
            }
    
    def get_last_turn(self, max_age_seconds: int = 300) -> Optional[SessionTurn]:
        """
        Get the last turn if it's recent enough.
        
        Args:
            max_age_seconds: Maximum age in seconds (default: 5 minutes)
            
        Returns:
            The last SessionTurn if recent, None otherwise
        """
        if not self.history:
            return None
        
        last = self.history[-1]
        return last if last.is_recent(max_age_seconds) else None
    
    def detect_context_reference(self, user_input: str) -> bool:
        """
        Detects if the user is referring to previous context.
        
        Examples:
            - "now show me the posts" → True
            - "give me them" → True
            - "what about that?" → True
            - "install docker" → False
        """
        text_lower = user_input.lower().strip()
        
        # Short follow-up pattern (under 10 words, contains context keywords)
        words = text_lower.split()
        if len(words) > 15:  # Long queries are likely new requests
            return False
        
        context_patterns = [
            # Pronouns
            r'\bit\b', r'\bthem\b', r'\bthose\b', r'\bthat\b', r'\bthis\b',
            # Temporal markers
            r'\bnow\b', r'\bjust\b', r'\bagain\b',
            # Demonstratives
            r'\bshow\s+me\b', r'\bgive\s+me\b', r'\bdisplay\b',
            # Context actions
            r'\bsame\b', r'\bprevious\b', r'\blast\b', r'\bprior\b'
        ]
        
        import re
        return any(re.search(pattern, text_lower) for pattern in context_patterns)
    
    def get_context_for_decision(self, user_input: str) -> Optional[Dict[str, Any]]:
        """
        Get relevant context for the decision engine.
        
        Returns context dict if user is likely referencing previous action,
        None otherwise.
        """
        if not self.detect_context_reference(user_input):
            return None
        
        last_turn = self.get_last_turn(max_age_seconds=600)  # 10 min window
        if not last_turn:
            return None
        
        return {
            'last_action': last_turn.intent_action,
            'last_input': last_turn.user_input,
            'last_result': last_turn.result,
            'last_reasoning': last_turn.intent_reasoning,
            'age_seconds': last_turn.age_seconds(),
            'success': last_turn.success
        }
    
    def get_recent_history(self, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get recent conversation history.
        
        Args:
            limit: Maximum number of turns to return
            
        Returns:
            List of turn dictionaries
        """
        recent = [turn for turn in self.history if turn.is_recent(600)]  # 10 min
        return [asdict(turn) for turn in recent[-limit:]]
    
    def get_summary(self) -> str:
        """
        Generate a human-readable summary of recent activity.
        """
        if not self.history:
            return "No recent activity."
        
        recent = [turn for turn in self.history if turn.is_recent(300)]
        if not recent:
            return "No recent activity (within 5 minutes)."
        
        lines = []
        for turn in recent[-3:]:  # Last 3 recent turns
            age = int(turn.age_seconds())
            status = "✓" if turn.success else "✗"
            lines.append(
                f"{status} {age}s ago: {turn.user_input[:50]} → {turn.intent_action}"
            )
        
        return "\n".join(lines)
    
    def clear(self) -> None:
        """Clear all session history and cached results."""
        self.history.clear()
        self.cached_results.clear()
