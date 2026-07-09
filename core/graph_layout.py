"""
core/graph_layout.py

Computes 2D positions for the venue graph, used only for visualization -
has zero effect on routing or congestion logic, purely cosmetic.

Strategy: fix the 8 sections on a circle (since they form the concourse
ring in the real layout), then let networkx's spring layout settle every
other node (gates, amenities, medical/info/parking/vip/exit) around those
fixed anchors. This keeps the recognizable "ring" shape without having to
hand-place all 22 nodes individually - and it keeps working automatically
if more nodes get added later.
"""

import numpy as np
import networkx as nx


def compute_layout(graph) -> dict:
    """
    Args:
        graph: the venue graph

    Returns:
        {node_name: (x, y)} - deterministic (fixed seed), so the map
        doesn't visually jump around between reruns/sessions.
    """
    sections = [n for n, d in graph.nodes(data=True) if d.get("type") == "section"]
    # Sort numerically (Section_1, Section_2, ... Section_8) so they're
    # placed around the circle in the same order they connect to each other
    sections.sort(key=lambda n: int(n.split("_")[1]))

    fixed_pos = {}
    n = len(sections)
    for i, node in enumerate(sections):
        angle = 2 * np.pi * i / n
        fixed_pos[node] = (np.cos(angle), np.sin(angle))

    pos = nx.spring_layout(
        graph,
        pos=fixed_pos,
        fixed=list(fixed_pos.keys()),
        seed=42,
        k=0.9,
        iterations=100,
    )
    return {node: (float(xy[0]), float(xy[1])) for node, xy in pos.items()}


if __name__ == "__main__":
    # Quick manual check: python core/graph_layout.py
    from venue import build_venue_graph

    G = build_venue_graph()
    positions = compute_layout(G)
    for node, (x, y) in positions.items():
        print(f"{node}: ({x:.2f}, {y:.2f})")
