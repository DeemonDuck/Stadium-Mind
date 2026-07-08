"""
agents/fan_agent.py

The "navigation + multi-language" half of StadiumMind. Given a fan's
current location and destination, finds a congestion-aware route (via
core.routing) and asks an LLM to phrase it as short, friendly directions
in the fan's chosen language.

MOCK MODE:
If no GROQ_API_KEY is found, falls back to an untranslated template
response instead of crashing. The route itself is always REAL (routing
doesn't need the LLM) - only the friendly phrasing/translation is mocked.
Once GROQ_API_KEY is set in .env, this automatically switches over.
"""

import os
from dotenv import load_dotenv
from core.routing import congestion_weighted_path

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL = "llama-3.1-8b-instant"  # fast model - plenty for short directions/translation

_client = None
if GROQ_API_KEY and GROQ_API_KEY != "your_groq_api_key_here":
    from openai import OpenAI
    _client = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")


def _build_prompt(path: list, distance: float, language: str) -> str:
    """Build the LLM prompt. Separate function so it can be tweaked/tested in isolation."""
    path_description = " -> ".join(path)
    return f"""A fan at a stadium wants directions to their destination.
The recommended route (already chosen to avoid crowded areas) is:
{path_description}
Total approximate distance: {distance:.0f} meters.

Write these directions as 2-3 short, friendly, easy-to-follow sentences,
in {language}. Mention that this route avoids the busiest areas."""


def _mock_directions(path: list, distance: float, language: str) -> str:
    """
    PLACEHOLDER used only when no GROQ_API_KEY is configured.

    The route (path/distance) is always real - only the friendly phrasing
    and translation are mocked, since those genuinely need the LLM.
    Clearly labeled so it's never mistaken for real AI output.
    """
    path_description = " -> ".join(path)
    return (
        "[MOCK RESPONSE - add a real GROQ_API_KEY to .env for AI-written, translated directions]\n"
        f"Head this way: {path_description}. "
        f"Approx {distance:.0f} meters. This route avoids the most crowded areas right now.\n"
        f"(Requested language: {language} - mock mode does not translate.)"
    )


def get_fan_directions(graph, simulator, start: str, destination: str, language: str = "English"):
    """
    Main entry point used by app.py.

    Args:
        graph: the venue graph
        simulator: a CrowdSimulator instance with live congestion data
        start: fan's current location (node name)
        destination: where the fan wants to go (node name)
        language: language to phrase the directions in

    Returns:
        (directions_text, path): human-readable directions (real or mock),
        and the raw list of node names, useful for debugging/display.
    """
    path, distance = congestion_weighted_path(graph, simulator, start, destination)

    if _client is None:
        return _mock_directions(path, distance, language), path

    prompt = _build_prompt(path, distance, language)
    try:
        response = _client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.5,
        )
        return response.choices[0].message.content, path
    except Exception as e:
        return f"[AI temporarily unavailable: {e}]\n" + _mock_directions(path, distance, language), path


if __name__ == "__main__":
    # Quick manual check - run from project root with: python -m agents.fan_agent
    from core.venue import build_venue_graph
    from core.crowd_sim import CrowdSimulator

    G = build_venue_graph()
    sim = CrowdSimulator(G, seed=1)
    sim.trigger_incident("Section_1", spike=70)
    sim.trigger_incident("Restroom_1", spike=70)

    text, path = get_fan_directions(G, sim, "Gate_A", "Restroom_2", language="Hindi")
    print(text)
    print("Path:", path)
