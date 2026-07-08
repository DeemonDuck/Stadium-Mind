"""
core/venue.py

Defines the stadium as a graph: gates, sections, and amenities are nodes;
corridors connecting them are edges with a walking-distance weight.

This graph is the single shared data structure used by both agents:
- The Organizer Agent reasons about congestion AT nodes.
- The Fan Agent finds paths ALONG edges between nodes.

In a real deployment, this would be generated from an actual venue floor plan
(e.g. loaded from a JSON file or CAD export). For the hackathon MVP, it's
hardcoded here for one sample stadium layout.
"""

import networkx as nx


def build_venue_graph() -> nx.Graph:
    """
    Construct and return the stadium venue graph.

    Node types:
        "gate"    - entry/exit points
        "section" - seating areas
        "amenity" - restrooms, food courts, etc.

    Edge weight:
        "weight" - approximate walking distance in meters between two
                   directly connected locations.

    Returns:
        networkx.Graph: an undirected graph representing the venue.
    """
    G = nx.Graph()

    # --- Nodes ---
    nodes = {
        "Gate_A": "gate",
        "Gate_B": "gate",
        "Gate_C": "gate",
        "Section_1": "section",
        "Section_2": "section",
        "Section_3": "section",
        "Restroom_1": "amenity",
        "Restroom_2": "amenity",
        "FoodCourt_1": "amenity",
    }
    for name, kind in nodes.items():
        G.add_node(name, type=kind)

    # --- Edges: (node_a, node_b, distance_in_meters) ---
    edges = [
        ("Gate_A", "Section_1", 40),
        ("Gate_B", "Section_2", 35),
        ("Gate_C", "Section_3", 50),
        ("Section_1", "Restroom_1", 20),
        ("Section_2", "Restroom_1", 25),
        ("Section_2", "FoodCourt_1", 30),
        ("Section_3", "Restroom_2", 20),
        ("Section_1", "Section_2", 60),
        ("Section_2", "Section_3", 60),
    ]
    for a, b, dist in edges:
        G.add_edge(a, b, weight=dist)

    return G


def get_nodes_by_type(graph: nx.Graph, node_type: str) -> list:
    """
    Return all node names of a given type ("gate", "section", or "amenity").
    Useful for populating dropdowns in the UI, e.g. "pick your destination amenity".
    """
    return [n for n, data in graph.nodes(data=True) if data.get("type") == node_type]


if __name__ == "__main__":
    # Quick manual sanity check when running this file directly:
    #   python core/venue.py
    G = build_venue_graph()
    print("All nodes:", list(G.nodes(data=True)))
    print("Amenities only:", get_nodes_by_type(G, "amenity"))
    print(
        "Shortest path Gate_A -> Restroom_2 (unweighted by crowd):",
        nx.shortest_path(G, "Gate_A", "Restroom_2", weight="weight"),
    )
