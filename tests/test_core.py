"""
tests/test_core.py

Lightweight sanity tests for the non-LLM core logic - the venue graph,
crowd simulator, and congestion-aware routing. Deliberately does NOT test
the agents' LLM output (that's mocked/non-deterministic); it tests the
data and routing logic that everything else depends on.

Run with: pytest tests/test_core.py -v
(or just: python -m pytest)
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.venue import build_venue_graph, get_nodes_by_type
from core.crowd_sim import CrowdSimulator
from core.routing import congestion_weighted_path


def test_venue_graph_has_expected_nodes():
    G = build_venue_graph()
    assert "Gate_A" in G.nodes
    assert "Restroom_2" in G.nodes
    assert len(G.nodes) == 9


def test_get_nodes_by_type_filters_correctly():
    G = build_venue_graph()
    amenities = get_nodes_by_type(G, "amenity")
    assert set(amenities) == {"Restroom_1", "Restroom_2", "FoodCourt_1"}


def test_crowd_simulator_starts_within_expected_range():
    G = build_venue_graph()
    sim = CrowdSimulator(G, seed=1)
    for node in G.nodes:
        score = sim.get_congestion(node)
        assert 0 <= score <= 100


def test_tick_keeps_scores_in_bounds():
    G = build_venue_graph()
    sim = CrowdSimulator(G, seed=1)
    for _ in range(50):  # stress-test many ticks
        sim.tick()
    for node in G.nodes:
        assert 0 <= sim.get_congestion(node) <= 100


def test_trigger_incident_increases_congestion_and_caps_at_100():
    G = build_venue_graph()
    sim = CrowdSimulator(G, seed=1)
    before = sim.get_congestion("Gate_A")
    sim.trigger_incident("Gate_A", spike=200)  # deliberately huge spike
    after = sim.get_congestion("Gate_A")
    assert after > before
    assert after == 100  # must clamp, never exceed


def test_congestion_label_thresholds():
    G = build_venue_graph()
    sim = CrowdSimulator(G, seed=1)
    sim.congestion["Gate_A"] = 10
    assert sim.get_congestion_label("Gate_A") == "low"
    sim.congestion["Gate_A"] = 40
    assert sim.get_congestion_label("Gate_A") == "moderate"
    sim.congestion["Gate_A"] = 60
    assert sim.get_congestion_label("Gate_A") == "high"
    sim.congestion["Gate_A"] = 90
    assert sim.get_congestion_label("Gate_A") == "critical"


def test_congestion_aware_path_reroutes_around_a_real_incident():
    """
    This is the core 'unique hook' of the whole project - proving that
    congestion actually changes the chosen route, not just the display.
    """
    G = build_venue_graph()
    sim = CrowdSimulator(G, seed=1)

    plain_path = list(__import__("networkx").shortest_path(G, "Gate_A", "Restroom_2", weight="weight"))

    # Heavily congest a node that sits on the plain shortest path
    sim.trigger_incident("Section_1", spike=70)
    sim.trigger_incident("Restroom_1", spike=70)

    aware_path, _ = congestion_weighted_path(G, sim, "Gate_A", "Restroom_2")

    assert aware_path != plain_path, "Congestion-aware path should differ from the plain shortest path once a node on it is heavily congested"
    assert "Restroom_1" not in aware_path, "Should route around the congested Restroom_1 node"


def test_congestion_aware_path_matches_plain_path_when_uncongested():
    """When nothing is congested, the 'smart' path should behave like a normal shortest path."""
    import networkx as nx

    G = build_venue_graph()
    sim = CrowdSimulator(G, seed=1)
    # Force everything to zero congestion for this test
    for node in sim.congestion:
        sim.congestion[node] = 0

    aware_path, _ = congestion_weighted_path(G, sim, "Gate_A", "Restroom_2")
    plain_path = nx.shortest_path(G, "Gate_A", "Restroom_2", weight="weight")

    assert aware_path == plain_path


if __name__ == "__main__":
    # Allows running directly with `python tests/test_core.py` without pytest installed
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
