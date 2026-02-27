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
        
        Robust logic: Only match when user is CLEARLY referring to past context,
        not when making a new request that happens to contain common words.
        
        Examples:
            - "show me that" → True (pronoun reference)
            - "do it again" → True (temporal + action reference)
            - "what about them?" → True (pronoun)
            - "show me latest news in delhi" → False (complete new request)
            - "install docker" → False (new request)
        """
        text_lower = user_input.lower().strip()
        words = text_lower.split()
        
        # CRITICAL FIX: Long queries with specific details are NEW requests
        if len(words) > 10:  # Most context references are short
            return False
        
        import re
        
        # Strong pronoun indicators (very likely context reference)
        strong_pronouns = [
            r'\bit\b', r'\bthem\b', r'\bthose\b', r'\bthat\b', r'\bthis\b'
        ]
        has_strong_pronoun = any(re.search(pattern, text_lower) for pattern in strong_pronouns)
        
        # Temporal + action combo (e.g., "now show", "again do")
        temporal_markers = [r'\bnow\b', r'\bjust\b', r'\bagain\b']
        has_temporal = any(re.search(pattern, text_lower) for pattern in temporal_markers)
        
        # Reference words
        reference_words = [r'\bsame\b', r'\bprevious\b', r'\bprior\b']
        has_reference = any(re.search(pattern, text_lower) for pattern in reference_words)
        
        # FIXED: "show me" or "give me" alone is NOT enough - need pronoun or very short query
        action_phrases = [r'\bshow\s+me\b', r'\bgive\s+me\b', r'\bdisplay\b']
        has_action_phrase = any(re.search(pattern, text_lower) for pattern in action_phrases)
        
        # Decision logic: Need STRONG evidence of context reference
        if has_strong_pronoun:
            return True
        
        # Temporal + action (e.g., "now show") with short query
        if has_temporal and has_action_phrase and len(words) <= 5:
            return True
        
        # Reference words (e.g., "same thing", "previous one")
        if has_reference:
            return True
        
        # Action phrase alone with VERY short query (2-3 words max)
        if has_action_phrase and len(words) <= 3:
            return True
        
        return False
    
    def get_context_for_decision(self, user_input: str) -> Optional[Dict[str, Any]]:
        """
        Get relevant context for the decision engine.
        
        Enhanced with semantic similarity check to prevent false positives.
        
        Returns context dict if user is likely referencing previous action,
        None otherwise.
        """
        if not self.detect_context_reference(user_input):
            return None
        
        last_turn = self.get_last_turn(max_age_seconds=600)  # 10 min window
        if not last_turn:
            return None
            
        # CRITICAL FIX: Add semantic similarity check
        # Only return cached context if current request is semantically related to previous one
        if not self._is_semantically_related(user_input, last_turn.user_input):
            return None
        
        return {
            'last_action': last_turn.intent_action,
            'last_input': last_turn.user_input,
            'last_result': last_turn.result,
            'last_reasoning': last_turn.intent_reasoning,
            'age_seconds': last_turn.age_seconds(),
            'success': last_turn.success
        }
    
    def _is_semantically_related(self, current_input: str, previous_input: str) -> bool:
        """
        Check if two inputs are semantically related using keyword overlap.
        
        This prevents showing cached results from completely unrelated previous queries.
        
        Examples:
            - "show that" (current) vs "download file" (previous) → True (pronoun reference)
            - "show me news in delhi" (current) vs "download CodeWithHarry podcast" (previous) → False (unrelated)
        """
        current_lower = current_input.lower()
        previous_lower = previous_input.lower()
        
        # Extract meaningful words (filter out common words)
        stop_words = {
            'show', 'me', 'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for',
            'of', 'and', 'or', 'but', 'is', 'are', 'was', 'were', 'be',
            'get', 'give', 'make', 'do', 'my', 'your', 'it', 'this', 'that'
        }
        
        def extract_keywords(text):
            words = text.split()
            return {w for w in words if len(w) > 2 and w not in stop_words}
        
        current_keywords = extract_keywords(current_lower)
        previous_keywords = extract_keywords(previous_lower)
        
        # If current query has very few keywords (e.g., "show that"), it's a pronoun reference
        # In this case, we trust the context reference detection
        if len(current_keywords) <= 2:
            return True  # Likely just pronoun reference, trust it
        
        # If current query has substantial keywords, check for overlap
        if not current_keywords or not previous_keywords:
            return False
        
        # Calculate keyword overlap
        overlap = current_keywords & previous_keywords
        overlap_ratio = len(overlap) / min(len(current_keywords), len(previous_keywords))
        
        # Require at least 30% keyword overlap for semantic relatedness
        return overlap_ratio >= 0.3
    
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
