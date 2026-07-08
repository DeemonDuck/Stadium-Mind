"""
core/crowd_sim.py

Simulates real-time crowd density at each node of the venue graph.

WHY THIS EXISTS:
A real stadium deployment would plug in actual sensor/camera/ticket-scan data
here instead of random numbers. For the hackathon MVP, this class stands in
for that data feed so the rest of the system (agents, UI) can be built and
demoed without needing physical sensors.

Both agents read from this same simulator:
    - Organizer Agent reads congestion to recommend actions.
    - Fan Agent reads congestion to avoid crowded routes.
"""

import random


class CrowdSimulator:
    """
    Tracks a congestion score (0-100) for every node in the venue graph.
    0 = empty, 100 = dangerously overcrowded.
    """

    def __init__(self, graph, seed: int | None = None):
        """
        Args:
            graph: the venue graph (from core.venue.build_venue_graph)
            seed: optional random seed, useful for reproducible demos
        """
        self.graph = graph
        if seed is not None:
            random.seed(seed)
        # Every location starts at a random low-to-moderate congestion level
        self.congestion = {node: random.randint(10, 30) for node in graph.nodes}

    def tick(self) -> None:
        """
        Advance the simulation by one time step.
        Each node's congestion randomly drifts, clamped to [0, 100].

        The drift range is slightly biased upward (-8 to +12) to mimic a
        stadium filling up over the course of an event, which makes for a
        more interesting live demo than pure random noise.
        """
        for node in self.congestion:
            drift = random.randint(-8, 12)
            self.congestion[node] = max(0, min(100, self.congestion[node] + drift))

    def trigger_incident(self, node: str, spike: int = 40) -> None:
        """
        Manually spike congestion at a specific node.
        Used to simulate a sudden crowd surge for demo purposes
        (e.g. "everyone rushes the exit after the match ends").

        Args:
            node: name of the node to spike (must exist in the graph)
            spike: how much to add to current congestion (default 40)
        """
        if node in self.congestion:
            self.congestion[node] = min(100, self.congestion[node] + spike)

    def get_congestion(self, node: str) -> int:
        """Return the current congestion score (0-100) for a single node."""
        return self.congestion.get(node, 0)

    def get_all(self) -> dict:
        """Return a snapshot of congestion for every node, as {node: score}."""
        return dict(self.congestion)

    def get_congestion_label(self, node: str) -> str:
        """
        Convert a numeric score into a human-readable label.
        Used both in the UI (color-coded metrics) and in LLM prompts,
        since "high" reads more naturally to a model than a raw number.
        """
        score = self.get_congestion(node)
        if score >= 75:
            return "critical"
        elif score >= 50:
            return "high"
        elif score >= 25:
            return "moderate"
        return "low"


if __name__ == "__main__":
    # Quick manual check: python core/crowd_sim.py
    from venue import build_venue_graph

    G = build_venue_graph()
    sim = CrowdSimulator(G, seed=1)
    print("Initial congestion:", sim.get_all())

    sim.tick()
    print("After 1 tick:", sim.get_all())

    sim.trigger_incident("Gate_A")
    print("After incident at Gate_A:", sim.get_all())
    print("Gate_A label:", sim.get_congestion_label("Gate_A"))
