"""
tests/test_app.py

Integration tests for app.py using Streamlit's official AppTest framework
(streamlit.testing.v1), which runs the real script through Streamlit's own
script runner and lets us click buttons / set widget values / read the
resulting session state - without a browser.

WHY THIS EXISTS:
BUILD_LOG.md documents manually re-running AppTest for every new flow (mode
toggle, transit comparison, task board) during development, but none of
that was committed as an automated test - app.py's tab-wiring had zero
CI-enforced coverage even though tests/test_core.py and tests/test_agents.py
cover everything underneath it. This closes that gap for the flows that
matter most: shared session-state init, all three tabs existing, and one
concrete interaction per tab (the same ones BUILD_LOG.md says were checked
by hand).

Runs with no GROQ_API_KEY set (same as CI for every other test file), so
every agent call below exercises mock mode - deterministic, no network.

Run with: pytest tests/test_app.py -v
"""

import os

from streamlit.testing.v1 import AppTest

APP_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app.py"))


def _run_app() -> AppTest:
    """Fresh AppTest instance, run once (a full script execution - the
    equivalent of a first page load, not a partial fragment rerun)."""
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()
    return at


def _click(at: AppTest, label: str) -> None:
    """Click the first button matching this exact label, then rerun.
    Matches by label rather than position, since button order isn't part
    of the contract this test suite wants to pin down."""
    matches = [b for b in at.button if b.label == label]
    assert matches, f"No button found with label {label!r}"
    matches[0].click().run()


def _set_selectbox(at: AppTest, widget_label: str, value: str) -> None:
    """Set the first selectbox matching this widget label, then rerun."""
    matches = [s for s in at.selectbox if s.label == widget_label]
    assert matches, f"No selectbox found with label {widget_label!r}"
    matches[0].set_value(value).run()


def _set_radio(at: AppTest, widget_label: str, value: str) -> None:
    """Set the first radio matching this widget label, then rerun."""
    matches = [r for r in at.radio if r.label == widget_label]
    assert matches, f"No radio found with label {widget_label!r}"
    matches[0].set_value(value).run()


def test_app_runs_without_exceptions():
    """The single most important check: a fresh load of app.py (all three
    tabs execute unconditionally - Streamlit runs every st.tabs() block on
    every script run, tab selection is a CSS/UI state, not a Python
    branch) raises nothing."""
    at = _run_app()
    assert not at.exception


def test_app_initializes_shared_session_state():
    """Regression test for the shared-state block at the top of app.py -
    graph/simulator/positions get built, and the volunteer-board state
    (including the new task_translations cache) starts empty."""
    at = _run_app()
    assert at.session_state["graph"] is not None
    assert at.session_state["simulator"] is not None
    assert at.session_state["positions"]
    assert at.session_state["incidents"] == []
    assert at.session_state["volunteer_tasks"] == {}
    assert at.session_state["task_translations"] == {}


def test_app_shows_three_tabs_in_expected_order():
    at = _run_app()
    labels = [tab.label for tab in at.tabs]
    assert labels == ["📊 Organizer Dashboard", "🧭 Fan Assistant", "🦺 Volunteer & Staff Board"]


def test_organizer_recommendation_button_returns_mock_recommendation():
    """Tab 1: 'Ask Stadium Brain' -> Get Recommendation, in mock mode
    (no GROQ_API_KEY in this test environment)."""
    at = _run_app()
    _click(at, "Get Recommendation")
    assert not at.exception
    assert any("MOCK" in info.value for info in at.info)


def test_fan_assistant_navigate_mode_returns_mock_directions():
    """Tab 2, default mode ('Navigate inside the venue'): Get Directions
    for the default start/destination pair (Gate_A -> Restroom_2, which
    are different nodes, so this doesn't hit the 'already there' warning
    branch)."""
    at = _run_app()
    _click(at, "Get Directions")
    assert not at.exception
    assert any("MOCK RESPONSE" in success.value for success in at.success)


def test_fan_assistant_transit_mode_toggle_reveals_transit_controls():
    """Tab 2: switching the mode radio to 'Getting to the stadium' should
    swap in the transit-comparison controls - this is the mode-toggle flow
    BUILD_LOG.md mentions checking manually."""
    at = _run_app()
    _set_radio(at, "What do you need help with?", "🚌 Getting to the stadium")
    assert not at.exception
    gate_selectors = [s for s in at.selectbox if s.label == "Which gate are you headed to?"]
    assert gate_selectors, "Transit mode should show a gate selector once toggled on"

    _click(at, "Compare Transit Options")
    assert not at.exception
    assert any("MOCK RESPONSE" in success.value for success in at.success)
    # Sustainability counter (Tab 1) should reflect this comparison.
    assert at.session_state["total_green_trips"] == 1


def test_volunteer_board_refresh_populates_tasks_and_language_selector_translates_them():
    """Tab 3: the flow BUILD_LOG.md calls out by name - refresh generates
    tasks from current conditions, and switching the language selector
    translates their descriptions (this project's newest multilingual
    feature, extending the Fan Assistant's translate pattern to the
    Volunteer & Staff Board)."""
    at = _run_app()
    _click(at, "🔄 Refresh Tasks from Current Conditions")
    assert not at.exception
    assert len(at.session_state["volunteer_tasks"]) > 0

    _set_selectbox(at, "Task language", "Spanish")
    assert not at.exception
    translations = at.session_state["task_translations"]
    assert len(translations) > 0
    assert all("[MOCK" in text for text in translations.values())


if __name__ == "__main__":
    # Allows running directly with `python tests/test_app.py` without pytest installed
    import traceback

    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    passed, failed = 0, 0
    for t in tests:
        try:
            t()
            print(f"PASS: {t.__name__}")
            passed += 1
        except Exception:
            print(f"FAIL: {t.__name__}")
            traceback.print_exc()
            failed += 1
    print(f"\n{passed} passed, {failed} failed")