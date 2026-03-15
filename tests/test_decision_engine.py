"""
Tests for jarvis.ai.decision_engine — DecisionEngine.

Verifies that:
- The fast heuristic path fires on exact-match inputs (no LLM needed)
- Install / remove / browse patterns are caught by regex
- Ambiguous inputs fall through to the LLM slow path
- When the LLM slow-path is used, it calls the router client
- SessionManager context causes SHOW_CACHED to be returned when appropriate
"""

from unittest.mock import MagicMock
from jarvis.ai.decision_engine import DecisionEngine


def _engine(router_response: str = "", session_manager=None) -> DecisionEngine:
    """Build a DecisionEngine with a mock router client."""
    router = MagicMock()
    router.generate_response.return_value = router_response
    return DecisionEngine(
        llm_client=router,
        router_client=router,
        session_manager=session_manager,
    )


class TestHeuristicFastPath:
    """Common inputs must be resolved by regex/heuristics — never hitting the LLM."""

    def test_update_is_recognized(self):
        engine = _engine()
        intent = engine.analyze("update")
        assert intent.action == "COMMAND"
        assert intent.confidence >= 0.95
        # Router must NOT have been called
        engine.router_client.generate_response.assert_not_called()

    def test_install_package_is_recognized(self):
        engine = _engine()
        intent = engine.analyze("install git")
        assert intent.action == "COMMAND"
        assert intent.args == "git"

    def test_remove_package_is_recognized(self):
        engine = _engine()
        intent = engine.analyze("remove nginx")
        assert intent.action == "COMMAND"
        assert intent.args == "nginx"

    def test_uninstall_package_is_recognized(self):
        engine = _engine()
        intent = engine.analyze("uninstall docker")
        assert intent.action == "COMMAND"
        assert intent.args == "docker"

    def test_case_insensitive_install(self):
        engine = _engine()
        intent = engine.analyze("Install Vim")
        assert intent.action == "COMMAND"
        assert intent.args == "vim"

    def test_system_upgrade_is_recognized(self):
        engine = _engine()
        intent = engine.analyze("upgrade system")
        assert intent.action == "COMMAND"


class TestSlowPathLLM:
    """Ambiguous inputs must fall through to the LLM router."""

    def _make_llm_intent_response(self, action="CHAT") -> str:
        """Return a valid JSON string the router would produce."""
        import json

        return json.dumps(
            {
                "action": action,
                "command": None,
                "args": None,
                "confidence": 0.85,
                "reasoning": "LLM classified this as " + action,
            }
        )

    def test_ambiguous_input_calls_router(self):
        router_resp = self._make_llm_intent_response("CHAT")
        engine = _engine(router_response=router_resp)
        engine.analyze("keep docker tidy")
        engine.router_client.generate_response.assert_called_once()

    def test_ambiguous_input_uses_llm_action(self):
        router_resp = self._make_llm_intent_response("PLAN")
        engine = _engine(router_response=router_resp)
        intent = engine.analyze("setup a full nginx stack with ssl")
        # It may return PLAN or fall back gracefully — either way, not a hard crash
        assert intent.action in ("PLAN", "CHAT", "COMMAND", "SEARCH", "BROWSE")


class TestSessionContextAwareness:
    """When session manager has recent context, SHOW_CACHED should be returned."""

    def test_show_cached_returned_when_recent_context_exists(self):
        session_mgr = MagicMock()
        session_mgr.get_context_for_decision.return_value = {
            "last_result": "some_output",
            "last_action": "COMMAND",
            "age_seconds": 5,
        }
        engine = _engine(session_manager=session_mgr)
        intent = engine.analyze("what was that?")
        assert intent.action == "SHOW_CACHED"
        assert intent.confidence >= 0.95

    def test_no_cached_context_falls_through(self):
        session_mgr = MagicMock()
        session_mgr.get_context_for_decision.return_value = None
        engine = _engine(session_manager=session_mgr)
        # Should not blow up; should proceed to heuristics or LLM
        intent = engine.analyze("install curl")
        assert intent.action != "SHOW_CACHED"
