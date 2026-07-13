"""
agents/llm_client.py

The one place StadiumMind talks to an LLM.

WHY THIS EXISTS:
Both agents used to carry their own private copy of the same three things -
the GROQ_API_KEY lookup, the client construction, and the
call-it-and-fall-back-to-a-mock block. That last one was duplicated four
times (get_organizer_recommendation, get_fan_directions,
get_transit_directions, translate_task_description), each an identical
~15-line dance of "no client? mock; call it; None content? mock; OpenAIError?
mock". Four copies of one policy is four places to forget to update it - and
the mock-fallback policy IS the resilience feature this project leans on, so
it's precisely the thing that shouldn't be scattered.

Now the agents own only what actually differs between them - their prompts,
their models, and their mock responses - and hand the call itself to
complete() below. Both agents keep their own MODEL because they genuinely
want different ones: the organizer needs reasoning (llama-3.3-70b-versatile),
the fan agent needs fast phrasing/translation (llama-3.1-8b-instant).

MOCK MODE:
If no usable key is configured, _client stays None and complete() returns the
caller's fallback() instead. That's the documented "runs with zero config"
behaviour: the whole app works end-to-end with data-driven placeholder text,
and switches to live AI the moment a real key appears - no code change.
"""

from __future__ import annotations

import os
from collections.abc import Callable

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# The value shipped in .env.example. Someone who copies the template without
# editing it has a "key" that isn't one, so treat it as no key at all rather
# than building a client that's guaranteed to 401 on first use.
PLACEHOLDER_KEY = "your_groq_api_key_here"

GROQ_BASE_URL = "https://api.groq.com/openai/v1"


def _get_groq_api_key() -> str | None:
    """
    Read GROQ_API_KEY from either source: local dev via .env/os.getenv, or
    Streamlit Community Cloud via st.secrets (Cloud doesn't deploy .env files,
    it injects secrets instead). Checking both is what lets the same code run
    unchanged in both environments.

    st.secrets.get() raises FileNotFoundError (specifically Streamlit's own
    StreamlitSecretNotFoundError) - it does NOT just return None - when no
    secrets.toml exists anywhere, as opposed to the key merely being absent
    from an existing one. That's the normal state for a fresh clone or a CI
    runner, so it has to be caught explicitly, or "mock mode needs zero config"
    would be a lie: the import itself would crash before mock mode ever got a
    chance to kick in.
    """
    key = os.getenv("GROQ_API_KEY")
    if key:
        return key
    try:
        return st.secrets.get("GROQ_API_KEY")
    except FileNotFoundError:
        return None


GROQ_API_KEY = _get_groq_api_key()

# Built once, shared by both agents. Only constructed when there's a real key,
# so the openai package's client config never even runs in mock mode.
_client = None
if GROQ_API_KEY and GROQ_API_KEY != PLACEHOLDER_KEY:
    from openai import OpenAI, OpenAIError

    _client = OpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL)


def complete(
    prompt: str,
    *,
    model: str,
    max_tokens: int,
    temperature: float,
    fallback: Callable[[], str],
) -> str:
    """
    Send one prompt to the LLM and return its text, degrading to fallback()
    instead of raising on every failure mode there is.

    This is the single implementation of StadiumMind's mock-fallback policy.
    There are exactly three ways a call can fail to produce usable text, and
    all three end at the same place - the caller's fallback:

      1. No client at all (no key configured) -> never call out, just fallback.
      2. The SDK types .message.content as `str | None`; a refused or
         tool-call-only response really does carry no text. Fall back rather
         than let a None flow into st.info()/st.success() downstream.
      3. An OpenAIError - rate limit, timeout, auth, connection blip. A live
         demo shouldn't die because Groq hiccuped, so annotate and fall back.
         Deliberately NOT `except Exception`: that would also swallow genuine
         bugs in our own code, which is the opposite of helpful.

    Args:
        prompt: the fully-built prompt text
        model: which Groq model to use (agents differ - see module docstring)
        max_tokens: cap on the response length
        temperature: sampling temperature
        fallback: zero-arg callable returning the mock text to use if the real
            call can't produce any. Taken as a callable, not a plain string, so
            the mock is only built if it's actually needed.

    Returns:
        The model's text, or the fallback's - always a usable string, never None.
    """
    if _client is None:
        return fallback()

    try:
        response = _client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        content = response.choices[0].message.content
        if content is None:
            return fallback()
        return content.strip()
    except OpenAIError as e:
        return f"[AI temporarily unavailable: {e}]\n" + fallback()
