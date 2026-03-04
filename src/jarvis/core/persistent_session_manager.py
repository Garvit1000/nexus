"""
Persistent Session Manager - Saves session state to disk.

This enhancement allows session context to survive app restarts.
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional
from .session_manager import SessionManager, SessionTurn


class PersistentSessionManager(SessionManager):
    """
    SessionManager with disk persistence.
    
    Saves session state to ~/.nexus/session.json
    Automatically restores on initialization.
    """
    
    def __init__(self, max_history: int = 50, session_file: Optional[str] = None):
        super().__init__(max_history=max_history)
        
        # Default session file location
        if session_file is None:
            session_dir = Path.home() / ".nexus"
            session_dir.mkdir(exist_ok=True)
            self.session_file = session_dir / "session.json"
        else:
            self.session_file = Path(session_file)
        
        # Try to restore previous session
        self.restore()
    
    def add_turn(self, user_input: str, intent_action: str, intent_reasoning: str,
                 result: Optional[str] = None, success: bool = True) -> None:
        """Add turn and save to disk."""
        super().add_turn(user_input, intent_action, intent_reasoning, result, success)
        self.save()
    
    def save(self) -> bool:
        """
        Save current session to disk.
        
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            session_data = {
                'history': [
                    {
                        'user_input': turn.user_input,
                        'intent_action': turn.intent_action,
                        'intent_reasoning': turn.intent_reasoning,
                        'result': turn.result,
                        'success': turn.success,
                        'timestamp': turn.timestamp
                    }
                    for turn in self.history
                ],
                'cached_results': self.cached_results
            }
            
            with open(self.session_file, 'w') as f:
                json.dump(session_data, f, indent=2)
            
            return True
        except Exception as e:
            logging.warning(f"Failed to save session: {e}")
            return False
    
    def restore(self) -> bool:
        """
        Restore session from disk.
        
        Returns:
            True if restored successfully, False otherwise
        """
        if not self.session_file.exists():
            return False
        
        try:
            with open(self.session_file, 'r') as f:
                session_data = json.load(f)
            
            # Restore history
            self.history = [
                SessionTurn(
                    user_input=turn['user_input'],
                    intent_action=turn['intent_action'],
                    intent_reasoning=turn['intent_reasoning'],
                    result=turn.get('result'),
                    success=turn.get('success', True),
                    timestamp=turn.get('timestamp')
                )
                for turn in session_data.get('history', [])
            ]
            
            # Restore cached results
            self.cached_results = session_data.get('cached_results', {})
            
            # Only keep recent history (within 24 hours)
            import time
            cutoff = time.time() - (24 * 60 * 60)
            self.history = [
                turn for turn in self.history 
                if turn.timestamp and turn.timestamp > cutoff
            ]
            
            logging.info(f"Restored session: {len(self.history)} turns from last 24h")
            return True
            
        except Exception as e:
            logging.warning(f"Could not restore session: {e}")
            # Session restore is best-effort
            return False
    
    def clear(self) -> None:
        """Clear session and delete file."""
        super().clear()
        try:
            if self.session_file.exists():
                self.session_file.unlink()
        except Exception:
            pass


# Example usage in console_app.py:
# from ..core.persistent_session_manager import PersistentSessionManager
# self.session_manager = PersistentSessionManager(max_history=50)
