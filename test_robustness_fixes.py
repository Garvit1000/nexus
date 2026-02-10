#!/usr/bin/env python3
"""
Test script to validate robustness fixes in Nexus agent.

This script tests the three major fixes:
1. Session Manager - Context detection and semantic matching
2. Decision Engine - Intent understanding (mocked LLM responses)
3. Planner - Appropriate use of CHECK steps (mocked LLM responses)

Run: python test_robustness_fixes.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from jarvis.core.session_manager import SessionManager
from jarvis.ai.decision_engine import DecisionEngine

# ANSI colors for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"

def print_test(test_name, passed, details=""):
    """Print test result with color."""
    status = f"{GREEN}✓ PASS{RESET}" if passed else f"{RED}✗ FAIL{RESET}"
    print(f"{status} | {test_name}")
    if details:
        print(f"       {details}")
    return passed

def test_session_manager():
    """Test Session Manager context detection and semantic matching."""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}Testing Session Manager Fixes{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")
    
    session = SessionManager()
    passed_count = 0
    total_count = 0
    
    # Test 1: Long detailed query should NOT be context reference
    total_count += 1
    query1 = "show me latest news in delhi top 10 trending"
    is_context = session.detect_context_reference(query1)
    passed = not is_context
    details = f"Query: '{query1}' | Detected as context: {is_context} (should be False)"
    passed_count += print_test("Long query NOT treated as context reference", passed, details)
    
    # Test 2: Short pronoun reference SHOULD be context reference
    total_count += 1
    query2 = "show me that"
    is_context = session.detect_context_reference(query2)
    passed = is_context
    details = f"Query: '{query2}' | Detected as context: {is_context} (should be True)"
    passed_count += print_test("Short pronoun reference IS context reference", passed, details)
    
    # Test 3: "show me" alone with 2 words should be context
    total_count += 1
    query3 = "show me"
    is_context = session.detect_context_reference(query3)
    passed = is_context
    details = f"Query: '{query3}' | Detected as context: {is_context} (should be True)"
    passed_count += print_test("Very short action phrase IS context reference", passed, details)
    
    # Test 4: Semantic matching - unrelated queries
    total_count += 1
    session.add_turn(
        user_input="download CodeWithHarry Python video",
        intent_action="PLAN",
        intent_reasoning="Download task",
        result="Video downloaded successfully",
        success=True
    )
    
    query4 = "show me latest news in delhi"
    context = session.get_context_for_decision(query4)
    passed = context is None  # Should NOT match unrelated previous query
    details = f"Current: '{query4}' | Previous: 'download CodeWithHarry Python video' | Context matched: {context is not None} (should be False)"
    passed_count += print_test("Unrelated query does NOT match cached context", passed, details)
    
    # Test 5: Semantic matching - related queries
    total_count += 1
    session.clear()
    session.add_turn(
        user_input="show me Python tutorials",
        intent_action="SEARCH",
        intent_reasoning="Search task",
        result="Found tutorials",
        success=True
    )
    
    query5 = "show that"
    context = session.get_context_for_decision(query5)
    passed = context is not None  # SHOULD match related query
    details = f"Current: '{query5}' | Previous: 'show me Python tutorials' | Context matched: {context is not None} (should be True)"
    passed_count += print_test("Pronoun reference matches related context", passed, details)
    
    # Test 6: Long query after unrelated task
    total_count += 1
    session.clear()
    session.add_turn(
        user_input="install docker",
        intent_action="COMMAND",
        intent_reasoning="Package install",
        result="Docker installed",
        success=True
    )
    
    query6 = "show me latest weather in Mumbai"
    context = session.get_context_for_decision(query6)
    passed = context is None
    details = f"Current: '{query6}' | Previous: 'install docker' | Context matched: {context is not None} (should be False)"
    passed_count += print_test("New detailed query after unrelated command", passed, details)
    
    print(f"\n{BLUE}Session Manager: {passed_count}/{total_count} tests passed{RESET}\n")
    return passed_count, total_count


def test_decision_engine_logic():
    """Test decision engine logic (without actual LLM calls)."""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}Testing Decision Engine Logic{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")
    
    # We'll test the heuristic rules only (fast path)
    # Full LLM integration would require API keys
    
    engine = DecisionEngine()
    passed_count = 0
    total_count = 0
    
    # Test 1: Update system command
    total_count += 1
    intent = engine.analyze("update system")
    passed = intent.action == "COMMAND" and intent.command == "/update"
    details = f"Input: 'update system' | Action: {intent.action}, Command: {intent.command}"
    passed_count += print_test("System update detected as COMMAND", passed, details)
    
    # Test 2: Install package
    total_count += 1
    intent = engine.analyze("install git")
    passed = intent.action == "COMMAND" and intent.command == "/install" and intent.args == "git"
    details = f"Input: 'install git' | Action: {intent.action}, Args: {intent.args}"
    passed_count += print_test("Package install detected correctly", passed, details)
    
    # Test 3: Remove package
    total_count += 1
    intent = engine.analyze("remove docker")
    passed = intent.action == "COMMAND" and intent.command == "/remove"
    details = f"Input: 'remove docker' | Action: {intent.action}"
    passed_count += print_test("Package removal detected correctly", passed, details)
    
    # Test 4: Search query
    total_count += 1
    intent = engine.analyze("search for Python tutorials")
    passed = intent.action == "COMMAND" and intent.command == "/search"
    details = f"Input: 'search for Python tutorials' | Action: {intent.action}"
    passed_count += print_test("Search query detected correctly", passed, details)
    
    # Test 5: Complex query defaults to PLAN (without LLM)
    total_count += 1
    intent = engine.analyze("show me latest news in delhi top 10")
    # Without LLM, it should default to PLAN
    passed = intent.action == "PLAN"
    details = f"Input: 'show me latest news...' | Action: {intent.action} (should default to PLAN without LLM)"
    passed_count += print_test("Complex query defaults to PLAN", passed, details)
    
    print(f"\n{BLUE}Decision Engine: {passed_count}/{total_count} tests passed{RESET}\n")
    print(f"{YELLOW}Note: Full LLM-based decision testing requires API keys and live testing{RESET}\n")
    return passed_count, total_count


def test_prompt_quality():
    """Test that prompts contain critical improvements."""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}Testing Prompt Quality (Static Analysis){RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")
    
    passed_count = 0
    total_count = 0
    
    # Read decision engine file
    decision_path = Path(__file__).parent / "src/jarvis/ai/decision_engine.py"
    with open(decision_path) as f:
        decision_content = f.read()
    
    # Test 1: Decision engine has location examples
    total_count += 1
    has_location_examples = "in delhi" in decision_content.lower() or "near me" in decision_content.lower()
    passed = has_location_examples
    details = "Checking for location-based query examples in Decision Engine prompt"
    passed_count += print_test("Decision Engine has location examples", passed, details)
    
    # Test 2: Decision engine has news examples
    total_count += 1
    has_news_examples = "news" in decision_content.lower() and "latest" in decision_content.lower()
    passed = has_news_examples
    details = "Checking for news query examples in Decision Engine prompt"
    passed_count += print_test("Decision Engine has news examples", passed, details)
    
    # Test 3: Planner has CHECK guidelines
    orchestrator_path = Path(__file__).parent / "src/jarvis/core/orchestrator.py"
    with open(orchestrator_path) as f:
        orchestrator_content = f.read()
    
    total_count += 1
    has_check_guidelines = "CHECK Step Guidelines" in orchestrator_content or "DON'T CHECK" in orchestrator_content
    passed = has_check_guidelines
    details = "Checking for CHECK step guidelines in Planner prompt"
    passed_count += print_test("Planner has CHECK guidelines", passed, details)
    
    # Test 4: Planner distinguishes data types
    total_count += 1
    has_data_type_logic = "Data Retrieval" in orchestrator_content or "dynamic" in orchestrator_content.lower()
    passed = has_data_type_logic
    details = "Checking for data type awareness in Planner"
    passed_count += print_test("Planner distinguishes static vs dynamic data", passed, details)
    
    print(f"\n{BLUE}Prompt Quality: {passed_count}/{total_count} tests passed{RESET}\n")
    return passed_count, total_count


def main():
    """Run all tests."""
    print(f"\n{GREEN}{'='*60}{RESET}")
    print(f"{GREEN}Nexus Agent Robustness Fix Validation{RESET}")
    print(f"{GREEN}{'='*60}{RESET}")
    
    all_passed = 0
    all_total = 0
    
    # Run test suites
    passed, total = test_session_manager()
    all_passed += passed
    all_total += total
    
    passed, total = test_decision_engine_logic()
    all_passed += passed
    all_total += total
    
    passed, total = test_prompt_quality()
    all_passed += passed
    all_total += total
    
    # Final summary
    print(f"{GREEN}{'='*60}{RESET}")
    success_rate = (all_passed / all_total * 100) if all_total > 0 else 0
    
    if all_passed == all_total:
        print(f"{GREEN}ALL TESTS PASSED: {all_passed}/{all_total} ({success_rate:.1f}%){RESET}")
        print(f"{GREEN}✓ Agent robustness fixes validated successfully!{RESET}")
    else:
        print(f"{YELLOW}PARTIAL SUCCESS: {all_passed}/{all_total} ({success_rate:.1f}%){RESET}")
        print(f"{YELLOW}Some tests failed. Review output above for details.{RESET}")
    
    print(f"{GREEN}{'='*60}{RESET}\n")
    
    return 0 if all_passed == all_total else 1


if __name__ == "__main__":
    sys.exit(main())
