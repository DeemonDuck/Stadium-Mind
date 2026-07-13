"""
tests/conftest.py

Forces every test into mock mode, regardless of the developer's environment.

WHY THIS EXISTS:
The suite asserts mock-mode behaviour (the "[MOCK RESPONSE ...]" strings, no
network calls) but never actually *forced* that mode - it just happened to get
it, because CI runs with no GROQ_API_KEY and no .env file. On any machine that
does have a real key configured - the normal state for anyone who has actually
run the app - load_dotenv() picks it up at import time, both agents build a live
client, and the mock-mode tests fail. Worse, the end-to-end ones would make real,
billable, non-deterministic network calls.

That's a test-isolation bug, not an environment quirk: a suite shouldn't depend
on an ambient secret being *absent* to pass. This autouse fixture pins both
agents' module-level `_client` back to None for the duration of every test, so
mock mode is an explicit precondition of the suite rather than an accident of
wherever it happens to run.

Both agents read `_client` as a module global at call time (`if _client is
None: ...`), so patching the attribute is enough - no re-import needed.

Note this deliberately does NOT patch GROQ_API_KEY itself: test_core.py's
test_openai_client_can_be_constructed builds its own client directly to guard
the openai/httpx incompatibility that broke the first deploy (see BUILD_LOG.md,
Day 4). That test constructs a client but makes no network call, so it's
unaffected by - and must stay independent of - this fixture.
"""

import pytest

import agents.fan_agent as fan_agent
import agents.organizer_agent as organizer_agent


@pytest.fixture(autouse=True)
def force_mock_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin both agents into mock mode for every test in the suite."""
    monkeypatch.setattr(fan_agent, "_client", None)
    monkeypatch.setattr(organizer_agent, "_client", None)
