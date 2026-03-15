"""
Tests for jarvis.core.session_manager — SessionManager.

Verifies that:
- Turns are recorded and retrievable
- History is trimmed when max_history is exceeded
- Context references are detected correctly
- Semantic relatedness prevents false-positive cache hits
- get_last_turn respects max_age_seconds
- get_summary returns a human-readable string
"""

import time
from jarvis.core.session_manager import SessionManager, SessionTurn


class TestSessionTurn:
    def test_timestamp_auto_assigned(self):
        turn = SessionTurn(
            user_input="hi", intent_action="CHAT", intent_reasoning="test"
        )
        assert turn.timestamp is not None
        assert abs(turn.timestamp - time.time()) < 2

    def test_is_recent_true_for_new_turn(self):
        turn = SessionTurn(
            user_input="hi", intent_action="CHAT", intent_reasoning="test"
        )
        assert turn.is_recent(max_age_seconds=10) is True

    def test_is_recent_false_for_old_turn(self):
        turn = SessionTurn(
            user_input="hi",
            intent_action="CHAT",
            intent_reasoning="test",
            timestamp=time.time() - 600,
        )
        assert turn.is_recent(max_age_seconds=300) is False

    def test_age_seconds_returns_positive(self):
        turn = SessionTurn(
            user_input="hi",
            intent_action="CHAT",
            intent_reasoning="test",
            timestamp=time.time() - 5,
        )
        assert turn.age_seconds() >= 4


class TestAddTurn:
    def test_add_turn_appends(self):
        sm = SessionManager()
        sm.add_turn("hi", "CHAT", "greeting")
        assert len(sm.history) == 1
        assert sm.history[0].user_input == "hi"

    def test_add_turn_stores_result(self):
        sm = SessionManager()
        sm.add_turn("do thing", "COMMAND", "reason", result="done", success=True)
        assert sm.history[0].result == "done"

    def test_history_trimmed_at_max(self):
        sm = SessionManager(max_history=3)
        for i in range(5):
            sm.add_turn(f"msg-{i}", "CHAT", "test")
        assert len(sm.history) == 3
        assert sm.history[0].user_input == "msg-2"

    def test_cached_results_dict_exists(self):
        sm = SessionManager()
        assert isinstance(sm.cached_results, dict)


class TestGetLastTurn:
    def test_returns_none_when_empty(self):
        sm = SessionManager()
        assert sm.get_last_turn() is None

    def test_returns_last_turn_when_recent(self):
        sm = SessionManager()
        sm.add_turn("hi", "CHAT", "test")
        last = sm.get_last_turn(max_age_seconds=10)
        assert last is not None
        assert last.user_input == "hi"

    def test_returns_none_when_too_old(self):
        sm = SessionManager()
        sm.add_turn("hi", "CHAT", "test")
        sm.history[0].timestamp = time.time() - 1000
        assert sm.get_last_turn(max_age_seconds=5) is None


class TestContextReferenceDetection:
    def test_pronoun_with_action(self):
        sm = SessionManager()
        assert sm.detect_context_reference("show me that") is True

    def test_short_pronoun(self):
        sm = SessionManager()
        assert sm.detect_context_reference("what about it?") is True

    def test_do_it_again(self):
        sm = SessionManager()
        assert sm.detect_context_reference("do it again") is True

    def test_previous_result(self):
        sm = SessionManager()
        assert sm.detect_context_reference("show previous result") is True

    def test_new_request_no_reference(self):
        sm = SessionManager()
        assert sm.detect_context_reference("install docker") is False

    def test_long_query_is_not_reference(self):
        sm = SessionManager()
        long_q = "show me the latest trending news articles from delhi about technology in india right now"
        assert sm.detect_context_reference(long_q) is False

    def test_same_keyword(self):
        sm = SessionManager()
        assert sm.detect_context_reference("same thing") is True


class TestSemanticRelatedness:
    def test_short_pronoun_is_related(self):
        sm = SessionManager()
        assert sm._is_semantically_related("show that", "download file") is True

    def test_overlapping_keywords_related(self):
        sm = SessionManager()
        assert (
            sm._is_semantically_related(
                "show me more docker logs", "check docker container"
            )
            is True
        )

    def test_no_overlap_unrelated(self):
        sm = SessionManager()
        assert (
            sm._is_semantically_related(
                "show me news in delhi today", "download CodeWithHarry podcast episode"
            )
            is False
        )


class TestGetContextForDecision:
    def test_returns_none_when_no_reference(self):
        sm = SessionManager()
        sm.add_turn("install curl", "COMMAND", "reason", result="ok")
        assert sm.get_context_for_decision("install docker") is None

    def test_returns_context_when_reference_detected(self):
        sm = SessionManager()
        sm.add_turn("install curl", "COMMAND", "reason", result="installed")
        ctx = sm.get_context_for_decision("show that")
        assert ctx is not None
        assert ctx["last_action"] == "COMMAND"

    def test_returns_none_when_history_too_old(self):
        sm = SessionManager()
        sm.add_turn("install curl", "COMMAND", "reason", result="ok")
        sm.history[0].timestamp = time.time() - 9999
        assert sm.get_context_for_decision("show that") is None


class TestGetRecentHistory:
    def test_returns_list_of_dicts(self):
        sm = SessionManager()
        sm.add_turn("hi", "CHAT", "test")
        sm.add_turn("bye", "CHAT", "test")
        history = sm.get_recent_history(limit=5)
        assert isinstance(history, list)
        assert len(history) == 2
        assert "user_input" in history[0]

    def test_limit_caps_results(self):
        sm = SessionManager()
        for i in range(10):
            sm.add_turn(f"msg-{i}", "CHAT", "test")
        history = sm.get_recent_history(limit=3)
        assert len(history) == 3


class TestGetSummary:
    def test_empty_history_message(self):
        sm = SessionManager()
        assert "No recent activity" in sm.get_summary()

    def test_recent_turns_appear_in_summary(self):
        sm = SessionManager()
        sm.add_turn("install docker", "COMMAND", "test", success=True)
        summary = sm.get_summary()
        assert "install docker" in summary
        assert "COMMAND" in summary


class TestClear:
    def test_clear_empties_history(self):
        sm = SessionManager()
        sm.add_turn("hi", "CHAT", "test")
        sm.clear()
        assert len(sm.history) == 0
