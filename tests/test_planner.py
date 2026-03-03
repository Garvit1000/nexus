"""
Tests for jarvis.core.orchestrator — Planner class.

Verifies that:
- A valid LLM response produces the correct TaskStep list
- Each fallback client is tried when the primary client fails
- Exponential backoff is applied between fallback attempts
- A completely exhausted LLM pool returns an empty list
- Malformed JSON from LLM returns an empty list
"""

import pytest
import time
from unittest.mock import MagicMock, patch
from jarvis.core.orchestrator import Planner, TaskStep


def make_client(response: str = "", raises: bool = False):
    """Helper to create a lightweight mock LLM client."""
    class _C:
        model_name = "mock"
        def generate_response(self, _p):
            if raises:
                raise Exception("429 Rate Limited")
            return response
    return _C()


VALID_PLAN = '[{"description":"Echo test","action":"TERMINAL","command":"echo test"}]'
MULTI_PLAN = (
    '[{"description":"Check","action":"CHECK","command":"which docker"},'
    '{"description":"Install","action":"TERMINAL","command":"apt install docker"}]'
)


class TestPlannerParsing:
    """The Planner must correctly parse well-formed LLM responses."""

    def test_valid_response_creates_steps(self):
        planner = Planner(make_client(VALID_PLAN))
        steps = planner.create_plan("do something")
        assert len(steps) == 1
        assert isinstance(steps[0], TaskStep)

    def test_step_fields_are_populated(self):
        planner = Planner(make_client(VALID_PLAN))
        steps = planner.create_plan("echo test")
        s = steps[0]
        assert s.description == "Echo test"
        assert s.action == "TERMINAL"
        assert s.command == "echo test"

    def test_multi_step_plan_all_parsed(self):
        planner = Planner(make_client(MULTI_PLAN))
        steps = planner.create_plan("install docker")
        assert len(steps) == 2
        assert steps[0].action == "CHECK"
        assert steps[1].action == "TERMINAL"

    def test_step_ids_are_sequential(self):
        planner = Planner(make_client(MULTI_PLAN))
        steps = planner.create_plan("x")
        assert [s.id for s in steps] == [1, 2]

    def test_malformed_json_returns_empty_list(self):
        planner = Planner(make_client("this is not json"))
        steps = planner.create_plan("do something")
        assert steps == []

    def test_markdown_fences_are_stripped(self):
        """LLM sometimes wraps JSON in ```json ... ``` fences."""
        fenced = f"```json\n{VALID_PLAN}\n```"
        planner = Planner(make_client(fenced))
        steps = planner.create_plan("x")
        assert len(steps) == 1


class TestPlannerFallback:
    """The Planner must fall through to the next client when the primary fails."""

    def test_fallback_client_used_on_primary_failure(self):
        primary = make_client(raises=True)
        fallback = make_client(VALID_PLAN)
        planner = Planner(primary, fallback_clients=[fallback])
        steps = planner.create_plan("do something")
        assert len(steps) == 1

    def test_all_clients_fail_returns_empty_list(self):
        clients = [make_client(raises=True) for _ in range(3)]
        planner = Planner(clients[0], fallback_clients=clients[1:])
        steps = planner.create_plan("do something")
        assert steps == []

    def test_exponential_backoff_called_between_fallbacks(self):
        """time.sleep must be called once between the 1st and 2nd client."""
        primary = make_client(raises=True)
        fallback = make_client(VALID_PLAN)
        planner = Planner(primary, fallback_clients=[fallback])

        with patch("jarvis.core.orchestrator.time.sleep") as mock_sleep:
            planner.create_plan("x")

        # sleep must be called at least once (for attempt=1)
        mock_sleep.assert_called_once()
        delay = mock_sleep.call_args.args[0]
        assert delay >= 2.0  # 2^1 + jitter >= 2.0
